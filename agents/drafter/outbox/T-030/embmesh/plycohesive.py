"""Cohesive ply-interface emitter and inserter for the plywise mesher."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

from .errors import MesherInputError


def _keyword(line: str) -> str:
    """Return the lowercase keyword at the start of an Abaqus keyword line."""
    return line.strip().split(",")[0].lower()


def _option(line: str, name: str) -> str | None:
    """Extract an option value from an Abaqus keyword line, e.g. name=Cohesion."""
    m = re.search(r"(?:^|,)\s*" + re.escape(name) + r"\s*=\s*([^,]+)", line, re.I)
    return m.group(1).strip() if m else None


def has_surface_interaction(deck_content: str | Sequence[str], interaction: str = "Cohesion") -> bool:
    """Check whether *Surface Interaction, name=<interaction> is defined in the deck."""
    lines = deck_content.splitlines() if isinstance(deck_content, str) else deck_content
    target = interaction.strip().lower()
    for line in lines:
        s = line.strip()
        if s.startswith("*") and not s.startswith("**"):
            if _keyword(s) == "*surface interaction":
                name = _option(s, "name")
                if name and name.strip("'\"").lower() == target:
                    return True
    return False


def cohesive_contact_lines(
    interface_pairs: Sequence[tuple[str, str]],
    interaction: str = "Cohesion",
    slave: str = "lower",
    unique_cpset: bool = True,
) -> list[str]:
    """Generate *Contact Pair lines for adjacent ply interface pairs.

    Parameters:
        interface_pairs: Sequence of (lower_surface_name, upper_surface_name),
                         e.g. [("Ply-1_top", "Ply-2_bottom"), ...]
        interaction: Name of the existing *Surface Interaction in the deck.
        slave: Which surface to designate as slave ("lower" or "upper").
               The reference deck Meshing/stack.inp uses "back, front2" where
               "back" is on Plate-1 (lower ply) and "front2" on Plate-2 (upper ply),
               meaning slave="lower" is the default matching reference convention.
        unique_cpset: Whether to assign a unique cpset name to each pair,
                      e.g. 'cohesion_1', 'cohesion_2'. Default True.

    Returns:
        list of strings representing the Abaqus contact pair block.
    """
    if slave not in ("lower", "upper"):
        raise ValueError(f"slave must be 'lower' or 'upper', got {slave!r}")

    lines: list[str] = []
    for k, (lower_surf, upper_surf) in enumerate(interface_pairs, start=1):
        if slave == "lower":
            slave_surf, master_surf = lower_surf, upper_surf
        else:
            slave_surf, master_surf = upper_surf, lower_surf

        cpset = f"cohesion_{k}" if unique_cpset else interaction.lower()
        lines.append(f"** Interaction: {cpset}")
        lines.append(
            f"*Contact Pair, interaction={interaction}, mechanical constraint=KINEMATIC, cpset={cpset}"
        )
        lines.append(f"{slave_surf}, {master_surf}")

    return lines


def insert_cohesive_contact(
    deck_text: str,
    interface_pairs: Sequence[tuple[str, str]],
    interaction: str = "Cohesion",
    slave: str = "lower",
    unique_cpset: bool = True,
) -> str:
    """Insert cohesive *Contact Pair blocks into the first *Step of the deck text.

    Refuses clearly if the deck has no *Surface Interaction with the specified name,
    or if the deck contains no *Step block.
    Idempotent: will not insert duplicate pairs if they are already present.

    Parameters:
        deck_text: Source Abaqus input deck as a string.
        interface_pairs: Sequence of (lower_surf, upper_surf) tuples.
        interaction: Name of the *Surface Interaction (default 'Cohesion').
        slave: 'lower' (default) or 'upper'.
        unique_cpset: Whether each pair gets a unique cpset name.

    Returns:
        Modified deck text string.
    """
    if not interface_pairs:
        return deck_text

    # Validate that *Surface Interaction exists in the deck
    if not has_surface_interaction(deck_text, interaction):
        raise MesherInputError(
            f"Source deck has no *Surface Interaction named '{interaction}'. "
            f"The mesher requires an existing interaction definition and will not invent one."
        )

    lines = deck_text.splitlines()

    # Find the first *Step block
    step_start = next((i for i, l in enumerate(lines) if _keyword(l) == "*step"), None)
    if step_start is None:
        raise MesherInputError("Source deck has no *Step block; cannot insert cohesive contact pairs.")

    step_end = next((i for i in range(step_start + 1, len(lines)) if _keyword(lines[i]) == "*end step"), None)
    if step_end is None:
        step_end = len(lines)

    step_lines = lines[step_start:step_end]

    # Filter out interface pairs that already exist (idempotence)
    # Check data lines under *Contact Pair
    existing_pairs = set()
    in_contact_pair = False
    for line in step_lines:
        s = line.strip()
        if s.startswith("*") and not s.startswith("**"):
            in_contact_pair = (_keyword(s) == "*contact pair")
        elif in_contact_pair and s and not s.startswith("**"):
            parts = [p.strip() for p in s.split(",")]
            if len(parts) >= 2:
                existing_pairs.add((parts[0], parts[1]))

    needed_pairs = []
    for lower_surf, upper_surf in interface_pairs:
        s_surf, m_surf = (lower_surf, upper_surf) if slave == "lower" else (upper_surf, lower_surf)
        if (s_surf, m_surf) not in existing_pairs:
            needed_pairs.append((lower_surf, upper_surf))

    if not needed_pairs:
        # All pairs already exist; return unchanged
        return deck_text

    # Generate lines to insert
    new_contact_lines = cohesive_contact_lines(
        needed_pairs,
        interaction=interaction,
        slave=slave,
        unique_cpset=unique_cpset,
    )

    # Determine insertion index within lines
    # Look for ** INTERACTIONS comment inside the step
    interactions_idx = None
    for idx in range(step_start, step_end):
        if lines[idx].strip().upper() == "** INTERACTIONS":
            interactions_idx = idx
            break

    if interactions_idx is not None:
        # Look for existing general contact *Contact or existing *Contact Pair after ** INTERACTIONS
        # Insert after any existing ** section comment lines (e.g. ** \n** INTERACTIONS\n** )
        insert_pos = interactions_idx + 1
        while insert_pos < step_end and lines[insert_pos].strip() == "**":
            insert_pos += 1
        # Insert here (before general contact or after existing contact pairs)
    else:
        # No ** INTERACTIONS comment found. Look for *Contact, or before output requests / *End Step
        target_pos = None
        for idx in range(step_start + 1, step_end):
            kw = _keyword(lines[idx])
            if kw in ("*contact", "*restart", "*output"):
                target_pos = idx
                break
            if lines[idx].strip().upper() == "** OUTPUT REQUESTS":
                target_pos = idx
                break

        if target_pos is None:
            target_pos = step_end

        # Prepend standard interactions header
        new_contact_lines = ["** ", "** INTERACTIONS", "** "] + new_contact_lines
        insert_pos = target_pos

    result_lines = lines[:insert_pos] + new_contact_lines + lines[insert_pos:]
    return "\n".join(result_lines) + "\n"


def insert_cohesive_contact_into_deck(
    source_deck: str | Path,
    output_deck: str | Path,
    interface_pairs: Sequence[tuple[str, str]],
    interaction: str = "Cohesion",
    slave: str = "lower",
    unique_cpset: bool = True,
) -> str:
    """Read source_deck, insert cohesive contact pairs, and write to output_deck."""
    source_path = Path(source_deck)
    output_path = Path(output_deck)

    text = source_path.read_text(encoding="utf-8")
    new_text = insert_cohesive_contact(
        text,
        interface_pairs=interface_pairs,
        interaction=interaction,
        slave=slave,
        unique_cpset=unique_cpset,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(new_text, encoding="utf-8")
    return new_text

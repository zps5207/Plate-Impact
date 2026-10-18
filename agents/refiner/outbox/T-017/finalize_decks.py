"""Normalize local mesher output and check the v500 contact-only change."""
from pathlib import Path
import difflib
import hashlib
import sys


def normalize(path):
    return Path(path).read_bytes().replace(b"\r\n", b"\n")


def main():
    baseline_generated, fiber_generated, reference, outdir = map(Path, sys.argv[1:5])
    outdir.mkdir(parents=True, exist_ok=True)
    baseline = normalize(baseline_generated)
    original = normalize(reference)
    if baseline != original:
        raise SystemExit("baseline differs from v500 reference")
    fiber = normalize(fiber_generated)
    duplicate = (b"*Surface Property Assignment, property=THICKNESS\n"
                 b"EMBMESH_FIBER_NODES, 0.000471406198242441\n")
    if fiber.count(duplicate) != 1:
        raise SystemExit("expected exactly one separate fiber thickness block")
    fiber = fiber.replace(duplicate, b"EMBMESH_FIBER_NODES, 0.000471406198242441\n")
    if fiber.count(b"*Surface Property Assignment, property=THICKNESS") != 1:
        raise SystemExit("unexpected thickness block count")
    (outdir / "v500_baseline.inp").write_bytes(baseline)
    (outdir / "v500_fiber_contact.inp").write_bytes(fiber)
    diff = "".join(difflib.unified_diff(
        baseline.decode().splitlines(keepends=True),
        fiber.decode().splitlines(keepends=True),
        fromfile="v500_baseline.inp", tofile="v500_fiber_contact.inp", n=2))
    (outdir / "fiber_contact.diff").write_text(diff, newline="\n")
    for name, data in (("baseline", baseline), ("fiber", fiber)):
        print(name, len(data), hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 5:
        raise SystemExit("usage: finalize_decks.py BASELINE_GEN FIBER_GEN REFERENCE OUTDIR")
    main()

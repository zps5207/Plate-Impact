"""Windows desktop wrapper for the embmesh command-line executable.

This intentionally keeps the mesher package unchanged.  It collects common
options and invokes the packaged ``embmesh.exe`` in a background process.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def engine_path() -> Path:
    """Find embmesh.exe both beside source and inside a PyInstaller bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        candidate = Path(bundled) / "embmesh.exe"
    else:
        candidate = Path(__file__).resolve().parent / "dist" / "embmesh.exe"
    if not candidate.is_file():
        raise FileNotFoundError(f"Could not find the mesher executable: {candidate}")
    return candidate


class DesktopApp(ttk.Frame):
    def __init__(self, master: tk.Tk) -> None:
        super().__init__(master, padding=14)
        self.master = master
        self.grid(sticky="nsew")
        master.title("Embedded Element Mesher")
        master.minsize(760, 610)
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)
        self.deck = tk.StringVar()
        self.instance = tk.StringVar()
        self.diameter = tk.StringVar(value="0.25")
        self.output = tk.StringVar()
        self.gap = tk.StringVar(value="0")
        self.fiber_type = tk.StringVar(value="truss")
        self.thickness_axis = tk.StringVar()
        self.precise_volume = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Choose an Abaqus input deck to begin.")
        self._build()

    def _build(self) -> None:
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text="Embedded Element Mesher", font=("Segoe UI", 16, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(self, text="Creates an embedded-fiber Abaqus deck using the bundled mesher.").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 12))
        self._path_row(2, "Input deck (.inp)", self.deck, self.choose_deck, "Browse…")
        self._path_row(3, "Output folder", self.output, self.choose_output, "Browse…")
        self._entry_row(4, "Instance name", self.instance, "Assembly instance to mesh, e.g. DISC-1")
        self._entry_row(5, "Fiber diameter", self.diameter, "Positive length in the deck's units")
        self._entry_row(6, "In-plane gap", self.gap, "Optional; default 0")
        ttk.Label(self, text="Fiber type").grid(row=7, column=0, sticky="w", pady=4)
        ttk.Combobox(self, textvariable=self.fiber_type, values=("truss", "beam"), state="readonly", width=18).grid(
            row=7, column=1, sticky="w", pady=4)
        ttk.Label(self, text="Thickness axis").grid(row=8, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=self.thickness_axis).grid(row=8, column=1, sticky="ew", pady=4)
        ttk.Label(self, text="Optional: x, y, z, or dx,dy,dz (normally auto-detected)").grid(row=8, column=2, sticky="w", padx=(8, 0))
        ttk.Checkbutton(self, text="Calculate precise per-host fiber volume (slower)", variable=self.precise_volume).grid(
            row=9, column=0, columnspan=3, sticky="w", pady=(6, 10))
        controls = ttk.Frame(self)
        controls.grid(row=10, column=0, columnspan=3, sticky="ew")
        self.run_button = ttk.Button(controls, text="Generate embedded mesh", command=self.run_mesh)
        self.run_button.pack(side="left")
        ttk.Button(controls, text="Open output folder", command=self.open_output).pack(side="left", padx=8)
        ttk.Label(self, textvariable=self.status).grid(row=11, column=0, columnspan=3, sticky="w", pady=(10, 4))
        self.log = tk.Text(self, height=14, wrap="word", state="disabled", font=("Cascadia Mono", 9))
        self.log.grid(row=12, column=0, columnspan=3, sticky="nsew")
        self.rowconfigure(12, weight=1)

    def _path_row(self, row: int, label: str, value: tk.StringVar, command, button: str) -> None:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=value).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Button(self, text=button, command=command).grid(row=row, column=2, sticky="w", padx=(8, 0), pady=4)

    def _entry_row(self, row: int, label: str, value: tk.StringVar, hint: str) -> None:
        ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=4)
        ttk.Entry(self, textvariable=value).grid(row=row, column=1, sticky="ew", pady=4)
        ttk.Label(self, text=hint).grid(row=row, column=2, sticky="w", padx=(8, 0))

    def choose_deck(self) -> None:
        name = filedialog.askopenfilename(title="Select Abaqus input deck", filetypes=[("Abaqus input decks", "*.inp"), ("All files", "*.*")])
        if name:
            self.deck.set(name)
            if not self.output.get():
                self.output.set(str(Path(name).with_suffix("")) + "-embmesh")

    def choose_output(self) -> None:
        name = filedialog.askdirectory(title="Select output folder")
        if name:
            self.output.set(name)

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def run_mesh(self) -> None:
        try:
            deck = Path(self.deck.get()).expanduser()
            if not deck.is_file():
                raise ValueError("Choose an existing .inp deck.")
            if not self.instance.get().strip():
                raise ValueError("Enter the assembly instance name.")
            if float(self.diameter.get()) <= 0:
                raise ValueError("Fiber diameter must be positive.")
            if float(self.gap.get()) < 0:
                raise ValueError("In-plane gap cannot be negative.")
            if not self.output.get().strip():
                raise ValueError("Choose an output folder.")
            output = Path(self.output.get()).expanduser()
            command = [str(engine_path()), "visualize", str(deck), "--instance", self.instance.get().strip(),
                       "--diameter", self.diameter.get(), "--output", str(output), "--gap", self.gap.get(),
                       "--fiber-type", self.fiber_type.get()]
            if self.thickness_axis.get().strip():
                command += ["--thickness-axis", self.thickness_axis.get().strip()]
            if self.precise_volume.get():
                command.append("--precise-volume")
        except (ValueError, FileNotFoundError) as exc:
            messagebox.showerror("Cannot generate mesh", str(exc), parent=self.master)
            return
        self.run_button.configure(state="disabled")
        self.status.set("Generating embedded mesh…")
        self.append_log("\n> " + subprocess.list2cmdline(command) + "\n")
        threading.Thread(target=self._worker, args=(command,), daemon=True).start()

    def _worker(self, command: list[str]) -> None:
        result = subprocess.run(command, capture_output=True, text=True, errors="replace")
        text = (result.stdout or "") + (result.stderr or "")
        self.master.after(0, self._finished, result.returncode, text)

    def _finished(self, returncode: int, text: str) -> None:
        self.append_log(text + ("\n" if text and not text.endswith("\n") else ""))
        self.run_button.configure(state="normal")
        if returncode == 0:
            self.status.set("Done. Open the output folder to find output.inp and visualization files.")
            messagebox.showinfo("Embedded mesh created", "Meshing completed successfully.", parent=self.master)
        else:
            self.status.set(f"Meshing failed (exit code {returncode}). See the log below.")
            messagebox.showerror("Meshing failed", "The mesher reported an error. See the log below.", parent=self.master)

    def open_output(self) -> None:
        folder = Path(self.output.get()).expanduser()
        if not folder.is_dir():
            messagebox.showwarning("Output folder unavailable", "Generate a mesh first, or choose an existing output folder.", parent=self.master)
            return
        os.startfile(folder)  # Windows desktop app


def main() -> None:
    root = tk.Tk()
    DesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

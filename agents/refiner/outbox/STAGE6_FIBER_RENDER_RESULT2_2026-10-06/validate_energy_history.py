"""Local contract tests for extract_energy_history.py without Abaqus."""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import types


SCRIPT = Path(__file__).with_name("extract_energy_history.py")


class HistoryOutput:
    def __init__(self, data):
        self.data = data


class Odb:
    def __init__(self, steps):
        self.steps = steps
        self.closed = False

    def close(self):
        self.closed = True


def load_module(odb):
    odb_access = types.ModuleType("odbAccess")
    odb_access.openOdb = lambda path, readOnly: odb
    previous = sys.modules.get("odbAccess")
    sys.modules["odbAccess"] = odb_access
    try:
        spec = importlib.util.spec_from_file_location("energy_extractor", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if previous is None:
            del sys.modules["odbAccess"]
        else:
            sys.modules["odbAccess"] = previous


def main():
    data = [(0.0, 0.0), (1.0e-7, 1.0), (2.0e-7, 2.0)]
    outputs = {
        "ALLKE": HistoryOutput(data),
        "ALLIE": HistoryOutput([(time, value + 10.0) for time, value in data]),
        "ALLWK": HistoryOutput([(time, value + 20.0) for time, value in data]),
        "ALLVD": HistoryOutput([(time, value + 30.0) for time, value in data]),
        "ETOTAL": HistoryOutput([(time, value + 40.0) for time, value in data]),
    }
    region = types.SimpleNamespace(historyOutputs=outputs)
    step = types.SimpleNamespace(historyRegions={"Assembly ASSEMBLY": region})
    odb = Odb({"Step-1": step})
    module = load_module(odb)

    key, selected = module.energy_region(step)
    assert key == "Assembly ASSEMBLY" and selected is region
    names, rows = module.aligned_energy_rows(region)
    assert names == ["ALLKE", "ALLIE", "ALLWK", "ALLVD", "ETOTAL"]
    assert rows[1] == [1.0e-7, 1.0, 11.0, 21.0, 31.0, 41.0]

    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "energy.csv"
        step_key, region_key, written_names, count = module.extract(
            "fixture.odb", "step-1", str(target))
        assert odb.closed
        assert step_key == "Step-1"
        assert region_key == "Assembly ASSEMBLY"
        assert written_names == names and count == 3
        with target.open(newline="") as handle:
            csv_rows = list(csv.reader(handle))
        assert csv_rows[0] == ["time"] + names
        assert len(csv_rows) == 4

    mismatched = types.SimpleNamespace(historyOutputs=dict(outputs))
    mismatched.historyOutputs["ALLWK"] = HistoryOutput([(0.0, 0.0)])
    try:
        module.aligned_energy_rows(mismatched)
    except RuntimeError as exc:
        assert "samples" in str(exc)
    else:
        raise AssertionError("mismatched history grids were accepted")

    print("energy history contract checks: PASS")


if __name__ == "__main__":
    main()

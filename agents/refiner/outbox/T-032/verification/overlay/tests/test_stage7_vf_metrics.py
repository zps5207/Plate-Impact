"""Regression tests for the Stage 7 result-checker correction."""
import importlib.util
from pathlib import Path
import sys
import types


METRICS = (Path(__file__).resolve().parents[1] / "verification" /
           "stage7_vf_metrics.py")
SPEC = importlib.util.spec_from_file_location("stage7_vf_metrics", METRICS)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

sys.path.insert(0, str(METRICS.parent))
sys.modules.setdefault("odbAccess", types.SimpleNamespace(openOdb=None))
CHECKER_SPEC = importlib.util.spec_from_file_location(
    "stage7_check_vf", METRICS.parent / "stage7_check_vf.py")
CHECKER = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(CHECKER)


def test_rel_is_relative_for_subunit_values():
    assert abs(MODULE.rel(1.1e-3, 1.0e-3) - 0.1) < 1.0e-15


def test_rel_exposes_reported_yield_mismatch():
    error = MODULE.rel(0.0016727478504808416, 0.0013462588880810975)
    assert abs(error - 0.24251573400202997) < 1.0e-15
    assert error > 0.03


def test_rel_has_explicit_zero_guard():
    assert MODULE.rel(0.0, 0.0) == 0.0
    assert MODULE.rel(1.0, 0.0) == float("inf")


def test_matching_time_diagnostic_retains_time_and_exact_half_force():
    full = [(0.0, 0.0, 0.0), (0.1, 0.0005, 1.0e8),
            (0.2, 0.0008, 1.6e8)]
    half = [(0.0, 0.0, 0.0), (0.1, 0.0005, 0.5e8),
            (0.2, 0.0008, 0.8e8)]
    result = CHECKER.matching_time_elastic(full, half)
    assert result["points"] == 2
    assert result["max_time_absolute_difference_s"] == 0.0
    assert result["max_nominal_strain_relative_error"] == 0.0
    assert result["max_half_force_relative_error"] == 0.0
    assert result["samples"][0]["vf05_over_vf0_reaction_ratio"] == 0.5

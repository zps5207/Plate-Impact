from verification.validate_vumat_fibers import run_truss_checks, run_beam_checks

def test_vumat_truss_local_oracle():
 results = run_truss_checks()
 assert all(r["passed"] for r in results), results

def test_vumat_beam_local_oracle():
 results = run_beam_checks()
 assert all(r["passed"] for r in results), results

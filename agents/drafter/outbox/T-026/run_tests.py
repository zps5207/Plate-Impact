import sys, os, pytest

if __name__ == '__main__':
    root = r"C:\Users\salas\OneDrive - The Pennsylvania State University\Plate Impact"
    t26 = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, t26)
    sys.path.insert(1, root)
    os.chdir(root)
    bdir = os.path.join(t26, ".tmp", "basetemp")
    cdir = os.path.join(t26, ".tmp", "pytest_cache")
    os.makedirs(bdir, exist_ok=True)
    os.makedirs(cdir, exist_ok=True)
    sys.exit(pytest.main(["-v", "tests", os.path.join(t26, "tests"), f"--basetemp={bdir}", "-o", f"cache_dir={cdir}"]))

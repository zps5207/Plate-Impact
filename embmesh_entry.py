import multiprocessing

from embmesh.cli import main

if __name__ == "__main__":
    # Required on Windows for a PyInstaller-frozen exe: without it, every
    # ProcessPoolExecutor worker spawned by embmesh.volume would re-run this
    # whole entry point (including re-parsing argv) instead of just executing
    # its assigned task.
    multiprocessing.freeze_support()
    raise SystemExit(main())

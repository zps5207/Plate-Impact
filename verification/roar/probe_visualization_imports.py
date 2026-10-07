"""Fast Abaqus/CAE noGUI probe for the visualization/display-group imports."""
from __future__ import print_function

from abaqus import session
from driverUtils import executeOnCaeStartup

executeOnCaeStartup()
import visualization
import displayGroupOdbToolset as display_group


def main():
    required = ("LeafFromElementSets", "LeafFromPartInstance")
    missing = [name for name in required if not hasattr(display_group, name)]
    if missing:
        raise RuntimeError(
            "displayGroupOdbToolset is missing: {0}".format(", ".join(missing)))
    if not hasattr(session, "Viewport"):
        raise RuntimeError("Abaqus session has no Viewport constructor")
    print("visualization module: {0}".format(
        getattr(visualization, "__file__", "<kernel built-in>")))
    print("display-group module: {0}".format(
        getattr(display_group, "__file__", "<kernel built-in>")))
    print("display-group constructors: {0}".format(", ".join(required)))
    print("VISUALIZATION_IMPORT_PROBE: PASS")


# Abaqus ``cae noGUI=...`` may not assign ``__main__`` to this script.
main()

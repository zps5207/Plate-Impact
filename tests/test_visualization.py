from embmesh.generate import mesh_flat

def test_visualization_outputs_and_symmetry(tmp_path):
    progress = []
    mesh_flat('examples/symmetry.inp', 'Q-1', .25, tmp_path, preview=False,
              progress=lambda percent, message: progress.append((percent, message)))
    text=(tmp_path/'output.inp').read_text()
    assert (tmp_path/'host_fibers.vtk').exists()
    assert '*Nset, nset=XSYM' in text
    assert '100000' in text
    assert '*Embedded Element' in text
    assert progress[0][0] == 5
    assert progress[-1] == (100, 'Meshing complete')

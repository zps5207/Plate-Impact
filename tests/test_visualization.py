from embmesh.generate import mesh_flat

def test_visualization_outputs_and_symmetry(tmp_path):
    mesh_flat('examples/symmetry.inp', 'Q-1', .25, tmp_path, preview=False)
    text=(tmp_path/'output.inp').read_text()
    assert (tmp_path/'host_fibers.vtk').exists()
    assert '*Nset, nset=XSYM' in text
    assert '100000' in text
    assert '*Embedded Element' in text

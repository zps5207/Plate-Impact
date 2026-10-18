# Curved translation stack

`build_deck.py --no-fibers` reuses T-023's `load_base`, `stack_length`, and `stack`. The source has one curved top quad mesh and a bottom face. `stack_length` averages corresponding top to bottom node displacements and rejects a nontranslation. `stack` rebuilds eleven shared node planes at ten equal offsets along that vector, producing 24,000 C3D8R hosts. `make_one_element_deck.py` in T-023 had already rebuilt the source bottom as an exact translate. Its source-face mismatch was 76.42 μm maximum (4.53 μm mean, 15.99 μm 95th percentile); the accepted tolerance was 100 μm, or 10.64% of the median 0.940 mm in-plane edge. The rebuilt host faces differ only by floating-point roundoff.

## Geometric Path Construction
The fiber generation in `stacked_surface_fibers` projects reference face quads onto in-plane scanline axes. Each scanline is intersected with reference quad edges in a vectorized pass, and the height along the stack axis is linearly interpolated across each quad's traversed edge. Intervals across adjacent quads are joined into continuous fiber lines. Each line is inset at its endpoints until the projected clearance to the plate outline reaches $d/2 + \text{end\_inset}$, plus a tiny numerical boundary margin.

Crucially, in T-025/T-026, the resulting polyline of edge-crossing vertices is **not** converted directly into finite element nodes. Instead, it is treated strictly as a 3D **geometric path** lying on the faceted host surface.

## Even Resampling and Equal-Chord Correction
Earlier revisions (T-024) placed finite element nodes at every host element edge crossing and attempted a heuristic "merge" of short segments within 5% of a host edge. That approach left short segments (as low as 33.8 μm) and irregular segment lengths across the mesh.

The new implementation in `_resample_by_arclength` distributes nodes evenly along each fiber, matching the strategy used by `flat_disc_fibers`:

1. **Target length and segment count**:
   The total 3D arc length $L$ of the continuous geometric path is calculated from the cumulative Euclidean distance along its vertices. Using the standard host-matching rule:
   $$\text{target\_length} = \sqrt[3]{\text{median host volume}}$$
   the number of segments is determined as:
   $$n = \max(1, \text{round}(L / \text{target\_length}))$$
   This establishes $n + 1$ nodes per fiber. Within any given fiber, all segments have uniform length.

2. **The arc-length vs. chord-length conflict**:
   If stations were placed purely at equal cumulative arc length along the faceted polyline ($\Delta s = L/n$), any segment spanning across an element boundary or corner would bend in 3D. The straight Euclidean distance between the two truss endpoints (the truss chord length) across a bend is strictly smaller than the traversed arc length:
   $$\|\mathbf{p}_{i+1} - \mathbf{p}_i\| < s_{i+1} - s_i$$
   This causes segments that cross element boundaries to have slightly shorter chord lengths than segments lying entirely within a single flat facet. In explicit dynamics, the Courant condition and stable time increment depend on the minimum straight chord length of truss elements.

3. **Equal-chord relaxation loop**:
   To resolve this conflict without moving points off the physical surface, `_resample_by_arclength` employs an iterative correction loop (up to 12 iterations):
   - Linear interpolation samples candidate 3D points $\mathbf{p}_i$ along the geometric polyline at current arc-length stations $s_i$.
   - The straight chord lengths are evaluated: $c_i = \|\mathbf{p}_{i+1} - \mathbf{p}_i\|$.
   - Convergence is reached when the relative chord spread is below numerical tolerance:
     $$\frac{\max(c) - \min(c)}{\text{median}(c)} \le 10^{-10}$$
   - If not converged, the arc-length intervals are adjusted proportionally to the chord error:
     $$\Delta s_i^{\text{new}} = \Delta s_i + (\bar{c} - c_i)$$
     Segments with shorter chords (those crossing corners) receive larger arc-length allocations; segments with longer chords receive smaller arc allocations.
   - The updated intervals are accumulated into new stations $s_i = \sum \Delta s$ and normalized so that $s_n = L$.
   - New points are re-sampled on the polyline.
   - The first and last points are strictly clamped to the path endpoints: $\mathbf{p}_0 = \text{path}[0]$ and $\mathbf{p}_n = \text{path}[-1]$.

Because the plate surfaces are shallow ($\theta_{\text{max}} \approx 11.5^\circ$), the correction converges in 2 to 3 iterations, achieving a relative segment length spread $< 10^{-10}$ across all segments in the fiber. Every sampled point stays precisely on the surface polyline, guaranteeing host containment.

## Host Containment and World Frame
The Plate-1 instance in the assembly undergoes translation and rotation. `select_elements` transforms the host mesh into world assembly coordinates prior to fiber generation. All fiber calculations are performed directly in world coordinates, and the resulting `EMBFIB-1` instance is written with an identity transform (zero translation, zero rotation).

Independent audit scripts verify that every fiber node, segment midpoint, and multiple interior samples (5 points per segment, totaling over 100,000 sample points) lie strictly inside host C3D8R hex elements in world coordinates (0 points outside).

## Flat Equivalence
When a planar deck is provided (either zero surface slope or discrete regular planes such as Flatv2), `stacked_surface_fibers` detects planarity and routes execution directly through `flat_disc_fibers`. This guarantees byte-for-byte identity between `--curved stacked` and `--curved flat` outputs on planar decks.

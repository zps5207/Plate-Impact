"""Build reports/D6_PAPER_MATERIALS_VIDEO.html: d6 plate impact video (paper materials) with the material table, video embedded as base64."""
import base64, json
vid = base64.b64encode(open("reports/d6_rigid_matched_100us.mp4", "rb").read()).decode()
x = json.load(open("Meshing/vals-plywise-balltests3/results/d6_rigid_matched_100us_extract.json"))
c = x["status"][-1]["cnt"]
html = f"""<!doctype html><html><head><meta charset="utf-8"><title>d6 plate impact video</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;max-width:1000px;margin:24px auto;padding:0 16px;color:#222}}
video{{width:100%;border:1px solid #ccc}}table{{border-collapse:collapse;margin:8px 0}}td,th{{border:1px solid #ccc;padding:4px 10px;text-align:left}}
th{{background:#f0f0f0}}.n{{color:#555;font-size:.9em}}</style></head><body>
<h1>Plate impact d6: materials from Valerie's paper</h1>
<p>20-ply plywise laminate (25.4 mm), 1000 m/s ball, quarter model, run to 100 us (Abaqus/Explicit on ROAR, job 56873219, completed). Symmetry-plane view, plate grey, ball red, fibers not drawn, deleted host elements hidden. Left: wide view; right: plate close-up. The ball travels toward the left.</p>
<video controls autoplay loop muted playsinline src="data:video/mp4;base64,{vid}"></video>
<h2>Materials (paper Table 2 values, as in the deck)</h2>
<table><tr><th>Material</th><th>Density kg/m3</th><th>E / nu</th><th>Plasticity</th><th>Damage</th></tr>
<tr><td>Fiber</td><td>981</td><td>135 GPa / 0.45</td><td>yield 3.5 / 4.3 / 4.5 GPa at rate 0 / 1 / 1000 /s</td><td>ductile, fracture strain 0.0391 / 0.0251 / 0.01167 at 0.01 / 1 / 1000 /s; energy evolution 1 J/m2</td></tr>
<tr><td>Matrix</td><td>980</td><td>0.7 GPa / 0.45</td><td>yield 70 MPa</td><td>ductile, fracture strain 0.1 at 0.01 /s; energy evolution 1460 J/m2</td></tr>
<tr><td>Cohesive interface</td><td>-</td><td>stiffness 60 / 36 / 36 N/mm3</td><td>-</td><td>max stress 1.2 / 1.8 / 1.8 MPa; Gc 0.544 / 1.088 N/mm</td></tr>
<tr><td>Ball (steel)</td><td>7850</td><td>203 GPa / 0.33</td><td>rigid body, cannot deform or be deleted</td><td>-</td></tr></table>
<h2>Result at 100 us</h2>
<ul><li>Host elements deleted: {c['host'][1]} of {c['host'][0]}</li><li>Fiber elements deleted: {c['fiber'][1]} of {c['fiber'][0]}</li></ul>
<p class="n">The ball is rigid in this run (d5/d6), so ball deformation is not modelled. The paper's own deck is Meshing/Vals.inp; d6 differs from it in the points noted in the deck comments.</p>
</body></html>"""
open("reports/D6_PAPER_MATERIALS_VIDEO.html", "w", encoding="utf-8").write(html)
print("ok", len(html))

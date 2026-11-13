import json

with open('outbox/T-054/nv3_native_extract.json') as f:
    native_data = json.load(f)

with open('outbox/T-054/nv3_vuel_extract.json') as f:
    vuel_data = json.load(f)

print('Frame  Time (us)     Native ge99  VUEL ge99  Native max  VUEL max  Native ge50  VUEL ge50')
for i in range(0, 30, 2):
    n_cs = native_data['cs'][i]
    v_cs = vuel_data['cs'][i]
    t = n_cs['t'] * 1e6
    print(f"{i:5d}  {t:8.4f} us   {n_cs['ge99']:10d}  {v_cs['ge99']:9d}  {n_cs['max']:10.4f}  {v_cs['max']:8.4f}  {n_cs['ge50']:11d}  {v_cs['ge50']:10d}")

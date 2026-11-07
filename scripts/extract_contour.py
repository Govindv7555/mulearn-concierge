from PIL import Image
import numpy as np
import json

# Load mask
arr = np.array(Image.open('static/img/mulearn-glyph-mask.png'))
alpha = (arr[:, :, 3] > 128)
H, W = alpha.shape

# Boundary tracing (clockwise)
sy, sx = np.argwhere(alpha)[0]
dirs = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
contour = []
curr_p = (sy, sx)
back_dir = 6

while True:
    contour.append((float(curr_p[1]), float(curr_p[0]))) # x, y
    start_d = (back_dir + 1) % 8
    found = False
    for i in range(8):
        d_idx = (start_d + i) % 8
        dy, dx = dirs[d_idx]
        ny, nx = curr_p[0] + dy, curr_p[1] + dx
        if 0 <= ny < H and 0 <= nx < W and alpha[ny, nx]:
            curr_p = (ny, nx)
            back_dir = (d_idx + 4) % 8
            found = True
            break
    if not found or ((curr_p[0], curr_p[1]) == (sy, sx) and len(contour) > 2):
        break

# RDP simplification
def rdp(pts, epsilon):
    dmax = 0.0
    index = 0
    end = len(pts) - 1
    p1 = pts[0]
    p2 = pts[end]
    diff = p2 - p1
    norm = np.hypot(diff[0], diff[1])
    for i in range(1, end):
        if norm == 0:
            d = np.hypot(pts[i,0] - p1[0], pts[i,1] - p1[1])
        else:
            d = abs(diff[0] * (p1[1] - pts[i,1]) - diff[1] * (p1[0] - pts[i,0])) / norm
        if d > dmax:
            index = i
            dmax = d
    if dmax > epsilon:
        rec1 = rdp(pts[:index+1], epsilon)
        rec2 = rdp(pts[index:], epsilon)
        return np.vstack((rec1[:-1], rec2))
    else:
        return np.array([p1, p2])

pts = np.array(contour, dtype=float)
# Test eps = 2.0
simp = rdp(pts, 2.0)
print(f"Simplified contour: {len(simp)} points")

# Normalize: center bounding box at (0, 0), height = 1.26 m (50% of medallion diameter 2.52m)
min_x, max_x = simp[:, 0].min(), simp[:, 0].max()
min_y, max_y = simp[:, 1].min(), simp[:, 1].max()
cx = (min_x + max_x) / 2.0
cy = (min_y + max_y) / 2.0
h_px = max_y - min_y
scale = 1.26 / h_px

# In Three.js, Y goes up, in image Y goes down, so flip Y:
norm_pts = []
for p in simp:
    nx = (p[0] - cx) * scale
    ny = (cy - p[1]) * scale # flip Y
    norm_pts.append([round(nx, 4), round(ny, 4)])

with open('static/glyph_contour_points.json', 'w') as f:
    json.dump(norm_pts, f)

print(f"Saved {len(norm_pts)} normalized points to static/glyph_contour_points.json")


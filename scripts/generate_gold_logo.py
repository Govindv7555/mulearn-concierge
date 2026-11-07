from PIL import Image
import numpy as np

# Load mask
mask_img = Image.open('static/img/mulearn-glyph-mask.png')
w, h = mask_img.size
mask_arr = np.array(mask_img)[:, :, 3].astype(float) / 255.0

# 1. Diagonal gradient: top-left (0, 0) to bottom-right (w-1, h-1)
# Normalized diagonal coordinate from 0.0 to 1.0
Y, X = np.ogrid[:h, :w]
diag = (X / float(w) + Y / float(h)) / 2.0 # 0.0 at top-left, 1.0 at bottom-right

# Color stops:
# 0.00: #FFF2D6 (champagne shimmer)
# 0.15: #E8D5A3 (light champagne)
# 0.50: #D8B266 (radiant gold)
# 0.85: #9C7A3A (deep gold)
# 1.00: #826026 (amber gold)
stops = [
    (0.00, np.array([255, 242, 214], dtype=float)),
    (0.15, np.array([232, 213, 163], dtype=float)),
    (0.50, np.array([216, 178, 102], dtype=float)),
    (0.85, np.array([156, 122, 58], dtype=float)),
    (1.00, np.array([130, 96, 38], dtype=float))
]

rgb = np.zeros((h, w, 3), dtype=float)
for i in range(len(stops) - 1):
    t0, c0 = stops[i]
    t1, c1 = stops[i + 1]
    seg = (diag >= t0) & (diag <= t1)
    factor = (diag - t0) / (t1 - t0)
    # Smooth Hermite interpolation
    smooth_f = factor * factor * (3.0 - 2.0 * factor)
    for c in range(3):
        rgb[seg, c] = c0[c] + (c1[c] - c0[c]) * smooth_f[seg]

# 2. Soft Edge Highlights & Shading via Sobel gradient of alpha mask
gy, gx = np.gradient(mask_arr)
# Light vector from top-left (-1, -1) normalized
lx, ly = -0.7071, -0.7071
# Edge normal is (-gx, -gy)
edge_light = -(gx * lx + gy * ly)
edge_highlight = np.clip(edge_light * 8.0, -0.25, 0.35)

# Apply edge highlight
for c in range(3):
    rgb[:, :, c] = np.clip(rgb[:, :, c] * (1.0 + edge_highlight), 0.0, 255.0)

# 3. Create RGBA image
out = np.zeros((h, w, 4), dtype=np.uint8)
out[:, :, :3] = np.round(rgb).astype(np.uint8)
out[:, :, 3] = np.round(mask_arr * 255.0).astype(np.uint8)

res_img = Image.fromarray(out, mode='RGBA')
res_img.save('static/img/mulearn-logo.png', format='PNG', optimize=True)
print(f"Saved static/img/mulearn-logo.png successfully! Size: {res_img.size}")


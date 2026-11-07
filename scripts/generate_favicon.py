import json

pts = json.load(open('static/glyph_contour_points.json'))
# pts are [x, y] in metres: x in [-0.495, 0.495], y in [-0.63, 0.63]
# We want to map to SVG 64x64 box
# glyph height in SVG ~ 38px
# scale = 38.0 / 1.26 = 30.1587
# center at (32, 32)
# In SVG, Y goes down, so svg_y = 32 - y * scale, svg_x = 32 + x * scale

scale = 36.0 / 1.26
svg_pts = []
for p in pts:
    sx = round(32.0 + p[0] * scale, 2)
    sy = round(32.0 - p[1] * scale, 2)
    svg_pts.append((sx, sy))

d_str = f"M {svg_pts[0][0]} {svg_pts[0][1]} " + " ".join(f"L {p[0]} {p[1]}" for p in svg_pts[1:]) + " Z"

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="favGold" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#E8D5A3"/>
      <stop offset="50%" stop-color="#D4AF65"/>
      <stop offset="100%" stop-color="#9C7A3A"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="#070B16"/>
  <path d="{d_str}" fill="url(#favGold)"/>
</svg>'''

with open('static/img/favicon.svg', 'w', encoding='utf-8') as f:
    f.write(svg_content)

print("Saved static/img/favicon.svg with new exact glyph shape!")


import json

pts = json.load(open('static/glyph_contour_points.json'))
# glyph height in 512x512 SVG ~ 270px
scale = 270.0 / 1.26
svg_pts = []
for p in pts:
    sx = round(256.0 + p[0] * scale, 2)
    sy = round(256.0 - p[1] * scale, 2)
    svg_pts.append((sx, sy))

d_str = f"M {svg_pts[0][0]} {svg_pts[0][1]} " + " ".join(f"L {p[0]} {p[1]}" for p in svg_pts[1:]) + " Z"

svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <linearGradient id="champagneGold" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFF5DC"/>
      <stop offset="15%" stop-color="#E8D5A3"/>
      <stop offset="50%" stop-color="#D4AF65"/>
      <stop offset="85%" stop-color="#9C7A3A"/>
      <stop offset="100%" stop-color="#84622A"/>
    </linearGradient>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#EED59B" stop-opacity="0.8"/>
      <stop offset="50%" stop-color="#C9A96E" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#8C662D" stop-opacity="0.8"/>
    </linearGradient>
    <radialGradient id="auraGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#C9A96E" stop-opacity="0.35"/>
      <stop offset="60%" stop-color="#C9A96E" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="#070B16" stop-opacity="0"/>
    </radialGradient>
    <filter id="goldDropShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#C9A96E" flood-opacity="0.35"/>
    </filter>
  </defs>

  <!-- Aura Glow -->
  <circle cx="256" cy="256" r="220" fill="url(#auraGlow)"/>

  <!-- Orbital Accent Rings -->
  <circle cx="256" cy="256" r="200" fill="none" stroke="url(#ringGrad)" stroke-width="2" stroke-dasharray="8 12" opacity="0.6"/>
  <circle cx="256" cy="256" r="185" fill="none" stroke="url(#champagneGold)" stroke-width="1.5" opacity="0.4"/>

  <!-- Core µ Monogram -->
  <g filter="url(#goldDropShadow)">
    <path d="{d_str}" fill="url(#champagneGold)"/>
  </g>
</svg>'''

with open('static/img/mulearn-logo.svg', 'w', encoding='utf-8') as f:
    f.write(svg_content)

print("Saved static/img/mulearn-logo.svg with new exact glyph shape!")


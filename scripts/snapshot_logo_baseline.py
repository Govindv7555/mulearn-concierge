import json
import os

baseline = {
    "timeline": {
        "duration": 88,
        "spacer_vh": 628,
        "labels": {
            "hero": 0,
            "rotationStart": 0,
            "approachStart": 0,
            "liftStart": 10.8,
            "rotationEnd": 18,
            "liftEnd": 18,
            "phase3Start": 18,
            "swirlStart": 18,
            "phase3End": 50,
            "phase4Start": 50,
            "phase4End": 66,
            "phase5Start": 66,
            "screenZoomEnd": 77,
            "phase5End": 77,
            "swapThreshold": 80,
            "end": 88
        }
    },
    "medallion": {
        "radius": 1.26,
        "thickness": 0.014
    },
    "orbit_rings": {
        "inner_radius": 1.50,
        "outer_radius": 1.68
    },
    "spark": {
        "position": [0.68, 0.72, 0.15]
    }
}

with open('static/logo_glyph_baseline_snapshot.json', 'w') as f:
    json.dump(baseline, f, indent=2)

print("Saved static/logo_glyph_baseline_snapshot.json")


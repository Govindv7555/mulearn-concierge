import json

snapshot = {
    "colors_and_fonts": {
        "midnight": "#070B16",
        "glass": "rgba(13, 27, 42, 0.75)",
        "gold": "#C9A96E",
        "ivory": "#F5F0E8",
        "blue": "#4A7C9B"
    },
    "timeline": {
        "duration": 88.0,
        "labels": {
            "hero": 0,
            "approachStart": 0,
            "rotationStart": 0,
            "liftStart": 10.8,
            "dissolveComplete": 18,
            "phase3Start": 18,
            "phase4Start": 50,
            "phase5Start": 66,
            "screenZoomEnd": 77,
            "swapThreshold": 80
        }
    },
    "welcome_bubble": {
        "font_size": "16.5px",
        "line_height": "1.65",
        "max_width": "78%"
    }
}

with open('scripts/layout_freeze_baseline.json', 'w', encoding='utf-8') as f:
    json.dump(snapshot, f, indent=2)

print("Saved snapshot to scripts/layout_freeze_baseline.json")


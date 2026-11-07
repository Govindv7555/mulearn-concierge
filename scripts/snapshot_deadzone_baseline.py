import json
import os

baseline = {
    "viewport_height_ref": 900,
    "old_spacer_height_vh": 700,
    "old_scroll_distance_vh": 600,
    "old_scroll_distance_px": 5400,
    "old_timeline_duration": 100,
    "px_per_timeline_unit": 54.0,
    "removed_span_units": 12,
    "removed_span_vh": 72.0,
    "removed_span_px": 648.0,
    "expected_new_spacer_vh": 628.0,
    "expected_new_scroll_distance_vh": 528.0,
    "expected_new_scroll_distance_px": 4752.0,
    "expected_new_timeline_duration": 88.0,
    "tweens": [
        {
            "id": "approach_cam",
            "old_start": 12,
            "duration_units": 18,
            "duration_vh": 108.0,
            "duration_px": 972.0,
            "ease": "power2.inOut",
            "target": {"x": 0, "y": 0.25, "z": 3.6, "targetX": 0, "targetY": 0, "targetZ": 0}
        },
        {
            "id": "logo_rotation",
            "old_start": 12,
            "duration_units": 18,
            "duration_vh": 108.0,
            "duration_px": 972.0,
            "ease": "power2.inOut",
            "target_y": -1.6336281798666924  # -Math.PI * 0.52
        },
        {
            "id": "logo_scale",
            "old_start": 12,
            "duration_units": 18,
            "duration_vh": 108.0,
            "duration_px": 972.0,
            "ease": "power2.inOut",
            "target": {"x": 1.25, "y": 1.25, "z": 1.25}
        },
        {
            "id": "lift_wave",
            "old_start": 22.8,
            "duration_units": 7.2,
            "duration_vh": 43.2,
            "duration_px": 388.8,
            "ease": "none",
            "target_value": 1.0
        },
        {
            "id": "phase3_morph",
            "old_start": 30,
            "duration_units": 32,
            "duration_vh": 192.0,
            "duration_px": 1728.0,
            "ease": "none",
            "target_p": 1.0
        },
        {
            "id": "phase3_cam",
            "old_start": 30,
            "duration_units": 32,
            "duration_vh": 192.0,
            "duration_px": 1728.0,
            "ease": "power2.inOut",
            "target": {"x": -0.12, "y": 1.25, "z": 1.62, "targetX": 0.06, "targetY": 0.88, "targetZ": -0.05}
        },
        {
            "id": "phase4_cam",
            "old_start": 62,
            "duration_units": 16,
            "duration_vh": 96.0,
            "duration_px": 864.0,
            "ease": "power2.inOut",
            "target_name": "screenTargets.phase4"
        },
        {
            "id": "phase5_cam",
            "old_start": 78,
            "duration_units": 11,
            "duration_vh": 66.0,
            "duration_px": 594.0,
            "ease": "power2.inOut",
            "target_name": "screenTargets.phase5"
        },
        {
            "id": "screen_fade_mesh",
            "old_start": 90.64,
            "duration_units": 1.36,
            "duration_vh": 8.16,
            "duration_px": 73.44,
            "ease": "power2.in",
            "target_opacity": 1.0
        }
    ]
}

os.makedirs('static', exist_ok=True)
with open('static/scroll_deadzone_baseline_snapshot.json', 'w', encoding='utf-8') as f:
    json.dump(baseline, f, indent=2)

print("Saved baseline snapshot to static/scroll_deadzone_baseline_snapshot.json")


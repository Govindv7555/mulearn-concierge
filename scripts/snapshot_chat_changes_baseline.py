import json
import os

baseline = {
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
            "phase5Start": 68,
            "screenZoomEnd": 77,
            "swapThreshold": 80
        },
        "phase1_duration": 3.7,
        "phase2_approach_cam_duration": 18.0,
        "phase2_logo_rotation_duration": 18.0,
        "phase2_logo_lift_duration": 7.2,
        "phase3_particle_morph_duration": 32.0,
        "phase4_laptop_approach_duration": 18.0,
        "phase5_screen_zoom_duration": 9.0
    },
    "swap_to_chat": {
        "fade_in": 0.8,
        "hold": 0.6,
        "swap_point": 1.1,
        "fade_out": 1.0,
        "total": 2.4
    },
    "swap_to_scene_replay": {
        "fade_in": 0.8,
        "hold": 0.6,
        "restore_point": 1.1,
        "fade_out": 1.0,
        "total": 2.4,
        "replay_label_offset": 1.0,
        "replay_position": 78.0
    }
}

out_path = os.path.join(os.path.dirname(__file__), "chat_changes_baseline.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(baseline, f, indent=2)

print("Saved baseline to", out_path)


# =============================================================================
#  IgnisGuard - Fire & PPE safety detection
#  Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
#  Author: Perarasu Boopathirajan
#  Unauthorized copying, redistribution or claiming authorship of this file,
#  via any medium, is prohibited without written permission. See LICENSE.
# =============================================================================
"""Central settings for IgnisGuard."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# IGNIS_DATA lets a host point storage at a persistent disk (e.g. /data on Hugging Face Spaces)
DATA_DIR = Path(os.environ.get("IGNIS_DATA") or ROOT / "data")
DATASET_DIR = DATA_DIR / "dataset"          # YOLO-format dataset built from the UI
MODELS_DIR = DATA_DIR / "models"            # trained model versions
RUNS_DIR = DATA_DIR / "runs"                # raw ultralytics training output
ACTIVE_MODEL_FILE = MODELS_DIR / "active.txt"

# Classes you label in the Training tab. Order matters (class id = index).
CLASSES = [
    "fire",            # 0 flames
    "smoke",           # 1 smoke
    "person",          # 2 a worker / firefighter
    "helmet",          # 3 a helmet being worn
    "no_helmet",       # 4 a bare head (no helmet)
    "fire_jacket",     # 5 a fire / safety jacket being worn
    "no_fire_jacket",  # 6 a torso without a fire jacket
]

# Colours (BGR) used when drawing boxes
COLORS = {
    "fire": (0, 69, 255), "smoke": (160, 160, 160), "person": (255, 180, 0),
    "helmet": (80, 200, 60), "no_helmet": (40, 40, 230),
    "fire_jacket": (60, 200, 200), "no_fire_jacket": (180, 40, 220),
}

# Which detections count as alerts
ALERT_CLASSES = {"fire": "FIRE", "smoke": "SMOKE",
                 "no_helmet": "NO HELMET", "no_fire_jacket": "NO FIRE JACKET"}

# Zero-shot starter model (used until you train your own). Open-vocabulary YOLO-World.
STARTER_MODEL = "yolov8s-worldv2.pt"
STARTER_PROMPTS = {
    "fire": ["fire", "flame"],
    "smoke": ["smoke"],
    "person": ["person"],
    "helmet": ["helmet", "hard hat", "firefighter helmet"],
    "fire_jacket": ["firefighter jacket", "high visibility safety vest", "reflective jacket"],
}

AUTHOR = "Perarasu Boopathirajan"

API_KEY = os.environ.get("IGNIS_API_KEY", "").strip()          # access key (strongly recommended online)
CORS_ORIGINS = [o.strip() for o in os.environ.get("IGNIS_CORS_ORIGINS", "*").split(",") if o.strip()]

# Upload limits (MB)
MAX_IMAGE_MB = int(os.environ.get("IGNIS_MAX_IMAGE_MB", "25"))
MAX_ZIP_MB = int(os.environ.get("IGNIS_MAX_ZIP_MB", "500"))
MAX_MODEL_MB = int(os.environ.get("IGNIS_MAX_MODEL_MB", "300"))
MAX_ZIP_FILES = 20000                     # zip-bomb guard for dataset import
MAX_ZIP_UNPACKED_MB = 4000

for d in (DATASET_DIR, MODELS_DIR, RUNS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# =============================================================================
#  IgnisGuard - Fire & PPE safety detection
#  Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
#  Author: Perarasu Boopathirajan
#  Unauthorized copying, redistribution or claiming authorship of this file,
#  via any medium, is prohibited without written permission. See LICENSE.
# =============================================================================
"""Model loading, inference and safety-rule logic."""
import threading
from pathlib import Path

import cv2
import numpy as np

from . import config as C


def _iou_inside(inner, outer):
    """Fraction of `inner` box area that lies inside `outer`."""
    x1, y1 = max(inner[0], outer[0]), max(inner[1], outer[1])
    x2, y2 = min(inner[2], outer[2]), min(inner[3], outer[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area = max(1e-6, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return inter / area


class Detector:
    def __init__(self):
        self.lock = threading.Lock()
        self.model = None
        self.model_name = None
        self.mode = None          # "custom" | "starter" | None
        self.error = None
        self.load_active()

    # ---------- loading ----------
    def load_active(self):
        from ultralytics import YOLO
        with self.lock:
            self.error = None
            active = None
            if C.ACTIVE_MODEL_FILE.exists():
                name = C.ACTIVE_MODEL_FILE.read_text().strip()
                if (C.MODELS_DIR / name).exists():
                    active = C.MODELS_DIR / name
            if active:
                try:
                    self.model = YOLO(str(active))
                    self.model_name, self.mode = active.name, "custom"
                    return
                except Exception as e:  # noqa
                    self.error = f"Could not load {active.name}: {e}"
            # fall back to zero-shot starter model
            try:
                from ultralytics import YOLOWorld
                m = YOLOWorld(C.STARTER_MODEL)
                self._prompt_map = []
                prompts = []
                for cls, words in C.STARTER_PROMPTS.items():
                    for w in words:
                        prompts.append(w)
                        self._prompt_map.append(cls)
                m.set_classes(prompts)
                self.model, self.model_name, self.mode = m, "Starter (YOLO-World, zero-shot)", "starter"
            except Exception as e:  # noqa
                self.model, self.model_name, self.mode = None, None, None
                self.error = ("No trained model yet and the starter model could not be "
                              f"downloaded ({e.__class__.__name__}). Train a model in the Training tab.")

    def set_active(self, name):
        C.ACTIVE_MODEL_FILE.write_text(name)
        self.load_active()

    def info(self):
        return {"model": self.model_name, "mode": self.mode, "error": self.error}

    # ---------- inference ----------
    def analyze(self, img_bgr, conf=0.35, check_helmet=True, check_jacket=True, check_fire=True):
        with self.lock:
            if self.model is None:
                raise RuntimeError(self.error or "No model loaded")
            res = self.model.predict(img_bgr, conf=conf, verbose=False)[0]
            names = res.names
            dets = []
            for b in res.boxes:
                cid = int(b.cls)
                label = self._prompt_map[cid] if self.mode == "starter" else names[cid]
                dets.append({"label": label, "conf": round(float(b.conf), 3),
                             "box": [round(float(v), 1) for v in b.xyxy[0].tolist()]})

        dets = self._apply_rules(dets, check_helmet, check_jacket)

        enabled = set()
        if check_fire: enabled |= {"fire", "smoke"}
        if check_helmet: enabled.add("no_helmet")
        if check_jacket: enabled.add("no_fire_jacket")
        dets = [d for d in dets if d["label"] not in C.ALERT_CLASSES or d["label"] in enabled]

        alerts = {}
        for d in dets:
            if d["label"] in C.ALERT_CLASSES:
                k = C.ALERT_CLASSES[d["label"]]
                alerts[k] = alerts.get(k, 0) + 1
        people = sum(1 for d in dets if d["label"] == "person")
        return dets, alerts, people, self._draw(img_bgr, dets)

    def _apply_rules(self, dets, check_helmet, check_jacket):
        """A person with no helmet / jacket overlapping them becomes a violation."""
        persons = [d for d in dets if d["label"] == "person"]
        helmets = [d for d in dets if d["label"] == "helmet"]
        jackets = [d for d in dets if d["label"] == "fire_jacket"]
        no_h = [d for d in dets if d["label"] == "no_helmet"]
        no_j = [d for d in dets if d["label"] == "no_fire_jacket"]
        extra = []
        for p in persons:
            x1, y1, x2, y2 = p["box"]
            h = y2 - y1
            head = [x1, y1, x2, y1 + 0.3 * h]
            torso = [x1, y1 + 0.15 * h, x2, y1 + 0.75 * h]
            if check_helmet:
                has = any(_iou_inside(hm["box"], head) > 0.4 for hm in helmets)
                flagged = any(_iou_inside(n["box"], p["box"]) > 0.5 for n in no_h)
                if not has and not flagged:
                    extra.append({"label": "no_helmet", "conf": p["conf"], "box": [round(v, 1) for v in head],
                                  "derived": True})
            if check_jacket:
                has = any(_iou_inside(jk["box"], torso) > 0.3 for jk in jackets)
                flagged = any(_iou_inside(n["box"], p["box"]) > 0.5 for n in no_j)
                if not has and not flagged:
                    extra.append({"label": "no_fire_jacket", "conf": p["conf"],
                                  "box": [round(v, 1) for v in torso], "derived": True})
        return dets + extra

    @staticmethod
    def _draw(img, dets):
        out = img.copy()
        t = max(2, int(round(min(out.shape[:2]) / 300)))
        fs = max(0.5, min(out.shape[:2]) / 900)
        for d in dets:
            x1, y1, x2, y2 = map(int, d["box"])
            col = C.COLORS.get(d["label"], (255, 255, 255))
            cv2.rectangle(out, (x1, y1), (x2, y2), col, t)
            txt = f'{d["label"].replace("_", " ").upper()} {d["conf"]:.2f}'
            (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, fs, 1)
            yb = max(th + 6, y1)
            cv2.rectangle(out, (x1, yb - th - 6), (x1 + tw + 6, yb), col, -1)
            cv2.putText(out, txt, (x1 + 3, yb - 4), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), 1, cv2.LINE_AA)
        return out


def decode_image(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Unsupported or corrupt image")
    return img

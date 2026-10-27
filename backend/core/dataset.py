# =============================================================================
#  IgnisGuard - Fire & PPE safety detection
#  Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
#  Author: Perarasu Boopathirajan
#  Unauthorized copying, redistribution or claiming authorship of this file,
#  via any medium, is prohibited without written permission. See LICENSE.
# =============================================================================
"""Dataset store: uploaded images + box annotations, exported to YOLO format for training."""
import io
import json
import random
import shutil
import threading
import uuid
import zipfile
from pathlib import Path

import cv2
import numpy as np
import yaml

from . import config as C

POOL = C.DATASET_DIR / "pool"
META = C.DATASET_DIR / "meta.json"
EXPORT = C.DATASET_DIR / "yolo"
POOL.mkdir(parents=True, exist_ok=True)
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Common class names from public datasets (Roboflow etc.) -> IgnisGuard classes
ALIASES = {
    "fire": "fire", "flame": "fire", "flames": "fire",
    "smoke": "smoke",
    "person": "person", "worker": "person", "firefighter": "person", "people": "person",
    "helmet": "helmet", "hardhat": "helmet", "hard-hat": "helmet", "hard_hat": "helmet", "hat": "helmet",
    "no_helmet": "no_helmet", "no-helmet": "no_helmet", "nohelmet": "no_helmet", "head": "no_helmet",
    "no-hardhat": "no_helmet", "no_hardhat": "no_helmet", "without_helmet": "no_helmet",
    "fire_jacket": "fire_jacket", "jacket": "fire_jacket", "vest": "fire_jacket",
    "safety vest": "fire_jacket", "safety_vest": "fire_jacket", "safety-vest": "fire_jacket",
    "no_fire_jacket": "no_fire_jacket", "no-jacket": "no_fire_jacket", "no_jacket": "no_fire_jacket",
    "no-safety vest": "no_fire_jacket", "no_safety_vest": "no_fire_jacket", "no-vest": "no_fire_jacket",
}


class Dataset:
    def __init__(self):
        self.lock = threading.Lock()
        self.meta = json.loads(META.read_text()) if META.exists() else {}

    def _save(self):
        META.write_text(json.dumps(self.meta, indent=1))

    # ---------- items ----------
    def add_image(self, filename, data: bytes, boxes=None, status="unlabeled"):
        img = cv2.imdecode(np.frombuffer(data, "uint8"), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError(f"{filename}: not a valid image")
        iid = uuid.uuid4().hex[:12]
        ext = Path(filename).suffix.lower()
        if ext not in IMG_EXT:
            ext = ".jpg"
        (POOL / f"{iid}{ext}").write_bytes(data)
        h, w = img.shape[:2]
        item = {"id": iid, "file": f"{iid}{ext}", "name": Path(filename.replace("\\", "/")).name[:150], "w": w, "h": h,
                "boxes": boxes or [], "status": "labeled" if boxes else status,
                "split": "val" if random.random() < 0.2 else "train"}
        with self.lock:
            self.meta[iid] = item
            self._save()
        return item

    def list(self):
        return sorted(self.meta.values(), key=lambda x: x["id"])

    def get(self, iid):
        return self.meta.get(iid)

    def path(self, iid):
        return POOL / self.meta[iid]["file"]

    def set_boxes(self, iid, boxes, background=False):
        """boxes: [{cls: name, x1,y1,x2,y2}] in pixel coords."""
        with self.lock:
            it = self.meta[iid]
            clean = []
            for b in boxes[:500]:
                if not isinstance(b, dict) or b.get("cls") not in C.CLASSES:
                    continue
                bx = [float(b[k]) for k in ("x1", "y1", "x2", "y2")]   # ValueError/KeyError -> 400
                if not all(np.isfinite(bx)):
                    continue
                x1, x2 = sorted([max(0, min(it["w"], bx[0])), max(0, min(it["w"], bx[2]))])
                y1, y2 = sorted([max(0, min(it["h"], bx[1])), max(0, min(it["h"], bx[3]))])
                if x2 - x1 >= 2 and y2 - y1 >= 2:
                    clean.append({"cls": b["cls"], "x1": x1, "y1": y1, "x2": x2, "y2": y2})
            it["boxes"] = clean
            it["status"] = "labeled" if clean else ("background" if background else "unlabeled")
            self._save()
            return it

    def delete(self, iid):
        with self.lock:
            it = self.meta.pop(iid, None)
            if it:
                (POOL / it["file"]).unlink(missing_ok=True)
                self._save()

    def stats(self):
        counts = {c: 0 for c in C.CLASSES}
        st = {"total": len(self.meta), "labeled": 0, "unlabeled": 0, "background": 0}
        for it in self.meta.values():
            st[it["status"]] += 1
            for b in it["boxes"]:
                counts[b["cls"]] = counts.get(b["cls"], 0) + 1
        st["per_class"] = counts
        return st

    # ---------- import a ready-labelled YOLO zip ----------
    def import_yolo_zip(self, data: bytes):
        zf = zipfile.ZipFile(io.BytesIO(data))
        infos = zf.infolist()
        # zip-bomb guard: refuse archives that unpack to something enormous
        if len(infos) > C.MAX_ZIP_FILES:
            raise ValueError(f"too many files in zip (max {C.MAX_ZIP_FILES})")
        if sum(i.file_size for i in infos) > C.MAX_ZIP_UNPACKED_MB * 1024 * 1024:
            raise ValueError(f"zip unpacks to more than {C.MAX_ZIP_UNPACKED_MB} MB")
        names = zf.namelist()
        # class names from data.yaml if present
        src_names = None
        for n in names:
            if n.lower().endswith(("data.yaml", "data.yml")):
                y = yaml.safe_load(zf.read(n)) or {}
                nm = y.get("names") if isinstance(y, dict) else None
                src_names = list(nm.values()) if isinstance(nm, dict) else nm
                break
        if src_names is None:
            src_names = C.CLASSES
        cmap = {}
        for i, n in enumerate(src_names):
            key = str(n).strip().lower()
            if key in ALIASES:
                cmap[i] = ALIASES[key]
        label_files = {n: n for n in names if n.lower().endswith(".txt")}
        added, skipped = 0, 0
        for n in names:
            if Path(n).suffix.lower() not in IMG_EXT or n.endswith("/"):
                continue
            p = Path(n)
            parts = list(p.parts)
            lbl = None
            # images/.../x.jpg -> labels/.../x.txt
            if "images" in parts:
                idx = len(parts) - 1 - parts[::-1].index("images")
                parts2 = parts[:idx] + ["labels"] + parts[idx + 1:]
                lbl = str(Path(*parts2).with_suffix(".txt")).replace("\\", "/")
            cand = [lbl, str(p.with_suffix(".txt")).replace("\\", "/")]
            lbl_name = next((c for c in cand if c and c in label_files), None)
            img_bytes = zf.read(n)
            img = cv2.imdecode(np.frombuffer(img_bytes, "uint8"), cv2.IMREAD_COLOR)
            if img is None:
                skipped += 1
                continue
            h, w = img.shape[:2]
            boxes = []
            if lbl_name:
                for line in zf.read(lbl_name).decode(errors="ignore").splitlines():
                    v = line.split()
                    if len(v) < 5:
                        continue
                    try:  # one malformed line shouldn't abort the whole import
                        ci = int(float(v[0]))
                        coords = list(map(float, v[1:]))
                    except ValueError:
                        continue
                    if ci not in cmap or (len(coords) > 4 and len(coords) % 2):
                        continue
                    if len(coords) > 4:  # polygon -> bbox
                        xs, ys = coords[0::2], coords[1::2]
                        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
                        bw, bh = max(xs) - min(xs), max(ys) - min(ys)
                    else:
                        cx, cy, bw, bh = coords
                    boxes.append({"cls": cmap[ci], "x1": (cx - bw / 2) * w, "y1": (cy - bh / 2) * h,
                                  "x2": (cx + bw / 2) * w, "y2": (cy + bh / 2) * h})
            it = self.add_image(p.name, img_bytes, status="background" if lbl_name else "unlabeled")
            if boxes:
                self.set_boxes(it["id"], boxes)
            added += 1
        return {"added": added, "skipped": skipped,
                "class_mapping": {str(src_names[k])[:60]: v for k, v in cmap.items()}}

    # ---------- export to YOLO folder ----------
    def export(self):
        with self.lock:
            items = [i for i in self.meta.values() if i["status"] in ("labeled", "background")]
            if sum(1 for i in items if i["status"] == "labeled") < 2:
                raise ValueError("Label at least 2 images before training (10+ per class recommended).")
            shutil.rmtree(EXPORT, ignore_errors=True)
            for s in ("train", "val"):
                (EXPORT / "images" / s).mkdir(parents=True)
                (EXPORT / "labels" / s).mkdir(parents=True)
            vals = [i for i in items if i["split"] == "val"]
            if not vals:  # guarantee a validation set
                vals = items[:max(1, len(items) // 5)]
            val_ids = {i["id"] for i in vals}
            for it in items:
                split = "val" if it["id"] in val_ids else "train"
                shutil.copy(POOL / it["file"], EXPORT / "images" / split / it["file"])
                lines = []
                for b in it["boxes"]:
                    cx = (b["x1"] + b["x2"]) / 2 / it["w"]
                    cy = (b["y1"] + b["y2"]) / 2 / it["h"]
                    bw = (b["x2"] - b["x1"]) / it["w"]
                    bh = (b["y2"] - b["y1"]) / it["h"]
                    lines.append(f"{C.CLASSES.index(b['cls'])} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
                (EXPORT / "labels" / split / (Path(it["file"]).stem + ".txt")).write_text("\n".join(lines))
            # if every item went to val, train on them too
            if not any((EXPORT / "images" / "train").iterdir()):
                for f in (EXPORT / "images" / "val").iterdir():
                    shutil.copy(f, EXPORT / "images" / "train" / f.name)
                for f in (EXPORT / "labels" / "val").iterdir():
                    shutil.copy(f, EXPORT / "labels" / "train" / f.name)
            yml = EXPORT / "data.yaml"
            yml.write_text(yaml.safe_dump({"path": str(EXPORT), "train": "images/train", "val": "images/val",
                                           "names": {i: n for i, n in enumerate(C.CLASSES)}}))
            return yml

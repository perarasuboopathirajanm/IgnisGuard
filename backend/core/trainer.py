# =============================================================================
#  IgnisGuard - Fire & PPE safety detection
#  Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
#  Author: Perarasu Boopathirajan
#  Unauthorized copying, redistribution or claiming authorship of this file,
#  via any medium, is prohibited without written permission. See LICENSE.
# =============================================================================
"""Background training job with live progress."""
import shutil
import threading
import time
import traceback
from datetime import datetime

from . import config as C


class Trainer:
    def __init__(self, dataset, detector):
        self.ds, self.det = dataset, detector
        self.thread = None
        self._stop = False
        self.state = {"status": "idle", "epoch": 0, "epochs": 0, "batch": 0, "batches": 0,
                      "history": [], "message": "", "model": None, "started": None}

    def running(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, epochs=50, imgsz=640, base="yolo11n", batch=8, device="auto"):
        if self.running():
            raise RuntimeError("Training already running")
        yml = self.ds.export()
        self._stop = False
        self.state = {"status": "starting", "epoch": 0, "epochs": epochs, "batch": 0, "batches": 0,
                      "history": [], "message": "Preparing…", "model": None, "started": time.time()}
        self.thread = threading.Thread(target=self._run, args=(yml, epochs, imgsz, base, batch, device),
                                       daemon=True)
        self.thread.start()

    def stop(self):
        self._stop = True
        self.state["message"] = "Stopping after current batch…"

    def _run(self, yml, epochs, imgsz, base, batch, device):
        from ultralytics import YOLO
        try:
            try:
                model = YOLO(f"{base}.pt")          # pretrained (needs internet first time)
                self.state["message"] = f"Fine-tuning pretrained {base}"
            except Exception:
                model = YOLO(f"{base}.yaml")        # offline fallback: from scratch
                self.state["message"] = f"Training {base} from scratch (pretrained weights unavailable)"

            def on_batch(tr):
                self.state["batch"] += 1
                self.state["batches"] = len(tr.train_loader)
                self.state["status"] = "training"
                if self._stop:
                    tr.stop = True

            def on_epoch_start(tr):
                self.state["batch"] = 0

            def on_fit_epoch(tr):
                m = tr.metrics or {}
                loss = tr.tloss
                if isinstance(loss, dict):
                    loss = sum(float(v) for v in loss.values())
                elif loss is not None:
                    loss = float(loss.sum())
                ep = min(tr.epoch + 1, self.state["epochs"])
                self.state["epoch"] = ep
                hist = self.state["history"]
                if hist and hist[-1]["epoch"] >= ep:   # final validation pass: update, don't add
                    hist.pop()
                hist.append({
                    "epoch": ep,
                    "loss": round(loss, 4) if loss is not None else None,
                    "mAP50": round(float(m.get("metrics/mAP50(B)", 0)), 4),
                    "precision": round(float(m.get("metrics/precision(B)", 0)), 4),
                    "recall": round(float(m.get("metrics/recall(B)", 0)), 4),
                })

            model.add_callback("on_train_batch_end", on_batch)
            model.add_callback("on_train_epoch_start", on_epoch_start)
            model.add_callback("on_fit_epoch_end", on_fit_epoch)

            dev = None if device == "auto" else device
            name = datetime.now().strftime("ignisguard_%Y%m%d_%H%M%S")
            model.train(data=str(yml), epochs=epochs, imgsz=imgsz, batch=batch, device=dev,
                        project=str(C.RUNS_DIR), name=name, exist_ok=True, workers=0,
                        patience=max(10, epochs // 3), plots=False, verbose=False)

            best = C.RUNS_DIR / name / "weights" / "best.pt"
            if not best.exists():
                best = C.RUNS_DIR / name / "weights" / "last.pt"
            if not best.exists():
                raise RuntimeError("Training finished but no weights were saved.")
            dst = C.MODELS_DIR / f"{name}.pt"
            shutil.copy(best, dst)
            self.det.set_active(dst.name)
            self.state.update(status="done", model=dst.name,
                              message=("Stopped early — " if self._stop else "") +
                                      f"Model saved as {dst.name} and activated for Analysis.")
        except Exception as e:  # noqa
            traceback.print_exc()
            self.state.update(status="error", message=f"{e.__class__.__name__}: {e}")

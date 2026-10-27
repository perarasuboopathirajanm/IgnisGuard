# =============================================================================
#  IgnisGuard - Fire & PPE safety detection
#  Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
#  Author: Perarasu Boopathirajan
#  Unauthorized copying, redistribution or claiming authorship of this file,
#  via any medium, is prohibited without written permission. See LICENSE.
# =============================================================================
"""IgnisGuard — Fire & PPE (helmet / fire jacket) detection with a training studio.

Run:  python app.py      then open http://127.0.0.1:8000
"""
import base64
import hmac
import os
import re
import time
from typing import List

import cv2
import uvicorn
from fastapi import Body, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from core import config as C
from core.dataset import Dataset
from core.detector import Detector, decode_image
from core.trainer import Trainer

app = FastAPI(title="IgnisGuard", description=f"Fire & PPE safety detection. (c) 2026 {C.AUTHOR}. All rights reserved.",
              contact={"name": C.AUTHOR})
detector = Detector()
dataset = Dataset()
trainer = Trainer(dataset, detector)
STATIC = C.ROOT / "static"
# Local all-in-one mode: serve ../frontend when running from the combined repo
FRONTEND = C.ROOT.parent / "frontend"
MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.pt$")

if not C.API_KEY:
    print("[ignisguard] WARNING: IGNIS_API_KEY is not set - the API is open to anyone who can reach it.\n"
          "[ignisguard]          Uploading .pt models is disabled until a key is set.", flush=True)


def safe_model_name(name: str) -> str:
    """Only plain file names like 'best_v2.pt' - blocks '../' path tricks."""
    name = (name or "").strip()
    if not MODEL_NAME_RE.fullmatch(name):
        raise HTTPException(400, "Invalid model name (letters, digits, . _ - only, ending in .pt)")
    return name


async def read_limited(f: UploadFile, max_mb: int) -> bytes:
    data = await f.read(max_mb * 1024 * 1024 + 1)
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(413, f"{f.filename}: file is larger than {max_mb} MB")
    return data


@app.middleware("http")
async def add_author_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Author"] = C.AUTHOR
    return response


@app.middleware("http")
async def require_key(request: Request, call_next):
    """If IGNIS_API_KEY is set, every /api call needs it (header X-API-Key or ?key=)."""
    if (C.API_KEY and request.url.path.startswith("/api/") and request.url.path != "/api/health"
            and request.method != "OPTIONS"):
        given = request.headers.get("x-api-key") or request.query_params.get("key") or ""
        if not hmac.compare_digest(given.encode(), C.API_KEY.encode()):  # bytes: non-ASCII input can't crash it
            return JSONResponse({"detail": "Invalid or missing API key"}, status_code=401)
    return await call_next(request)


# added after the key check so CORS headers are present on every response (incl. 401)
app.add_middleware(CORSMiddleware, allow_origins=C.CORS_ORIGINS, allow_methods=["*"],
                   allow_headers=["*"], allow_credentials=False)

_ui = STATIC if (STATIC / "index.html").exists() else (FRONTEND if (FRONTEND / "index.html").exists() else None)
if _ui is not None:
    app.mount("/static", StaticFiles(directory=_ui / "static" if (_ui / "static").is_dir() else _ui), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return (_ui / "index.html").read_text(encoding="utf-8")
else:
    @app.get("/")
    def index():
        return {"service": "IgnisGuard API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health():
    return {"ok": True, "model": detector.model_name, "training": trainer.running(),
            "auth": bool(C.API_KEY), "author": C.AUTHOR}


@app.get("/api/info")
def info():
    return {"classes": C.CLASSES, "alert_classes": C.ALERT_CLASSES, "detector": detector.info()}


# ---------------- ANALYSIS ----------------
@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), conf: float = Form(0.35),
                  helmet: bool = Form(True), jacket: bool = Form(True), fire: bool = Form(True),
                  return_image: bool = Form(True)):
    conf = min(max(conf, 0.01), 0.99)
    data = await read_limited(file, C.MAX_IMAGE_MB)
    try:
        img = await run_in_threadpool(decode_image, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    t = time.time()
    try:
        # model inference is CPU-heavy: run it in a worker thread so the server stays responsive
        dets, alerts, people, drawn = await run_in_threadpool(detector.analyze, img, conf, helmet, jacket, fire)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    out = {"detections": dets, "alerts": alerts, "people": people,
           "ms": round((time.time() - t) * 1000), "model": detector.model_name,
           "width": img.shape[1], "height": img.shape[0]}
    if return_image:
        ok, buf = cv2.imencode(".jpg", drawn, [cv2.IMWRITE_JPEG_QUALITY, 85])
        out["image"] = "data:image/jpeg;base64," + base64.b64encode(buf).decode()
    return out


# ---------------- MODELS ----------------
@app.get("/api/models")
def models():
    active = C.ACTIVE_MODEL_FILE.read_text().strip() if C.ACTIVE_MODEL_FILE.exists() else None
    items = [{"name": p.name, "size_mb": round(p.stat().st_size / 1e6, 1), "created": p.stat().st_mtime,
              "active": p.name == active and detector.mode == "custom"}
             for p in sorted(C.MODELS_DIR.glob("*.pt"), key=lambda p: -p.stat().st_mtime)]
    return {"models": items, "detector": detector.info()}


@app.post("/api/models/activate")
def activate(name: str = Body(..., embed=True)):
    if name == "__starter__":
        C.ACTIVE_MODEL_FILE.unlink(missing_ok=True)
        detector.load_active()
    else:
        name = safe_model_name(name)
        if not (C.MODELS_DIR / name).is_file():
            raise HTTPException(404, "Model not found")
        detector.set_active(name)
    return detector.info()


@app.post("/api/models/upload")
async def upload_model(file: UploadFile = File(...)):
    # A .pt file is a Python pickle: loading one can run arbitrary code on the server.
    # So model upload is only allowed when the API is protected by a key.
    if not C.API_KEY:
        raise HTTPException(403, "Model upload is disabled because IGNIS_API_KEY is not set. "
                                 "Set an API key on the server first (a .pt file can contain code).")
    name = safe_model_name(os.path.basename((file.filename or "").replace("\\", "/")))
    data = await read_limited(file, C.MAX_MODEL_MB)
    tmp = C.MODELS_DIR / (name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, C.MODELS_DIR / name)
    return {"ok": True, "name": name}


@app.get("/api/models/download/{name}")
def download_model(name: str):
    name = safe_model_name(name)
    p = C.MODELS_DIR / name
    if not p.is_file():
        raise HTTPException(404)
    return FileResponse(p, filename=name)


# ---------------- TRAINING DATA ----------------
@app.get("/api/dataset")
def ds_list():
    return {"items": dataset.list(), "stats": dataset.stats()}


@app.post("/api/dataset/upload")
async def ds_upload(files: List[UploadFile] = File(...)):
    added, errors = [], []
    for f in files:
        try:
            data = await read_limited(f, C.MAX_IMAGE_MB)
            added.append(await run_in_threadpool(dataset.add_image, f.filename or "image.jpg", data))
        except HTTPException as e:
            errors.append(e.detail)
        except ValueError as e:
            errors.append(str(e))
    return {"added": added, "errors": errors}


@app.post("/api/dataset/import")
async def ds_import(file: UploadFile = File(...)):
    data = await read_limited(file, C.MAX_ZIP_MB)
    try:
        return await run_in_threadpool(dataset.import_yolo_zip, data)
    except Exception as e:  # noqa
        raise HTTPException(400, f"Import failed: {e}")


@app.get("/api/dataset/image/{iid}")
def ds_image(iid: str):
    if not dataset.get(iid):
        raise HTTPException(404)
    return FileResponse(dataset.path(iid))


@app.post("/api/dataset/{iid}/boxes")
def ds_boxes(iid: str, payload: dict = Body(...)):
    if not dataset.get(iid):
        raise HTTPException(404)
    boxes = payload.get("boxes", []) if isinstance(payload, dict) else None
    if not isinstance(boxes, list):
        raise HTTPException(400, "boxes must be a list")
    try:
        return dataset.set_boxes(iid, boxes, bool(payload.get("background", False)))
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "Each box needs cls, x1, y1, x2, y2 (numbers)")


@app.post("/api/dataset/{iid}/autolabel")
def ds_autolabel(iid: str, conf: float = Body(0.3, embed=True)):
    """Pre-fill boxes using the current model so you only need to correct them."""
    it = dataset.get(iid)
    if not it:
        raise HTTPException(404)
    img = cv2.imread(str(dataset.path(iid)))
    if img is None:
        raise HTTPException(500, "Stored image could not be read")
    conf = min(max(float(conf), 0.01), 0.99)
    try:
        dets, _, _, _ = detector.analyze(img, conf, False, False, True)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"boxes": [{"cls": d["label"], "x1": d["box"][0], "y1": d["box"][1],
                       "x2": d["box"][2], "y2": d["box"][3]} for d in dets if d["label"] in C.CLASSES]}


@app.delete("/api/dataset/{iid}")
def ds_delete(iid: str):
    dataset.delete(iid)
    return {"ok": True}


# ---------------- TRAINING JOB ----------------
@app.post("/api/train/start")
def train_start(epochs: int = Body(50), imgsz: int = Body(640), base: str = Body("yolo11n"),
                batch: int = Body(8), device: str = Body("auto")):
    if base not in {"yolo11n", "yolo11s", "yolo11m", "yolov8n", "yolov8s"}:
        raise HTTPException(400, "Unknown base model")
    # keep values sane so one request can't tie up the server for days or crash it
    if not 1 <= epochs <= 500:
        raise HTTPException(400, "epochs must be between 1 and 500")
    if not 160 <= imgsz <= 1280:
        raise HTTPException(400, "imgsz must be between 160 and 1280")
    imgsz = imgsz // 32 * 32
    if not 1 <= batch <= 64:
        raise HTTPException(400, "batch must be between 1 and 64")
    device = str(device).strip().lower()
    if not re.fullmatch(r"auto|cpu|mps|\d+(,\d+)*", device):
        raise HTTPException(400, "device must be auto, cpu, mps or GPU numbers like 0 or 0,1")
    try:
        trainer.start(epochs, imgsz, base, batch, device)
    except (RuntimeError, ValueError) as e:
        raise HTTPException(400, str(e))
    return trainer.state


@app.post("/api/train/stop")
def train_stop():
    trainer.stop()
    return trainer.state


@app.get("/api/train/status")
def train_status():
    s = dict(trainer.state)
    s["running"] = trainer.running()
    return s


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"\n  IgnisGuard running →  http://127.0.0.1:{port}\n")
    uvicorn.run(app, host="0.0.0.0", port=port)

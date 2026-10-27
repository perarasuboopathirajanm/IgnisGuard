# IgnisGuard - Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
# IgnisGuard API: Hugging Face Space (Docker SDK)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*

# Spaces run the container as user 1000
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    YOLO_CONFIG_DIR=/home/user/.config/Ultralytics \
    PORT=7860
WORKDIR /home/user/app

# CPU-only PyTorch keeps the image small (Spaces free tier has no GPU)
RUN pip install --no-cache-dir --user torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt \
 && (pip install --no-cache-dir --user "git+https://github.com/ultralytics/CLIP.git" || echo "CLIP will be installed on first use")

COPY --chown=user . .

# Pre-download weights so the first request is fast (ignored if it fails)
RUN python -c "from ultralytics import YOLO, YOLOWorld; YOLO('yolo11n.pt'); m=YOLOWorld('yolov8s-worldv2.pt'); m.set_classes(['fire','person'])" || true

EXPOSE 7860
# Use the persistent disk (/data) when it's enabled on the Space; otherwise use local, temporary storage
CMD ["sh", "-c", "if [ -z \"$IGNIS_DATA\" ]; then if [ -w /data ]; then export IGNIS_DATA=/data/ignisguard; else export IGNIS_DATA=/home/user/app/data; fi; fi; exec uvicorn app:app --host 0.0.0.0 --port 7860"]

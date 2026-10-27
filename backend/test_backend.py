# IgnisGuard - Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
"""IgnisGuard backend self-test (no extra packages needed).

Usage:
    python test_backend.py <BACKEND_URL> [API_KEY] [image.jpg]

Example:
    python test_backend.py https://your-name-ignisguard-api.hf.space mySecretKey fire.jpg
    python test_backend.py http://127.0.0.1:7860
"""
import base64, json, sys, time, urllib.error, urllib.request, uuid

SAMPLE_JPG = base64.b64decode("/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA0JCgsKCA0LCgsODg0PEyAVExISEyccHhcgLikxMC4pLSwzOko+MzZGNywtQFdBRkxOUlNSMj5aYVpQYEpRUk//2wBDAQ4ODhMREyYVFSZPNS01T09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT09PT0//wAARCADwAUADASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwDjqKKK0ICiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKms4PtNykO7buzzjOOM0pSUU5PZDjFzkordkNFbP9hf8ATz/5D/8Ar0f2F/08/wDkP/69cv1/D/zfg/8AI7P7NxP8v4r/ADMaitn+wv8Ap5/8h/8A16P7C/6ef/If/wBej6/h/wCb8H/kH9m4n+X8V/mY1FbP9hf9PP8A5D/+vR/YX/Tz/wCQ/wD69H1/D/zfg/8AIP7NxP8AL+K/zMaitn+wv+nn/wAh/wD16P7C/wCnn/yH/wDXo+v4f+b8H/kH9m4n+X8V/mY1FbP9hf8ATz/5D/8Ar0f2F/08/wDkP/69H1/D/wA34P8AyD+zcT/L+K/zMaitn+wv+nn/AMh//Xo/sL/p5/8AIf8A9ej6/h/5vwf+Qf2bif5fxX+ZjUVZv7T7HOsfmb8ruzjHc/4VWrphNTipR2ZyThKnJxlugoooqiQooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap1c0j/AJCcP/Av/QTWOI/gy9H+Rthf48PVfmdNRRRXy59gFFFFABRRRQAUUUUAFFFFABRRRQBz+vf8fqf9cx/M1m1pa9/x+p/1zH8zWbX0uE/gR9D5PHf7xP1Ciiiuk5QooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACiiigAooooAKKKKACrmkf8AITh/4F/6Cap0qO0bBkYqw6EHBqKkeeDj3RdKfJUjN9GmdjRXJ/a7r/n5m/77NH2u6/5+Zv8Avs15H9lz/mR7f9sQ/lZ1lFcn9ruv+fmb/vs0fa7r/n5m/wC+zR/Zc/5kH9sQ/lZ1lFcn9ruv+fmb/vs0fa7r/n5m/wC+zR/Zc/5kH9sQ/lZ1lFcn9ruv+fmb/vs0fa7r/n5m/wC+zR/Zc/5kH9sQ/lZ1lFcn9ruv+fmb/vs0fa7r/n5m/wC+zR/Zc/5kH9sQ/lZ1lFcn9ruv+fmb/vs0fa7r/n5m/wC+zR/Zc/5kH9sQ/lZc17/j9T/rmP5ms2nSSSStukdnOMZY5pterRpunTUH0PGxFRVajmuoUUUVqZBRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFABRRRQAUUUUAFFFFAH/2Q==")

if len(sys.argv) < 2:
    print(__doc__); sys.exit(1)
BASE = sys.argv[1].rstrip("/")
KEY = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "-" else ""
IMG = sys.argv[3] if len(sys.argv) > 3 else None
ok_all = True


def call(path, data=None, headers=None, key=True, timeout=120):
    h = dict(headers or {})
    if key and KEY:
        h["X-API-Key"] = KEY
    req = urllib.request.Request(BASE + path, data=data, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}"), dict(r.headers)
    except urllib.error.HTTPError as e:
        try: body = json.loads(e.read())
        except Exception: body = {}
        return e.code, body, dict(e.headers)


def check(name, cond, detail=""):
    global ok_all
    ok_all &= bool(cond)
    print(("  PASS  " if cond else "  FAIL  ") + name + (f"  ->  {detail}" if detail else ""))


print(f"\nTesting IgnisGuard backend at {BASE}\n")

# 1. health (wakes a sleeping Space)
for attempt in range(12):
    try:
        st, body, _ = call("/api/health", key=False, timeout=30)
        break
    except Exception as e:
        print(f"  ...backend not answering yet ({e.__class__.__name__}), retrying in 10 s")
        time.sleep(10)
else:
    check("backend reachable", False, "no answer after 2 minutes: check the Space status/logs"); sys.exit(1)
check("1. backend reachable (/api/health)", st == 200 and body.get("ok"), body)

# 2. API key protection
st, body, _ = call("/api/info", key=False)
if st == 401:
    check("2. API key is required (good)", True)
    if not KEY:
        print("\n  This backend needs a key: run again with your IGNIS_API_KEY as the 2nd argument."); sys.exit(1)
else:
    print("  WARN  2. backend is NOT protected by an API key (set IGNIS_API_KEY secret on the Space)")

# 3. key accepted + model status
st, body, _ = call("/api/info")
check("3. key accepted (/api/info)", st == 200, "" if st == 200 else body)
det = body.get("detector", {}) if st == 200 else {}
check("4. a model is loaded", bool(det.get("model")), det.get("model") or det.get("error"))

# 4. CORS (what the Netlify site needs)
_, _, hdrs = call("/api/health", headers={"Origin": "https://example.netlify.app"}, key=False)
allow = {k.lower(): v for k, v in hdrs.items()}.get("access-control-allow-origin")
print(f"  INFO  5. CORS allow-origin header: {allow!r}  (must be * or your Netlify URL)")

# 5. analyze an image
data = open(IMG, "rb").read() if IMG else SAMPLE_JPG
bnd = uuid.uuid4().hex
body_bytes = (f"--{bnd}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"test.jpg\"\r\n"
              f"Content-Type: image/jpeg\r\n\r\n").encode() + data + \
             f"\r\n--{bnd}\r\nContent-Disposition: form-data; name=\"return_image\"\r\n\r\nfalse\r\n--{bnd}--\r\n".encode()
t = time.time()
st, body, _ = call("/api/analyze", data=body_bytes, headers={"Content-Type": f"multipart/form-data; boundary={bnd}"})
check("6. image analysis (/api/analyze)", st == 200,
      f"{int((time.time()-t)*1000)} ms, alerts={body.get('alerts')}, detections={len(body.get('detections', []))}"
      if st == 200 else body)
if st == 200:
    for d in body["detections"][:10]:
        print(f"          - {d['label']:<15} {d['conf']:.2f}  {[int(v) for v in d['box']]}")

# 6. dataset + training endpoints respond
st, body, _ = call("/api/dataset")
check("7. training data endpoint (/api/dataset)", st == 200, body.get("stats") if st == 200 else body)
st, body, _ = call("/api/train/status")
check("8. training status endpoint", st == 200, body.get("status") if st == 200 else body)

print("\nRESULT: " + ("ALL CHECKS PASSED ✔" if ok_all else "SOME CHECKS FAILED ✘ (see above)") + "\n")
sys.exit(0 if ok_all else 1)

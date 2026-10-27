# IgnisGuard: Connect & Test Guide

_IgnisGuard · © 2026 Perarasu Boopathirajan. All rights reserved._

This repo has two parts:

| File | What it is | Where it goes |
|---|---|---|
| **`backend/`** folder | AI server (FastAPI + YOLO): detection, training, models | **Hugging Face Space** (Docker) |
| **`frontend/`** folder | Website (HTML/CSS/JS): Analysis and Training screens | **Netlify** |

```
 You (browser) ──▶ Netlify website ──(HTTPS API calls + API key)──▶ Hugging Face backend
```

**Order:** 1) deploy the backend → 2) test the backend → 3) set the backend URL in the frontend → 4) deploy the frontend → 5) connect → 6) test everything.

---

## STEP 1: Deploy the backend (Hugging Face)

1. Open the **`backend`** folder. You should see:
   ```
   Dockerfile   README.md   app.py   requirements.txt   test_backend.py   .dockerignore   core\ (5 files)
   ```
2. Go to **https://huggingface.co/new-space** and fill in the form:
   - Space name: `ignisguard-api`
   - SDK: **Docker** → template **Blank**
   - Hardware: **CPU basic (free)**
   - Visibility: **Public**
   - Then click **Create Space**.
3. On the Space page, go to **Files** → **+ Contribute** → **Upload files**. Drag in **all the files inside `backend/` and the `core` folder** (not the `backend` folder itself), then click **Commit changes to main**.
   - When asked about `README.md`, replace the existing one. Ours contains the Docker settings.
   - After committing, open **Files** and confirm that `core/` contains `__init__.py, config.py, dataset.py, detector.py, trainer.py`.
4. Add the access key: **Settings** → **Variables and secrets** → **New secret**
   - Name: `IGNIS_API_KEY`
   - Value: a password you make up, e.g. `fire-7Kq2-guard-93xZ`. **Write it down.**
   - Without a key the API is open to anyone, and **Upload .pt model** stays disabled (a `.pt` file can contain code).
5. Wait for the build (**Logs** tab). The first build takes about 5–10 minutes. It's done when the badge at the top says **Running**.

**Your backend URL** looks like this:
```
https://<your-hf-username>-ignisguard-api.hf.space
```
(You can also find it under **⋮ (top right) → Embed this Space → Direct URL**. Use lowercase, and change any `_` or `.` in your username to `-`.)

---

## STEP 2: Test the backend (before touching the frontend)

### Test 2a: browser (10 seconds)
| Open this URL | You should see |
|---|---|
| `https://<backend-url>/api/health` | `{"ok":true,"model":"Starter (YOLO-World, zero-shot)","training":false}` |
| `https://<backend-url>/api/info` | `{"detail":"Invalid or missing API key"}` ← this is correct: your key protection works |
| `https://<backend-url>/docs` | The interactive API page (Swagger) |

### Test 2b: full self-test script (recommended)
On your PC, in the `backend` folder, run this in PowerShell (only Python is needed, no extra packages):
```powershell
python test_backend.py https://<backend-url> YOUR_API_KEY
```
To also test with a real photo:
```powershell
python test_backend.py https://<backend-url> YOUR_API_KEY C:\path\to\fire.jpg
```
Expected output:
```
  PASS  1. backend reachable (/api/health)
  PASS  2. API key is required (good)
  PASS  3. key accepted (/api/info)
  PASS  4. a model is loaded
  INFO  5. CORS allow-origin header: '*'
  PASS  6. image analysis (/api/analyze)  ->  850 ms, alerts={'FIRE': 1}, detections=3
  PASS  7. training data endpoint (/api/dataset)
  PASS  8. training status endpoint
RESULT: ALL CHECKS PASSED ✔
```
**Don't continue until you see ALL CHECKS PASSED.** If something fails, see *Troubleshooting* at the bottom.

### Test 2c: Swagger (optional)
In `https://<backend-url>/docs`, open **POST /api/analyze** → **Try it out** → choose an image → **Execute**.
(If you set a key, Swagger has no key box. Use the test script instead, or test before adding the secret.)

---

## STEP 3: Point the frontend at the backend

1. Open the **`frontend`** folder. You should see:
   ```
   index.html   netlify.toml   static\app.js   static\config.js   static\style.css
   ```
2. Open **`static\config.js`** in Notepad and paste your backend URL between the quotes:
   ```js
   window.IGNIS_API = "https://<your-hf-username>-ignisguard-api.hf.space";
   ```
   - Use `https://`, and **don't** add a `/` at the end.
   - **Don't** put your API key in this file. Anyone can read it once it's online.
3. Save the file.

---

## STEP 4: Deploy the frontend (Netlify)

1. Go to **https://app.netlify.com/drop** and log in.
2. Drag the **`frontend` folder** (the one containing `index.html`) onto the page.
   (Or connect the GitHub repo and set **Base directory** = `frontend`.)
3. After a few seconds you get a URL like `https://sparkly-cat-12ab34.netlify.app`.
4. Optional: rename it under **Site configuration** → **Change site name** (e.g. `ignisguard` → `https://ignisguard.netlify.app`).

> If you change `config.js` later: go to Netlify → your site → **Deploys** tab and drag the folder in again.

---

## STEP 5: Connect them

1. Open your Netlify site.
2. At first you'll see **"Wrong API key"** at the top right. That's expected.
3. Click **⚙ Settings** (top right):
   - **Backend URL:** leave it empty (it comes from `config.js`), or paste the backend URL to override it.
   - **API key:** your `IGNIS_API_KEY`.
   - Click **Save & reload**.
4. The top-right badge should now show a **green or yellow dot** and the model name:
   - 🟡 yellow = starter model (zero-shot)
   - 🟢 green = your own trained model
   - 🔴 red = not connected (see Troubleshooting)

The key is saved in *this browser only*. Enter it once on each new device or browser.

5. **Lock the backend to your site (recommended):** in the Hugging Face Space, go to **Settings → Variables and secrets → New variable**:
   - Name: `IGNIS_CORS_ORIGINS`
   - Value: `https://ignisguard.netlify.app` (your exact Netlify URL, no trailing `/`)

   The Space restarts. Afterwards, reload the Netlify site; it should still connect.

---

## STEP 6: Test everything end-to-end

Tick each box:

**Analysis tab**
- [ ] Upload 1 fire photo → a red **🔥 FIRE** badge and a box on the image
- [ ] Upload a photo of workers without helmets → **⛑️ NO HELMET**
- [ ] Upload a photo of workers with helmets and vests → fewer or no violations
- [ ] Upload 3–5 images at once → a thumbnail row appears (SAFE / alert labels), and clicking one switches the view
- [ ] Turn off **No helmet** and upload again → no helmet alerts
- [ ] Move the **confidence** slider to 0.15 → more boxes; move it to 0.7 → fewer boxes
- [ ] **Webcam** → allow the camera → live boxes appear (about 1–2 analysed frames/s on free CPU)
- [ ] **Video** → choose an .mp4 → boxes follow the video

**Training tab**
- [ ] *1 · Add images*: upload 10 photos → the counters go up
- [ ] *2 · Label*: press `3` and drag a box around a person; press `5` and drag around a bare head; press `S` → the next image opens, and the thumbnail shows ✔
- [ ] **✨ Auto-label** adds suggested boxes
- [ ] *3 · Train*: YOLO11 Nano, **Epochs 5**, **Image size 416** → **Start training** → the progress bar and chart move
- [ ] When it shows **Finished ✔**, the model appears in the list as **ACTIVE**, and the top-right badge turns 🟢
- [ ] **Download** saves the `.pt` file to your PC. Keep it: free Spaces lose data on restart.
- [ ] **Use starter model** switches back to 🟡, and **Use** on your model switches back to 🟢

**Persistence check**
- [ ] In the Space, click **Settings → Restart this Space**, wait, and reload the site. Your images and models are still there only if **Persistent storage** is enabled. Otherwise re-upload your model with **Upload .pt model**.

---

## Test locally first (optional, no internet deploy needed)

**Quickest: one window.** When run from this repo, the backend also serves the frontend:
```powershell
cd path\to\IgnisGuard\backend
python -m venv .venv; .\.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open **http://127.0.0.1:8000**. That's it.

**Or two windows** (closer to the real Netlify + Hugging Face setup):

**Window 1: backend**
```powershell
cd path\to\IgnisGuard\backend
python -m venv .venv; .\.venv\Scripts\activate
pip install -r requirements.txt
$env:IGNIS_API_KEY="test123"; $env:PORT="7860"
python app.py
```
**Window 2: frontend**
```powershell
cd path\to\IgnisGuard\frontend
# set static\config.js to:  window.IGNIS_API = "http://127.0.0.1:7860";
python -m http.server 8080
```
Open **http://127.0.0.1:8080** → ⚙ Settings → key `test123`.
Test the backend with: `python test_backend.py http://127.0.0.1:7860 test123`

---

## Troubleshooting

| What you see | Cause | Fix |
|---|---|---|
| Badge **"Backend offline"** + yellow banner | Space asleep, still building, or wrong URL | Open `<backend-url>/api/health` in a new tab and wait 1–2 min. Check `config.js` (https, no trailing `/`). Check the Space **Logs**. |
| Badge **"Wrong API key"** | Key missing or different | ⚙ Settings → re-type the key exactly (it's case-sensitive). |
| Browser console (F12) shows **"blocked by CORS policy"** | `IGNIS_CORS_ORIGINS` doesn't match your site | Set it to your exact Netlify URL (`https://…netlify.app`, no `/` at the end), or delete the variable to allow all. |
| **"No trained model yet and the starter model could not be downloaded"** | The weights download failed during the build | Space → **Settings → Factory rebuild**. Or train a model / upload a `.pt`. |
| Space build **fails** | See the **Logs** tab | Check that `README.md` (with `sdk: docker`, `app_port: 7860`) and `Dockerfile` are at the top level, not inside a sub-folder. |
| `/api/health` shows **404** | Files were uploaded inside a folder | Move the files to the Space's root folder. |
| Import error **`No module named core`** | The `core` folder wasn't uploaded correctly | Upload the 5 files into `core/` (**+ Contribute → Create new file** → name `core/config.py` …). |
| Training is **very slow** | Free CPU | Use Nano, size 416, fewer epochs. Or train on your PC with `run.bat` and upload the `.pt` file. |
| **Webcam** doesn't start | No HTTPS, or permission was denied | Use the https Netlify URL, and allow the camera in the browser's address bar. |
| Images and models **disappeared** | The Space restarted without persistent storage | Enable **Persistent storage**, and keep downloaded `.pt` files as a backup. |
| Big dataset **zip import fails** | Upload too large or timed out | Split the zip into parts under 100 MB. |

Need to change something later?
- **Backend code:** upload the changed file to the Space again (it rebuilds automatically).
- **Frontend:** drag the folder onto Netlify → **Deploys** again.

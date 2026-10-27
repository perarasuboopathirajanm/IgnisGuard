---
title: IgnisGuard API
emoji: 🔥
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# IgnisGuard API

Created by **Perarasu Boopathirajan** · © 2026 · All rights reserved

This is the backend for IgnisGuard, which detects fire, smoke, missing helmets, and missing fire jackets, and includes a training studio.
The web interface is hosted separately (on Netlify).

* Health check: `/api/health`
* Interactive API docs: `/docs`

## Space settings (Settings → Variables and secrets)
| Name | Type | Purpose |
|---|---|---|
| `IGNIS_API_KEY` | **Secret** (strongly recommended) | Access key. The web UI must enter the same key under ⚙ Settings. Without it the API is open and model upload is disabled. |
| `IGNIS_CORS_ORIGINS` | Variable (optional) | Your Netlify URL, e.g. `https://ignisguard.netlify.app`, to allow only that site. Default is `*`. |

Enable **Persistent storage** (Settings → Persistent storage) to keep uploaded images and trained models across restarts. Without it, they are lost whenever the Space restarts or sleeps.

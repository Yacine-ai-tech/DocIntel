# Self-Hosting DocIntel

1. **Environment:** Copy `.env.example` to `.env` and fill in the routes you want (see the
   comments in that file — Route A/B/C, `FRONTEND_URL`, etc).
2. **Docker:** `docker build -t docintel . && docker run -p 8001:8001 --env-file .env docintel`
   (or `docker compose -f docker-compose.dev.yml up` for local dev). FastAPI serves the built
   frontend itself (`frontend/dist/`) at `/`, so frontend and backend share one origin by default.
3. **GPU Note:** If running Surya or Marker natively, a CUDA GPU with 16GB+ VRAM is recommended.
4. **Hosting:** Render free tier (see `render.yaml`) or a dedicated on-demand GPU cloud host.
5. **Mobile camera scan:** set `FRONTEND_URL` to wherever your phone can actually reach the app
   (not `localhost` unless the phone and server are the exact same machine). Most mobile browsers
   only allow camera capture on a secure context — **HTTPS**, or `localhost` for same-device
   testing. Plain `http://192.168.x.x:8001` on a LAN will generally NOT be allowed to open the
   camera; put a reverse proxy with TLS (Caddy, nginx + certbot, a Cloudflare Tunnel, etc.) in
   front of it, or accept that mobile scan won't work over bare HTTP on your network.

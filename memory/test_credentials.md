# Test Credentials & Config

No user authentication — the app is a single-video / no-login flow.

## API keys (already in /app/backend/.env)
- `ELEVENLABS_API_KEY` — ElevenLabs Scribe STT (free tier: STT works, TTS blocked)
- `CLOUDINARY_API_KEY` = 319487612252352
- `CLOUDINARY_API_SECRET` = d8g34miTcQylPaF9AOqAtx072yY
- `CLOUDINARY_CLOUD_NAME` = `poaievfx` → **WORKING** (api.ping ok, exports upload + CDN 9:16 reframe delivered, HTTP 200).

## Test media
- `/app/memory/testvid.mp4` — 14.7s espeak speech clip with a 2.5s silence gap (640x360)
- A real face clip already uploaded in the library: "WhatsApp Video 2026-08-16 at 7.25.08 PM.mp4" (576x1024)

## Notes
- Headless Chromium in the preview env cannot decode H.264, so `<video>` previews render black in
  automated screenshots. This is an environment limitation, not an app bug.

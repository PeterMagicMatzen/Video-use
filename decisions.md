# Decisions — video-use

## 2026-04-24 — video-use installed; client-content restriction pending John's ADV review

**Context:** Installed browser-use/video-use at `C:\Users\pceci\Claude\Projects\video-use` with symlink registered at `%USERPROFILE%\.claude\skills\video-use`. Skill is globally available from any directory via `claude` + an inventory/edit prompt. Outputs land in `<source-folder>/edit/`, never in the repo.

**Data flow:** ElevenLabs Scribe API handles transcription. Audio leaves the machine → ElevenLabs servers → word-level transcript returned. Video itself is never uploaded; only audio is sent for transcription. ffmpeg runs locally for rendering.

**Constraint (compliance):** No client meeting recordings, prospect calls, RIA-identifiable audio, or any content containing client PII runs through this skill until John reviews the ElevenLabs data flow as part of the ADV Part 2A AI disclosure work. This is the same gating constraint that applies to other cloud AI processing of client data.

**Permitted use today:**
- Personal video
- Youth sports (Jr. Trevians, JTL/Lax Lab, LaxVerse promo)
- Marketing/launch videos (SnapShooter, ShelfIQ, DirectorOps)
- NSIA-related non-confidential content (not board executive session recordings)

**Open items:**
- Add ElevenLabs to the RIA vendor/data-flow inventory for John's ADV review
- Once cleared, document permitted client-content scenarios and any required disclosures
- Revisit whether self-hosted Whisper (local transcription, no cloud) is a better fit for any client-adjacent use case even post-clearance

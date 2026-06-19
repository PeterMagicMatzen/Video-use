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

## 2026-06-19 — ElevenLabs data flow cleared for client content (supersedes the 2026-04-24 restriction)

**Decision:** John approved the ElevenLabs Scribe data flow for **full client content**. The 2026-04-24 restriction — barring client meeting recordings, prospect calls, RIA-identifiable audio, and any client-PII audio from this skill — is **lifted**. All such content may now be transcribed and edited through video-use.

**Scope:** Full. No client-content carve-outs remain.

**Conditions:** None. Approval was unconditional.

**Documentation basis:** Verbal approval, per Pete, 2026-06-19. No written ADV-file record captured yet (see open item).

**Open items:**
- **Documentation hygiene (not a usage blocker):** capture a one-line written confirmation of John's approval into the ADV Part 2A AI-disclosure file / vendor inventory. Verbal-only sign-off for a third-party cloud vendor that receives client PII is thin for an exam trail — a dated email or memo closes that gap.
- The `risk: caution` tag on SKILL.md can remain (audio still leaves the machine to a third party, so "caution" stays factually accurate even when use is permitted) or be revisited — Pete's call.
- Self-hosted Whisper remains worth evaluating as a no-cloud alternative for the most sensitive material, even though cloud use is now permitted.

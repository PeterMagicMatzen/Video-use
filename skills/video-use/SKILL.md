---
name: video-use
description: Edit any video by conversation. Transcribe, cut, color grade, generate overlay animations, burn subtitles — for talking heads, montages, tutorials, travel, interviews. No presets, no menus. Ask questions, confirm the plan, execute, iterate, persist. Production-correctness rules are hard; everything else is artistic freedom.
---

# video-use

This is the plugin entry point for video-use. The full production rules, editing craft, and pipeline live in the repo-root `SKILL.md`; the editing scripts live in `helpers/`.

## Prerequisite (one-time — NOT part of the AI workflow)

video-use needs the repo cloned plus `ffmpeg` and an ElevenLabs API key. If `${CLAUDE_PLUGIN_ROOT}/helpers/transcribe.py` and `ffmpeg` aren't available, do the one-time setup in [`${CLAUDE_PLUGIN_ROOT}/install.md`](../../install.md) first.

## Start here

1. Read the complete skill — production rules, the ask→confirm→execute→self-eval→persist loop, and the cut craft — at **`${CLAUDE_PLUGIN_ROOT}/SKILL.md`**. That file is authoritative; follow it exactly.
2. The editing scripts (`transcribe.py`, `render.py`, `timeline_view.py`, …) are in **`${CLAUDE_PLUGIN_ROOT}/helpers/`**. Always read them before running — that's where the real logic lives.
3. For animation overlays, the `manim-video` skill in this plugin covers Manim-based generation.

## The one-line model

The LLM never watches the video — it *reads* it: a packed word-level transcript (`takes_packed.md`) is the primary surface, and `timeline_view` renders a filmstrip + waveform PNG only at decision points. Cuts come from speech boundaries and silence, never frame-dumping. Don't touch the cut without strategy approval.

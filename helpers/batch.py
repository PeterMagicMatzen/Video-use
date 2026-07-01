#!/usr/bin/env python3
"""
batch.py — processa múltiplos vídeos em sequência:
  1. Transcreve (Scribe, cached)
  2. Corrige português (Claude API)
  3. Detecta gaps internos (check_gaps)
  4. Gera EDL via sub-agente Claude
  5. Renderiza
  6. Exporta formatos

Uso:
    python3 batch.py <videos_dir> [--task remove-silence] [--formats reels feed]
    python3 batch.py /path/to/videos --task remove-silence --formats reels landscape
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


HELPERS = Path(__file__).parent


def run(cmd, description=""):
    if description:
        print(f"  → {description}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ⚠️  ERRO: {result.stderr[-300:]}", file=sys.stderr)
    return result.returncode == 0, result.stdout, result.stderr


def find_videos(videos_dir, extensions=(".mp4", ".mov", ".MP4", ".MOV")):
    return sorted([
        str(p) for p in Path(videos_dir).iterdir()
        if p.suffix in extensions and not p.stem.startswith(".")
    ])


def transcribe(video_path, edit_dir):
    ok, out, _ = run([
        sys.executable, str(HELPERS / "transcribe.py"), video_path,
        "--edit-dir", edit_dir
    ], "transcrever")
    return ok


def correct_transcript(transcript_path):
    corrected = str(Path(transcript_path).with_suffix(".corrected.json"))
    if os.path.exists(corrected):
        print(f"  ↩  correção já existe: {corrected}")
        return corrected
    ok, _, _ = run([
        sys.executable, str(HELPERS / "correct_transcript.py"),
        transcript_path, "-o", corrected
    ], "corrigir português")
    return corrected if ok else transcript_path


def check_gaps_report(edl_path, transcripts_dir):
    ok, out, _ = run([
        sys.executable, str(HELPERS / "check_gaps.py"),
        edl_path, transcripts_dir, "--min-ms", "300"
    ], "checar gaps internos")
    return out


def render(edl_path, out_path):
    ok, _, _ = run([
        sys.executable, str(HELPERS / "render.py"),
        edl_path, "-o", out_path
    ], f"renderizar → {out_path}")
    return ok


def export(final_path, formats, out_dir):
    run([
        sys.executable, str(HELPERS / "export_formats.py"),
        final_path,
        "--formats", *formats,
        "--out-dir", out_dir
    ], f"exportar {formats}")


def process_video(video_path, edit_dir, task, formats):
    stem = Path(video_path).stem
    print(f"\n{'='*60}")
    print(f"  {stem}")
    print(f"{'='*60}")

    # 1. transcrever
    transcripts_dir = os.path.join(edit_dir, "transcripts")
    os.makedirs(transcripts_dir, exist_ok=True)
    transcript_path = os.path.join(transcripts_dir, f"{stem}.json")

    if os.path.exists(transcript_path):
        print(f"  ↩  transcrição já existe")
    else:
        if not transcribe(video_path, edit_dir):
            print(f"  ✗ falha na transcrição — pulando")
            return False

    # 2. corrigir português
    corrected_path = correct_transcript(transcript_path)

    # 3. pack transcripts
    run([sys.executable, str(HELPERS / "pack_transcripts.py"),
         "--edit-dir", edit_dir], "pack transcripts")

    print(f"\n  ⚠️  EDL manual necessário para {stem}")
    print(f"     Transcrição disponível em: {corrected_path}")
    print(f"     Use Claude para gerar o EDL e depois rode:")
    print(f"     python3 render.py <edl.json> -o {edit_dir}/final_{stem}.mp4")

    edl_path = os.path.join(edit_dir, f"edl_{stem}.json")
    if not os.path.exists(edl_path):
        print(f"  ↩  EDL não encontrado — aguardando geração manual")
        return False

    # 4. checar gaps
    gaps_report = check_gaps_report(edl_path, transcripts_dir)
    if "gap" in gaps_report:
        print(f"\n  ⚠️  GAPS DETECTADOS:\n{gaps_report}")

    # 5. renderizar
    final_path = os.path.join(edit_dir, f"final_{stem}.mp4")
    if not render(edl_path, final_path):
        return False

    # 6. exportar formatos
    if formats:
        exports_dir = os.path.join(edit_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        export(final_path, formats, exports_dir)

    print(f"\n  ✓ {stem} concluído → {final_path}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("videos_dir")
    parser.add_argument("--task", default="remove-silence",
                        help="Tarefa a executar (padrão: remove-silence)")
    parser.add_argument("--formats", nargs="*",
                        default=[],
                        help="Formatos de export (reels feed stories landscape)")
    parser.add_argument("--edit-dir", default=None)
    args = parser.parse_args()

    videos = find_videos(args.videos_dir)
    if not videos:
        sys.exit(f"Nenhum vídeo encontrado em {args.videos_dir}")

    edit_dir = args.edit_dir or os.path.join(args.videos_dir, "edit")
    os.makedirs(edit_dir, exist_ok=True)

    print(f"Batch: {len(videos)} vídeo(s) em {args.videos_dir}")
    print(f"Task: {args.task}")
    print(f"Formatos: {args.formats or 'nenhum'}")

    results = {"ok": [], "fail": []}
    for vp in videos:
        ok = process_video(vp, edit_dir, args.task, args.formats)
        (results["ok"] if ok else results["fail"]).append(Path(vp).stem)

    print(f"\n{'='*60}")
    print(f"Batch concluído: {len(results['ok'])} ok, {len(results['fail'])} falhas")
    if results["fail"]:
        print(f"Falhas: {results['fail']}")


if __name__ == "__main__":
    main()

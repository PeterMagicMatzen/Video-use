#!/usr/bin/env python3
"""
correct_transcript.py — corrige erros ortográficos e de reconhecimento de fala
no JSON do Scribe usando Claude API, preservando os timestamps palavra por palavra.

Uso:
    python3 correct_transcript.py <transcript.json> [-o corrected.json]
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    sys.exit("anthropic não instalado. Rode: pip3 install anthropic")


SYSTEM_PROMPT = """Você é um revisor de transcrições automáticas em português brasileiro.
Receberá uma lista de palavras transcritas por ASR (reconhecimento de fala automático).
Sua tarefa:
1. Corrigir erros ortográficos mantendo o tom coloquial da fala (ex: "tá" é aceitável, não mude para "está")
2. Corrigir nomes próprios e siglas (ex: "fiap" → "FIAP", "linkedin" → "LinkedIn", "mec" → "MEC")
3. Corrigir palavras cortadas pelo ASR se o contexto deixar claro (ex: "Laboratória" → "Laboratoria" se for nome de empresa)
4. NÃO mudar palavras informais naturais da fala (tá, né, pra, vamo, a gente, etc.)
5. NÃO alterar a ordem das palavras
6. NÃO adicionar nem remover palavras
7. Retornar EXATAMENTE o mesmo número de palavras, uma por linha, na mesma ordem

Retorne APENAS as palavras corrigidas, uma por linha, sem numeração, sem explicações."""


def correct_words(words, api_key=None):
    client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))

    # só palavras reais (ignora audio_event e spacing)
    word_tokens = [(i, w) for i, w in enumerate(words) if w.get("type") == "word"]
    if not word_tokens:
        return words

    texts = [w["text"] for _, w in word_tokens]

    # envia em batches de 200 para não ultrapassar context
    batch_size = 200
    corrected_texts = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start:start + batch_size]
        prompt = "\n".join(batch)

        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )

        fixed = response.content[0].text.strip().split("\n")

        # garante mesmo número de palavras
        if len(fixed) != len(batch):
            print(f"  ⚠️  batch {start//batch_size+1}: retornou {len(fixed)} palavras, esperado {len(batch)} — mantendo original", file=sys.stderr)
            corrected_texts.extend(batch)
        else:
            corrected_texts.extend(fixed)

    # aplica correções de volta
    result = list(words)
    for (orig_idx, _), corrected_text in zip(word_tokens, corrected_texts):
        if result[orig_idx]["text"] != corrected_text:
            print(f"  {result[orig_idx]['text']!r} → {corrected_text!r}")
        result[orig_idx] = dict(result[orig_idx], text=corrected_text)

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", help="arquivo JSON do Scribe")
    parser.add_argument("-o", "--output", default=None)
    parser.add_argument("--api-key", default=None)
    args = parser.parse_args()

    with open(args.transcript) as f:
        data = json.load(f)

    print(f"  corrigindo {args.transcript}...")
    data["words"] = correct_words(data["words"], api_key=args.api_key)

    out_path = args.output or str(Path(args.transcript).with_suffix(".corrected.json"))
    with open(out_path, "w", ensure_ascii=False) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\ndone: {out_path}")


if __name__ == "__main__":
    main()

"""
news_server.py — Servidor Flask para geração de conteúdo a partir de manchetes
Uso: python3 news_server.py
Acesse: http://localhost:5050
"""

import os, json, time
from flask import Flask, jsonify, request, send_from_directory
import feedparser
import anthropic

app = Flask(__name__, static_folder="static")

TECHCRUNCH_RSS = "https://techcrunch.com/feed/"
HEADLINES_CACHE_TTL = 300  # seconds
_headlines_cache: dict = {"at": 0.0, "items": []}

# Client is created once; resolves ANTHROPIC_API_KEY from the environment.
_client = anthropic.Anthropic() if os.environ.get("ANTHROPIC_API_KEY") else None

PROMPTS = {
    "linkedin": """Você é um criador de conteúdo especialista em LinkedIn para o mercado tech brasileiro.
Com base na manchete abaixo, escreva um post profissional para LinkedIn.
Regras: português brasileiro, tom reflexivo e profissional, 150-250 palavras, termine com 2-3 hashtags relevantes, sem emojis excessivos.
Manchete: {headline}
Resumo: {summary}""",

    "instagram": """Você é um criador de conteúdo para Instagram focado em tecnologia.
Com base na manchete abaixo, escreva uma legenda para Instagram.
Regras: português brasileiro, engajante e direto, 80-120 palavras, emojis estratégicos, 5-8 hashtags no final.
Manchete: {headline}
Resumo: {summary}""",

    "tiktok": """Você é um roteirista de TikTok sobre tecnologia para público brasileiro jovem.
Com base na manchete abaixo, escreva uma legenda + gancho para vídeo TikTok.
Regras: português brasileiro coloquial, gancho forte na primeira linha, máximo 80 palavras, call to action no final.
Manchete: {headline}
Resumo: {summary}""",

    "twitter": """Você é um criador de threads no X (Twitter) sobre tecnologia.
Com base na manchete abaixo, escreva uma thread em português brasileiro.
Regras: 5 tweets numerados (1/5, 2/5...), máximo 280 caracteres cada, primeiro tweet com gancho forte, último com opinião/conclusão.
Manchete: {headline}
Resumo: {summary}""",

    "stories": """Você é um criador de conteúdo para Stories do Instagram sobre tecnologia.
Com base na manchete abaixo, escreva um roteiro de 3-5 stories sequenciais.
Regras: português brasileiro, cada story marcado [Story 1], [Story 2] etc, texto curto por story (max 2 linhas), inclua sugestão de fundo/visual entre parênteses.
Manchete: {headline}
Resumo: {summary}""",

    "roteiro": """Você é um roteirista de vídeos curtos (Reels/TikTok/Shorts) sobre tecnologia.
Com base na manchete abaixo, escreva um roteiro narrado de 60 segundos.
Regras: português brasileiro, marcações [GANCHO], [DESENVOLVIMENTO], [CONCLUSÃO], inclua sugestões visuais entre colchetes, ritmo dinâmico.
Manchete: {headline}
Resumo: {summary}""",
}

FORMAT_LABELS = {
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "twitter": "Thread X/Twitter",
    "stories": "Stories",
    "roteiro": "Roteiro de Vídeo",
}


@app.route("/")
def index():
    return send_from_directory(".", "news.html")


@app.route("/api/headlines")
def headlines():
    try:
        now = time.time()
        if _headlines_cache["items"] and now - _headlines_cache["at"] < HEADLINES_CACHE_TTL:
            return jsonify({"ok": True, "items": _headlines_cache["items"], "cached": True})
        feed = feedparser.parse(TECHCRUNCH_RSS)
        items = []
        for entry in feed.entries[:20]:
            items.append({
                "title": entry.get("title", ""),
                "summary": entry.get("summary", "")[:400],
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "image": next(
                    (m.get("url") for m in entry.get("media_content", []) if m.get("url")),
                    None
                ),
            })
        _headlines_cache["at"] = now
        _headlines_cache["items"] = items
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.json or {}
    headline = data.get("headline", "").strip()
    summary  = data.get("summary", "").strip()
    fmt      = data.get("format", "linkedin")

    if not headline:
        return jsonify({"ok": False, "error": "headline obrigatória"}), 400

    if fmt not in PROMPTS:
        return jsonify({"ok": False, "error": f"formato inválido: {fmt}"}), 400

    if _client is None:
        return jsonify({"ok": False, "error": "ANTHROPIC_API_KEY não configurada"}), 500

    try:
        prompt = PROMPTS[fmt].format(headline=headline, summary=summary)

        message = _client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        content = message.content[0].text
        return jsonify({"ok": True, "content": content, "format": FORMAT_LABELS.get(fmt, fmt)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "") == "1"
    print("🚀 Servidor rodando em http://localhost:5050")
    app.run(port=5050, debug=debug)

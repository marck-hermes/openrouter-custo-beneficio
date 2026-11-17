#!/usr/bin/env python3
"""Compara os modelos do OpenCode Zen com os mesmos modelos no OpenRouter.

Fontes locais (já no repo, ver refresh.py):
  data/aiiq_v1_models.json  — notas AI IQ por modelo
  data/or_models.json       — catálogo OpenRouter (preço/ctx)
  data/arena_elo.json       — ELO/agente do Arena (join por slug normalizado)
Saída: zen_compare.csv e zen_compare.md (tabela markdown)

Join = IDENTIDADE (nome normalizado), nunca preço — mesma regra do build_map.py.
Velocidade (tps/lat) existe apenas para endpoints :free do OpenRouter; o Zen não
tem :free, então a métrica fica de fora aqui.
"""
import csv
import json
import re
from pathlib import Path

REPO = Path(__file__).parent
DATA = REPO / "data"

# Tabela oficial Zen (opencode.ai/console/models, 2026-11-16). $/1M. None = não listado.
ZEN = [
    ("Claude Fable 5.1", "claude-fable-5-1", 10.00, 50.00, 0.25, 12.50),
    ("Claude Haiku 5.5", "claude-haiku-5-5", 0.10, 0.50, 0.01, 0.125),
    ("Claude Opus 5.5", "claude-opus-5-5", 4.00, 20.00, 0.20, 5.00),
    ("Claude Sonnet 5.5", "claude-sonnet-5-5", 2.00, 10.00, 0.20, 2.50),
    ("DeepSeek V4 Pro", "deepseek-v4-pro", 1.74, 3.48, 0.145, None),
    ("DeepSeek V4.1 Flash", "deepseek-v4.1-flash", 0.30, 1.20, 0.006, None),
    ("Gemini 3.5 Flash Lite", "gemini-3.5-flash-lite", 0.30, 2.50, 0.03, None),
    ("Gemini 3.8 Flash", "gemini-3.8-flash", 1.50, 7.50, 0.15, None),
    ("Gemini 4 Argon", "gemini-4-argon", 2.00, 10.00, 0.10, None),
    ("GLM-5.3", "glm-5.3", 1.40, 4.40, 0.26, None),
    ("GLM-5.3-Flash", "glm-5.3-flash", 0.15, 0.50, 0.03, None),
    ("GPT-5.3 Codex", "gpt-5.3-codex", 1.75, 14.00, 0.175, None),
    ("GPT-5.3 Codex Spark", "gpt-5.3-codex-spark", 1.75, 14.00, 0.175, None),
    ("GPT-5.4 Mini", "gpt-5.4-mini", 0.75, 4.50, 0.075, None),
    ("GPT-5.4 Nano", "gpt-5.4-nano", 0.20, 1.25, 0.02, None),
    ("GPT-5.5", "gpt-5.5", 5.00, 30.00, 0.50, None),
    ("GPT-5.5 Pro", "gpt-5.5-pro", 30.00, 180.00, 30.00, None),
    ("GPT-5.6 Terra", "gpt-5.6-terra", 2.00, 12.00, 0.20, 2.50),
    ("GPT-6 Astra", "gpt-6-astra", 10.00, 50.00, 1.00, 12.50),
    ("GPT-6 Luna", "gpt-6-luna", 0.10, 0.50, 0.01, 0.125),
    ("GPT-6.1 Sol", "gpt-6.1-sol", 2.00, 10.00, 0.10, 2.50),
    ("Grok 4.7", "grok-4.7", 2.00, 6.00, 0.50, None),
    ("Grok Build 0.1", "grok-build-0.1", 1.00, 2.00, 0.20, None),
    ("Kimi K2.7 Code", "kimi-k2.7-code", 0.95, 4.00, 0.19, None),
    ("Kimi K3", "kimi-k3", 3.00, 15.00, 0.30, 3.00),
    ("MiniMax-M3", "minimax-m3", 0.30, 1.20, 0.06, None),
    ("Mistral Large 4", "mistral-large-4", 0.68, 2.09, 0.07, None),
    ("Muse Wonder", "muse-wonder", 4.00, 20.00, 0.20, None),
    ("Qwen3.8 Flash", "qwen3.8-flash", 0.15, 0.47, 0.016, 0.20),
]

VENDOR = re.compile(r"^(google|openai|anthropic|meta|qwen|nvidia|xiaomi|z-ai|moonshotai|mistralai|"
                    r"x-ai|minimax|cohere|inclusionai|thinkingmachines|sakana|tencent|baidu|liquid|"
                    r"dots-studio|recursive|particle-ai|amazon|ibm-granite|upstage|perceptron|"
                    r"moondream|elorian|prism-ml|ai21|microsoft|perplexity|deepseek)-")


def slug(s: str) -> str:
    """Slug para join por identidade: minúsculo, sem separadores."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def ai_norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r":(free|batch)$", "", s)
    s = re.sub(r"^~", "", s)
    s = s.split("/")[-1]           # provider/model -> model
    s = re.sub(r"^claude-", "", s)
    s = VENDOR.sub("", s)
    s = re.sub(r"-it$", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


# Aliases manuais (Zen -> id OpenRouter) quando a identidade não bate sozinha
OR_ALIASES = {
    "mistral-large-4": "mistral-large-4-0",  # OpenRouter publicou como 4.0
}


def slug_elo(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def main():
    aiiq = json.loads((DATA / "aiiq_v1_models.json").read_text(encoding="utf-8"))["models"]
    ai_by = {}
    for m in aiiq:
        ai_by.setdefault(ai_norm(m["id"]), []).append(m)
        ai_by.setdefault(ai_norm(m.get("name", "")), []).append(m)

    or_models = json.loads((DATA / "or_models.json").read_text(encoding="utf-8"))["data"]
    or_by = {}
    for m in or_models:
        or_by.setdefault(ai_norm(m["id"]), []).append(m)

    elo_doc = json.loads((DATA / "arena_elo.json").read_text(encoding="utf-8")) if (DATA / "arena_elo.json").exists() else {"models": []}
    elo = {slug_elo(k): v for k, v in (elo_doc.get("models") or {}).items()}

    def best_or(cands):
        if not cands:
            return None
        def score(m):
            i = m["id"]
            if i.endswith((":batch", ":free")):
                return 1  # prefere variante normal sobre batch/free
            return 0
        cands = sorted(cands, key=score)
        return cands[0]

    def price1m(p):
        try:
            return float(p or 0) * 1e6
        except (TypeError, ValueError):
            return None

    rows = []
    for name, zid, zin, zout, zcr, zcw in ZEN:
        key = ai_norm(zid)
        key_or = ai_norm(OR_ALIASES.get(zid, zid))
        ai = (ai_by.get(key) or [None])[0]
        orm = best_or(or_by.get(key_or))
        r = {"zen": name, "zen_id": zid, "zen_in": zin, "zen_out": zout,
             "zen_cr": zcr, "zen_cw": zcw}
        if ai:
            d = ai.get("dimensions", {})
            r.update({
                "aiiq": ai["id"], "iq": ai.get("iq"),
                "cov": f"{ai.get('iqCoverage', {}).get('directDimensions', 0)}/{ai.get('iqCoverage', {}).get('totalDimensions', 7)}",
                "abs": d.get("abstract-reasoning"), "math": d.get("mathematical-reasoning"),
                "acad": d.get("academic-reasoning"), "code": d.get("programmatic-reasoning"),
                "cu": d.get("computer-use"), "rel": d.get("reliability"), "kw": d.get("knowledge-work"),
                "ctx": ai.get("contextWindow"), "rel_date": ai.get("releaseDate"),
                "open_source": ai.get("openSource"),
            })
        else:
            r.update({"aiiq": None, "iq": None, "cov": None, "abs": None, "math": None,
                      "acad": None, "code": None, "cu": None, "rel": None, "kw": None,
                      "ctx": None, "rel_date": None, "open_source": None})
        if orm:
            p = orm.get("pricing", {})
            r.update({"or_id": orm["id"],
                      "or_in": price1m(p.get("prompt")),
                      "or_out": price1m(p.get("completion")),
                      "or_cr": price1m(p.get("input_cache_read")),
                      "or_cw": price1m(p.get("input_cache_write"))})
            # delta Zen vs OpenRouter (%)
            try:
                r["delta_in"] = round(100 * (zin - r["or_in"]) / r["or_in"], 1) if r["or_in"] else None
                r["delta_out"] = round(100 * (zout - r["or_out"]) / r["or_out"], 1) if r["or_out"] else None
            except Exception:
                r["delta_in"] = r["delta_out"] = None
        else:
            r.update({"or_id": None, "or_in": None, "or_out": None, "or_cr": None,
                      "or_cw": None, "delta_in": None, "delta_out": None})
        e = elo.get(slug_elo(key)) or elo.get(slug_elo(ai["id"] if ai else ""))
        if e:
            r.update({"elo": e.get("rating"), "elo_rank": e.get("rank"),
                      "elo_code": e.get("coding_rating"), "elo_agent": e.get("agent_score")})
        else:
            r.update({"elo": None, "elo_rank": None, "elo_code": None, "elo_agent": None})
        rows.append(r)

    cols = ["zen", "zen_id", "zen_in", "zen_out", "zen_cr", "zen_cw",
            "or_id", "or_in", "or_out", "or_cr", "or_cw", "delta_in", "delta_out",
            "aiiq", "iq", "cov", "abs", "math", "acad", "code", "cu", "rel", "kw",
            "ctx", "rel_date", "open_source", "elo", "elo_rank", "elo_code", "elo_agent"]
    with open(REPO / "zen_compare.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    def fmt(x, unit="", dash="—"):
        return f"{x}{unit}" if x is not None else dash

    def pct(x, dash="—"):
        if x is None:
            return dash
        return f"{x:+.1f}%"

    lines = []
    lines.append("# OpenCode Zen × OpenRouter — comparação ($/1M tokens)")
    lines.append("")
    lines.append(f"Fonte preços Zen: opencode.ai/console/models (2026-11-16). "
                 f"AI IQ: snapshot {elo_doc.get('fetched_at', '')[:10] and 'local' or 'local'}; ELO: arena_elo.json local.")
    lines.append("")
    lines.append("| Zen model | Zen $in/out | OR equiv | OR $in/out | Δ in | Δ out | AI IQ (ψ) | Cov | Ctx | ELO |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        or_eq = r["or_id"] or "—"
        z = f"${r['zen_in']}/${r['zen_out']}"
        o = (f"${r['or_in']}/${r['or_out']}" if r["or_in"] is not None else "—")
        iq = r["iq"] if r["iq"] is not None else "—"
        lines.append(f"| {r['zen']} | {z} | `{or_eq}` | {o} | {pct(r['delta_in'])} | {pct(r['delta_out'])} "
                     f"| {iq} | {r['cov'] or '—'} | {fmt(r['ctx'], ' ctx').replace(' ', '')} "
                     f"| {fmt(r['elo'])} |")
    lines.append("")
    missing_ai = [r["zen"] for r in rows if r["iq"] is None]
    missing_or = [r["zen"] for r in rows if r["or_id"] is None]
    lines.append(f"Sem nota AI IQ: {', '.join(missing_ai) if missing_ai else 'nenhum'}")
    lines.append(f"Sem par OpenRouter: {', '.join(missing_or) if missing_or else 'nenhum'}")
    (REPO / "zen_compare.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"OK — {len(rows)} modelos. Saída: zen_compare.csv, zen_compare.md")
    print(f"Sem AI IQ: {missing_ai or 'nenhum'}; sem OR: {missing_or or 'nenhum'}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Liga ids do AI IQ aos ids do OpenRouter. Chave = identidade, nunca valor.

Regras, em ordem de confianca:
 1. Nome normalizado IDENTICO (`gpt-6-luna` -> `openai/gpt-6-luna`). 100%.
 2. OpenRouter acrescentou apenas PARAMETROS ao nome: tamanho total e ativos do MoE
    (`nemotron-3-ultra` -> `nemotron-3-ultra-550b-a55b`). Aceito, 80%.
 3. Qualquer outro sufixo e VERSIONAMENTO e e REJEITADO: `gpt-5` NAO e `gpt-5.5`,
    `opus-5` NAO e `opus-5.5`, `glm-5.3` NAO e `glm-5.3-flash`, `gpt-6-luna`
    NAO e `gpt-6-luna-october`. Aceitar prefixo solto gerava 54 pares errados,
    todos silenciosos -- o modelo herdava notas de outra geracao.

Preco nunca liga dois modelos; e reforco de confianca, nao chave.
"""
import json, re

AI = "aiiq_v1_models.json"
OR = "or_models.json"

VENDOR = (r"^(google|openai|anthropic|meta|qwen|nvidia|xiaomi|z-ai|moonshotai|mistralai|"
          r"x-ai|minimax|cohere|inclusionai|thinkingmachines|sakana|tencent|baidu|liquid|"
          r"dots-studio|recursive|particle-ai|amazon|ibm-granite|upstage|perceptron|"
          r"moondream|elorian|prism-ml|ai21|microsoft|perplexity)-")

# Sufixo aceitavel = parametros do modelo (tamanho total + ativos do MoE).
# ATENCAO: `norm` remove hifens, entao `550b-a55b` chega aqui como `550ba55b`.
PARAM_SUFFIX = re.compile(r"^(\d+b)(a\d+b)?$", re.I)


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r":(free|batch)$", "", s)
    s = re.sub(r"^~", "", s)
    s = s.split("/")[-1]
    s = re.sub(r"^claude-", "", s)
    s = re.sub(VENDOR, "", s)
    s = re.sub(r"-it$", "", s)
    s = re.sub(r"[^a-z0-9.]", "", s)
    return s


def or_price(m):
    p = m.get("pricing") or {}
    try:
        return float(p.get("prompt", 0)) * 1e6, float(p.get("completion", 0)) * 1e6
    except (TypeError, ValueError, KeyError):
        return None


def ai_price(m):
    c = m.get("cost") or {}
    if c.get("inputPer1M") is None or c.get("outputPer1M") is None:
        return None
    return float(c["inputPer1M"]), float(c["outputPer1M"])


def close(a, b, tol=0.25):
    if a == b:
        return True
    if a <= 0 or b <= 0:
        return False
    return abs(a - b) / max(abs(a), abs(b)) <= tol


def match(ai_m, ors_by_norm):
    """Retorna (or_id, confianca) ou None se nao houver correspondencia inequivoca."""
    na = norm(ai_m["id"])
    exact = ors_by_norm.get(na)
    if exact:
        if len(exact) == 1:
            return exact[0]["id"], 100
        ap = ai_price(ai_m)
        if ap:
            def dist(m):
                op = or_price(m)
                return 9e9 if not op else abs(op[0] - ap[0]) + abs(op[1] - ap[1])
            best = sorted(exact, key=dist)
            if dist(best[0]) < dist(best[1]):
                return best[0]["id"], 95
        return None

    cands = []
    for k, ms in ors_by_norm.items():
        if not k.startswith(na):
            continue
        if not PARAM_SUFFIX.match(k[len(na):]):
            continue
        cands.extend(ms)
    if len(cands) == 1:
        conf = 80
        ap, op = ai_price(ai_m), or_price(cands[0])
        if ap and op and not close(ap[0], op[0]):
            conf = 65          # nome bate por parametros mas preco diverge muito
        return cands[0]["id"], conf
    return None


def main():
    ai = json.load(open(AI))["models"]
    allor = json.load(open(OR))["data"]
    # :free sai do pool (empata com o base e torna todo par ambiguo); :batch e alias
    # ~ nao sao modelos independentes.
    ors = [m for m in allor
           if ":batch" not in m["id"] and not m["id"].startswith("~")
           and not m["id"].endswith(":free")]
    by_norm = {}
    for m in ors:
        by_norm.setdefault(norm(m["id"]), []).append(m)
    by_id = {m["id"]: m for m in ors}

    out, skipped = [], []
    for a in ai:
        hit = match(a, by_norm)
        if not hit:
            skipped.append((a["id"], a["provider"]))
            continue
        oid, conf = hit
        ap, op = ai_price(a), or_price(by_id[oid])
        out.append({
            "aiiq_id": a["id"], "or_id": oid, "confidence": conf,
            "ai_price": ap, "or_price": op,
            "or_vs_table": (round(op[0] / ap[0], 3)
                            if ap and op and ap[0] > 0 and op[0] > 0 else None),
        })

    print(f"AI IQ: {len(ai)} modelos")
    print(f"  mapeados   : {len(out)}  ({100*len(out)/len(ai):.1f}%)")
    print(f"  descartados: {len(skipped)}  (sem correspondencia inequivoca)")
    byconf = {}
    for o in out:
        byconf[o["confidence"]] = byconf.get(o["confidence"], 0) + 1
    print("  por confianca:", dict(sorted(byconf.items(), reverse=True)))

    # guarda-corpo: dois ids do AI IQ nao podem apontar para o mesmo id do OpenRouter
    seen, dup = {}, []
    for o in out:
        if o["or_id"] in seen:
            dup.append((seen[o["or_id"]], o["aiiq_id"], o["or_id"]))
        seen[o["or_id"]] = o["aiiq_id"]
    print(f"  colisoes  : {len(dup)}" + ("" if not dup else f" -> {dup}"))
    if sk := [s[0] for s in skipped[:12]]:
        print(f"  nao mapeados (amostra): {sk}")

    json.dump(out, open("mapping.json", "w"), indent=1)


if __name__ == "__main__":
    main()

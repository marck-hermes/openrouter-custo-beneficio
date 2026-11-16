#!/usr/bin/env python3
"""Mapeia AI IQ -> OpenRouter com verificacao.

Regras aprendidas:
- O AI IQ publica preco de TABELA; o OpenRouter pratica desconto/roteamento proprio.
  Preco divergente NAO invalida o match de nome -- serve como DESEMPATE entre
  candidatos e como sinal de confianca (campo `price_ratio`).
- O OpenRouter acrescenta sufixos de parametros (nemotron-3-ultra-550b-a55b,
  gemma-4-31b-it), entao o id do AI IQ costuma ser PREFIXO do id do OpenRouter.
- Um modelo so recebe notas se o match for inequivoco depois do desempate.
"""
import json, re

AI = "aiiq_v1_models.json"
OR = "or_models.json"

FAMILY = {
    "Anthropic": ["anthropic"], "Google": ["google"], "OpenAI": ["openai"],
    "DeepSeek": ["deepseek"], "Alibaba": ["qwen"], "Z.ai": ["z-ai"],
    "Xiaomi": ["xiaomi"], "Meta": ["meta-llama", "meta"], "xAI": ["x-ai"],
    "MiniMax": ["minimax"], "Kimi": ["moonshotai"],
    "Thinking Machines": ["thinkingmachines"], "NVIDIA": ["nvidia"],
    "Cohere": ["cohere"], "Mistral": ["mistralai"],
}
# para providers "Other", aceita qualquer vendor
OPEN_FAMILIES = {"US (Other)", "China (Other)", "World (Other)"}


def norm(s: str) -> str:
    s = s.lower().replace(":free", "").replace(":batch", "")
    s = re.sub(r"^~", "", s)
    s = s.split("/")[-1]
    s = re.sub(r"^claude-", "", s)
    s = re.sub(r"^(google|openai|anthropic|meta|qwen|nvidia|xiaomi|z-ai|moonshotai)-", "", s)
    s = re.sub(r"-it$", "", s)
    s = re.sub(r"[^a-z0-9.]", "", s)
    return s


def or_price(m):
    p = m.get("pricing") or {}
    try:
        return float(p.get("prompt", 0)) * 1e6, float(p.get("completion", 0)) * 1e6
    except (TypeError, ValueError):
        return None


def ai_price(m):
    c = m.get("cost") or {}
    if c.get("inputPer1M") is None or c.get("outputPer1M") is None:
        return None
    return float(c["inputPer1M"]), float(c["outputPer1M"])


def ratio(a, b):
    """quao distante o preco OR esta do preco de tabela AI IQ (>1 = OR mais barato)"""
    if a <= 0 or b <= 0:
        return None
    return b / a


def score_candidate(ai_m, or_m):
    """confianca do par: nome exato > prefixo; preco proximo reforca."""
    na, no = norm(ai_m["id"]), norm(or_m["id"])
    if na == no:
        s = 100
    elif no.startswith(na) or na.startswith(no):
        s = 80
    else:
        return None
    ap, op = ai_price(ai_m), or_price(or_m)
    if ap and op:
        r = ratio(ap[0], op[0])
        if r is not None:
            # OR nunca deveria ser MUITO mais caro que a tabela; mais barato e normal
            if 0.15 <= r <= 1.5:
                s += 10
            elif r > 3:
                s -= 40          # provavel modelo diferente com nome parecido
    return s


def main():
    ai = json.load(open(AI))["models"]
    ors = [m for m in json.load(open(OR))["data"]
           if ":batch" not in m["id"] and not m["id"].startswith("~")]
    # Variantes :free tem os mesmos pesos do modelo-base. Deixá-las no pool torna
    # `x` e `x:free` empatados e o par vira ambíguo; o custo delas é derivado depois.
    ors_paid = [m for m in ors if not m["id"].endswith(":free")]

    out, skipped, ambig = [], [], []
    for a in ai:
        fam = FAMILY.get(a["provider"], [])
        pool = []
        for m in ors_paid:
            if fam and m["id"].split("/")[0] not in fam and a["provider"] not in OPEN_FAMILIES:
                continue
            sc = score_candidate(a, m)
            if sc is not None:
                pool.append((sc, m))
        if not pool:
            skipped.append((a["id"], a["provider"], "sem nome correspondente"))
            continue
        pool.sort(key=lambda x: -x[0])
        top = pool[0]
        # empate: dois candidatos com mesma confianca e nomes diferentes -> ambiguo
        tied = [m for sc, m in pool if sc == top[0]]
        if len(tied) > 1:
            # desempata por preco mais proximo do de tabela
            ap = ai_price(a)
            if ap:
                def dist(m):
                    op = or_price(m)
                    if not op:
                        return 9e9
                    return abs(op[0] - ap[0]) + abs(op[1] - ap[1])
                tied.sort(key=dist)
                if len(tied) > 1 and dist(tied[0]) == dist(tied[1]):
                    ambig.append((a["id"], [m["id"] for m in tied[:4]]))
                    continue
                chosen = tied[0]
            else:
                ambig.append((a["id"], [m["id"] for m in tied[:4]]))
                continue
        else:
            chosen = top[1]
        if top[0] < 60:
            skipped.append((a["id"], a["provider"], f"match fraco ({chosen['id']})"))
            continue
        ap, op = ai_price(a), or_price(chosen)
        out.append({
            "aiiq_id": a["id"], "or_id": chosen["id"], "confidence": top[0],
            "ai_price": ap, "or_price": op,
            "or_vs_table": (round(op[0] / ap[0], 3) if ap and op and ap[0] > 0 and op[0] > 0 else None),
        })

    print(f"AI IQ: {len(ai)} modelos")
    print(f"  mapeados   : {len(out)}  ({100*len(out)/len(ai):.1f}%)")
    print(f"  ambiguos   : {len(ambig)}")
    print(f"  descartados: {len(skipped)}")
    if ambig:
        print("\nAMBIGUOS:")
        for a, ids in ambig[:10]:
            print(f"  {a:30} -> {ids}")
    print("\nnao mapeados (amostra):", [s[0] for s in skipped[:20]])
    json.dump(out, open("mapping.json", "w"), indent=1)


if __name__ == "__main__":
    main()

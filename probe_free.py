#!/usr/bin/env python3
"""Probe de 10 tokens em cada modelo :free. O dashboard original listou como
melhor gratuito um endpoint que retorna 403 'only available on agentic harnesses'
em chamada direta. Um teste custa ~zero e evita recomendar modelo inutilizavel."""
import json, os, re, urllib.request, urllib.error

KEY = None
for path in ("/home/ubuntu/.hermes/.env",):
    if os.path.exists(path):
        for line in open(path):
            if line.startswith("OPENROUTER_API_KEY="):
                KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
if not KEY:
    KEY = os.environ.get("OPENROUTER_API_KEY")
assert KEY, "sem OPENROUTER_API_KEY"

src = json.load(open("or_models.json"))["data"]
frees = [m["id"] for m in src
         if m["id"].endswith(":free")]
print(f"probes: {len(frees)} endpoints :free\n")


def probe(model):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ok"}],
        "max_tokens": 4,
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r:
            j = json.load(r)
        u = j.get("usage") or {}
        msg = (j.get("choices") or [{}])[0].get("message") or {}
        txt = msg.get("content") or ""
        if not txt and msg.get("reasoning"):
            txt = "[reasoning]"
        return "ok", (txt or "[empty]")[:16], u.get("prompt_tokens")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(raw)["error"]["message"]
        except Exception:
            msg = raw[:120]
        if "agentic harness" in msg:
            return "gated", "agentic-harness", None
        if e.code == 429:
            return "rate-limited", msg[:60], None
        return f"http-{e.code}", msg[:70], None
    except Exception as e:
        return "error", str(e)[:60], None


results = []
for m in frees:
    st, detail, pt = probe(m)
    results.append({"model": m, "status": st, "detail": detail})
    print(f"  {st:14} {m:48} {detail}")

json.dump(results, open("free_probe.json", "w"), indent=1)
ok = [r for r in results if r["status"] == "ok"]
print(f"\nchamáveis: {len(ok)}/{len(results)}")

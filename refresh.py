#!/usr/bin/env python3
"""Atualiza o dashboard "OpenRouter: custo x beneficio" semanalmente.

Cada passo fecha ou falha com um motivo declarado:
  1. OpenRouter (catalogo de modelos + precos)
  2. AI IQ (notas — a unica fonte de capacidade usada no dashboard)
  3. mapping.json (join AI IQ -> OpenRouter por identidade, nunca por valor)
  4. free_probe.json (probe de 4 tokens em cada :free, com chave autenticada)
  5. arena_elo.json + model_speed.json (sinais da tabela antiga, portados)
  6. guarded excluded.json (gerado no step 6/7 junto com index.html)
  7. regenera index.html com generate.py
  8. git push -> Vercel

Uso:
  python3 refresh.py             # tudo, inclusive probe e deploy
  python3 refresh.py --skip-probe --skip-deploy   # refresh barato, so gera
  python3 refresh.py --no-deploy                  # gera mas nao publica
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
import datetime
from pathlib import Path

REPO = Path(__file__).parent
DATA = REPO / "data"
DATA.mkdir(exist_ok=True)
ENV_PATH = os.path.expanduser("~/.hermes/.env")
TOKEN_DASHBOARD = Path("/home/ubuntu/token-dashboard")
UA = {"User-Agent": "Hermes-Agent/1.0"}
TIMEOUT = 60


def log(msg):
    print(msg, flush=True)


def fetch_json(url, timeout=TIMEOUT, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def openrouter_key():
    env = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env:
        return env
    try:
        for line in open(ENV_PATH, encoding="utf-8"):
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


def step_openrouter():
    doc = fetch_json("https://openrouter.ai/api/v1/models")
    (DATA / "or_models.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    log(f"1. OpenRouter: {len(doc['data'])} modelos")
    return len(doc["data"])


def step_aiiq():
    doc = fetch_json("https://www.aiiq.org/api/v1/models")
    (DATA / "aiiq_v1_models.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    log(f"2. AI IQ: {len(doc['models'])} modelos")
    return len(doc["models"])


def step_mapping():
    subprocess.run([sys.executable, str(REPO / "build_map.py")],
                   cwd=DATA, check=True)


def step_probe(skip_probe=False):
    src = json.loads((DATA / "or_models.json").read_text(encoding="utf-8"))["data"]
    ids = [m["id"] for m in src if m["id"].endswith(":free")]
    cached = {r["model"]: r for r in json.loads((DATA / "free_probe.json").read_text(encoding="utf-8"))} \
        if (DATA / "free_probe.json").exists() else {}

    if skip_probe:
        if (DATA / "free_probe.json").exists():
            results = json.loads((DATA / "free_probe.json").read_text(encoding="utf-8"))
            usable = sum(1 for r in results if r.get("status") in ("ok", "agentic"))
            log(f"4. Probe ignorado; usando cache ({usable}/{len(results)} utilizaveis)")
            return results
        log("4. Probe ignorado e sem cache; saindo da lista vazia")
        return []

    key = openrouter_key()
    if not key:
        log("4. PROBE IGNORADO: sem OPENROUTER_API_KEY (reutilizando cache)")
        return [cached[i] for i in ids if i in cached]

    def probe(model):
        body = json.dumps({"model": model,
                           "messages": [{"role": "user", "content": "ok"}],
                           "max_tokens": 4}).encode()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "User-Agent": "Hermes-Agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                j = json.load(resp)
            ch = (j.get("choices") or [{}])[0]
            txt = ((ch.get("message") or {}).get("content") or "").strip()
            if not txt and (ch.get("message") or {}).get("reasoning"):
                txt = "[reasoning]"
            return "ok", (txt or "[empty]")[:16], None
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

    # O gate do inkling-2-small:free e "agentic harness" — este script nao e um
    # agente. Preserva a verificacao humana de que ele responde (esta sessao roda
    # nele) em vez de rebaixar para "gated" silenciosamente.
    AGENTIC_VERIFIED = {"thinkingmachines/inkling-2-small:free"}

    results = []
    for mid in ids:
        if mid in cached and cached[mid].get("verified_by") == "human":
            res = cached[mid]
        else:
            st, detail, _ = probe(mid)
            res = {"model": mid, "status": st, "detail": detail}
            if mid in AGENTIC_VERIFIED and st == "gated":
                res["status"] = "agentic"
                res["detail"] = ("curl direto 403 (gate agentic-harness); "
                                 "verificado pelo usuario como respondendo em sessao agente")
                res["verified_by"] = "human"
        results.append(res)
        log(f"   {res['status']:12} {res['model']}")
        time.sleep(0.3)
    (DATA / "free_probe.json").write_text(json.dumps(results, indent=1, ensure_ascii=False),
                                          encoding="utf-8")
    ok = sum(1 for r in results if r["status"] in ("ok", "agentic"))
    log(f"4. Probe: {ok}/{len(results)} endpoints :free utilizaveis")
    return results



def fetch_models():
    return json.loads((DATA / "or_models.json").read_text(encoding="utf-8"))["data"]


def step_arena():
    sys.path.insert(0, str(TOKEN_DASHBOARD / "scripts"))
    try:
        import update_llm_comparison as U
    except Exception as exc:
        log(f"6. Arena Elo: modulo nao carregado ({exc}); mantendo cache atual")
        return
    try:
        table = U.fetch_arena_elo()
        payload = {"fetched_at": datetime.datetime.now().isoformat(), "models": table}
        (DATA / "arena_elo.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                             encoding="utf-8")
        log(f"6. Arena Elo: {len(table)} modelos (HF rows)")
    except Exception as exc:
        if (DATA / "arena_elo.json").exists():
            cached = json.loads((DATA / "arena_elo.json").read_text(encoding="utf-8"))
            log(f"6. Arena Elo: falha ({exc}); mantendo cache de {cached.get('fetched_at', '?')[:16]}")
        else:
            log(f"6. Arena Elo: falha e sem cache ({exc})")


def step_speed():
    sys.path.insert(0, str(TOKEN_DASHBOARD / "scripts"))
    try:
        import update_llm_comparison as U
        selected = {m["id"]: m for m in fetch_models()}
        speed = U.load_speed_data(selected, refresh=False)
        (DATA / "model_speed.json").write_text(json.dumps(speed, indent=2, ensure_ascii=False),
                                               encoding="utf-8")
        log(f"6. Velocidade: {len(speed)} modelos (recarrega apenas >7d)")
    except Exception as exc:
        log(f"6. Velocidade: falha ({exc}); mantendo cache")


def step_flex_pricing():
    """Busca preços Flex para modelos da tabela (IQ >= 100)."""
    rows_path = DATA / "data.json"
    if not rows_path.exists():
        log("Flex pricing: data.json não existe, pulando")
        return
    rows = json.loads(rows_path.read_text(encoding="utf-8"))
    oids = {r["id"] for r in rows}
    key = openrouter_key()
    if not key:
        log("Flex pricing: sem API key, pulando")
        return

    flex = {}
    for oid in oids:
        try:
            url = f"https://openrouter.ai/api/v1/models/{urllib.parse.quote(oid)}/endpoints"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}", **UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)

            best_flex = None
            for ep in data.get("data", {}).get("endpoints", []):
                if ep.get("service_tier") == "flex":
                    p = ep.get("pricing", {})
                    in_p = float(p.get("prompt", 0)) * 1e6
                    out_p = float(p.get("completion", 0)) * 1e6
                    cache_p = float(p.get("input_cache_read", 0)) * 1e6
                    if best_flex is None or in_p < best_flex["in"]:
                        best_flex = {"in": in_p, "out": out_p, "cache": cache_p, "provider": ep["provider_name"]}

            if best_flex:
                flex[oid] = best_flex
            time.sleep(0.2)  # be nice
        except Exception as e:
            log(f"  Flex {oid}: {e}")

    (DATA / "flex_pricing.json").write_text(json.dumps(flex, ensure_ascii=False), encoding="utf-8")
    log(f"Flex pricing: {len(flex)}/{len(oids)} modelos com Flex")


def step_generate():
    env = os.environ.copy()
    env["DASH_DATA"] = str(DATA)
    env["DASH_ROWS"] = str(REPO / "data.json")
    env["DASH_HTML"] = str(REPO / "index.html")
    subprocess.run([sys.executable, str(REPO / "generate.py")], cwd=DATA, env=env, check=True)


GIT_USER = ("-c", "user.email=marck@hermes.local", "-c", "user.name=marck-hermes")

# O token-dashboard é um deploy 2s baseado em push para o branch padrão do repo:
# o projeto está ligado como "Other/static" com Vercel git integration; .vercel/project.json
# tem outputDirectory="." e o projeto NÃO depende mais do deploy.sh/npx vercel --prod
# (que quebra com múltiplas chamadas aguardadas). Por isso promoção = git push, não CLI.
def step_deploy():
    status = subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True)
    if not status.stdout.strip():
        log("8. nada a commitar; branch já está sincronizado, sem deploy")
        return True
    subprocess.run(["git", "add", "-A"], cwd=REPO, check=True)
    subprocess.run(["git", "-c", "user.email=marck@hermes.local",
                    "-c", "user.name=marck-hermes",
                    "commit", "-q", "-m",
                    f"chore: update dashboard ({datetime.date.today().isoformat()})"],
                   cwd=REPO, check=True)
    push = subprocess.run(["git", "push", "origin", "master"], cwd=REPO,
                          capture_output=True, text=True)
    if push.returncode != 0:
        log(f"8. git push FALHOU: {push.stderr.strip()[:300]}")
        return False
    log("8. git push: ok (Vercel faz deploy automático; o projeto está ligado ao branch)")
    return True


def main():
    skip_probe = "--skip-probe" in sys.argv
    no_deploy = "--no-deploy" in sys.argv
    skip_deploy = "--skip-deploy" in sys.argv or no_deploy

    log(f"== OpenRouter: custo x beneficio — refresh {datetime.date.today().isoformat()} ==")
    step_openrouter()
    step_aiiq()
    step_mapping()
    step_probe(skip_probe=skip_probe)
    step_arena()
    step_speed()
    step_flex_pricing()
    step_generate()
    if skip_deploy:
        log("8. deploy ignorado (--skip-deploy)")
        return 0
    ok = step_deploy()
    log("== done ==" if ok else "== refresh ok, deploy FALHOU ==")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

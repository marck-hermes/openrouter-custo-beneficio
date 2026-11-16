#!/usr/bin/env python3
"""Gera o dashboard de custo x beneficio para o Hermes Agent.

Decisoes que nao sao obvias e o porque:

1. JOIN: notas do AI IQ ligadas ao OpenRouter por NOME normalizado (identidade),
   nunca pela propria nota. A versao original fazia join pela nota e seis modelos
   de familias diferentes herdaram as 8 notas e o custo do `o1`.

2. CUSTO: tres baldes reais de token. O Hermes grava `input_tokens` JA LIQUIDO de
   cache (`agent/usage_pricing.py`: input = prompt - cache_read - cache_write), entao
   o modelo precisa de nao-cacheado + cache-read + saida separados.

3. MIX NO CLIENTE: o custo e recalculado no navegador a partir dos precos, com um
   seletor de % de cache e % de saida. Assim a sensibilidade e visivel, nao apenas
   afirmada. Os valores iniciais vem do uso real medido (30 dias).

4. FILTRO DE IQ: filtra a EXIBICAO, nunca a nota exibida. Um `iq` vindo do
   benchmark e imutavel qualquer que seja o filtro -- filtrar reescrevendo a nota
   seria o mesmo pecado do dashboard original.

5. Modelo sem nota continua visivel: `-` e honesto, omissao nao e.
"""
import json, datetime, statistics, os

# Mix medido em ~/.hermes/state.db, janela de 30 dias, chamadas reais do agente.
MIX = {"uncached_in_M": 18.62, "cache_read_M": 105.89, "out_M": 0.657, "calls": 1279}

ors = {m["id"]: m for m in json.load(open("or_models.json"))["data"]}
mp = {x["or_id"]: x for x in json.load(open("mapping.json"))}
aiiq = {m["id"]: m for m in json.load(open("aiiq_v1_models.json"))["models"]}
probe = {r["model"]: r for r in json.load(open("free_probe.json"))}


def pricing(m):
    p = m.get("pricing") or {}

    def f(k):
        v = p.get(k)
        if v in (None, ""):
            return None
        try:
            return float(v) * 1e6
        except (TypeError, ValueError):
            return None
    return {"in": f("prompt"), "out": f("completion"),
            "cache_read": f("input_cache_read"), "cache_write": f("input_cache_write")}


def monthly(pr):
    if not pr or pr["in"] is None or pr["out"] is None or pr["cache_read"] is None:
        return None
    return (MIX["uncached_in_M"] * pr["in"] + MIX["cache_read_M"] * pr["cache_read"]
            + MIX["out_M"] * pr["out"])


def prompt_blend(pr):
    if not pr or pr["in"] is None or pr["cache_read"] is None:
        return None
    tot = MIX["uncached_in_M"] + MIX["cache_read_M"]
    return (MIX["uncached_in_M"] * pr["in"]
            + MIX["cache_read_M"] * pr["cache_read"]) / tot


def build_row(oid, aiiq_id, free=False):
    m = ors.get(oid)
    am = aiiq.get(aiiq_id) if aiiq_id else None
    if not m:
        return None
    d = (am or {}).get("dimensions") or {}
    pr = pricing(m)

    # Modelo sem preco de cache publicado: usa o preco de ENTRADA como pior caso
    # (nenhum desconto de cache), em vez de omitir a linha. Omitir tirava do
    # catalogo modelos com IQ 100-110 (gemma-4-31b, nemotron-3-super-120b,
    # qwen3.6-plus/27b); estimar sem avisar seria pior. A linha carrega a marca
    # `cacheEst` e a UI mostra isso explicitamente.
    cache_est = False
    if pr["cache_read"] is None and pr["in"] is not None:
        pr["cache_read"] = pr["in"]
        cache_est = True

    cost = 0.0 if free else monthly(pr)
    if cost is None:
        return None
    reason = m.get("reasoning") or {}
    return {
        "id": oid, "name": (m.get("name") or oid),
        "provider": oid.split("/")[0],
        "aiiq": aiiq_id,
        "iq": (am or {}).get("iq"), "cu": d.get("computer-use"),
        "code": d.get("programmatic-reasoning"), "rel": d.get("reliability"),
        "kw": d.get("knowledge-work"), "abs": d.get("abstract-reasoning"),
        "math": d.get("mathematical-reasoning"), "acad": d.get("academic-reasoning"),
        "ctx": m.get("context_length") or 0,
        "maxout": (m.get("top_provider") or {}).get("max_completion_tokens") or 0,
        "inP": pr["in"], "outP": pr["out"], "cacheP": pr["cache_read"],
        "cacheEst": cache_est,
        "cost": cost, "per1m": (0.0 if free else (prompt_blend(pr) or 0.0)),
        "tools": "tools" in (m.get("supported_parameters") or []),
        "rmand": bool(reason.get("mandatory")),
        "free": free,
        "modality": (m.get("architecture") or {}).get("modality") or "",
        "coverage": ((am or {}).get("iqCoverage") or {}).get("directDimensions", 0),
    }


rows = []
for oid, a in mp.items():
    r = build_row(oid, a["aiiq_id"])
    if r:
        rows.append(r)

# Gratuitos confirmados por probe. Herdam as notas do modelo-base quando existir.
seen = {r["id"] for r in rows}
for fid, pf in probe.items():
    if pf["status"] != "ok" or fid in seen or fid not in ors:
        continue
    base = mp.get(fid[:-5])
    r = build_row(fid, base["aiiq_id"] if base else None, free=True)
    if r:
        rows.append(r)

rows.sort(key=lambda r: (r["cost"], -(r["cu"] or 0)))

# ---------------------------------------------------------------------------
# Transparencia: o que NAO entrou. Sem esta secao o dashboard da a impressao de
# que o catalogo tem 135 modelos, quando o OpenRouter lista 467. O usuario
# precisa poder auditar a exclusao, nao so confiar nela.
# ---------------------------------------------------------------------------
allor_list = json.load(open("or_models.json"))["data"]
excluded = json.load(open("excluded.json"))
_neg = sum(1 for m in allor_list
           if float((m.get("pricing") or {}).get("prompt", 0) or 0) < 0)
_n_batch = sum(1 for m in allor_list if ":batch" in m["id"])
_n_alias = sum(1 for m in allor_list if m["id"].startswith("~"))
_n_freev = sum(1 for m in allor_list if m["id"].endswith(":free"))
_n_total = len(allor_list)
# 467 - batch - alias - routers = modelos unicos (pagos + variantes :free)
_n_unique = _n_total - _n_batch - _n_alias - _neg
_n_paid_indep = _n_unique - _n_freev
_n_rows = len(rows)
_n_rows_free = sum(1 for r in rows if r["free"])
_n_rows_paid = _n_rows - _n_rows_free
_n_excl = len(excluded)
_n_free_ok = _n_rows_free
_n_free_excl = _n_freev - _n_free_ok

# O funil so vale se fechar. Uma soma que nao fecha e pior que nao ter funil.
assert _n_paid_indep == _n_rows_paid + _n_excl, (
    f"funil nao fecha: {_n_paid_indep} pagos independentes != "
    f"{_n_rows_paid} analisados + {_n_excl} excluidos")
assert _n_freev == _n_free_ok + _n_free_excl, "funil de :free nao fecha"

EXCL_REASON = (
    "Estes modelos existem no OpenRouter mas <b>nao tem nota no AI IQ</b> &mdash; "
    "em muitos casos porque sao modelos antigos ou pequenos que o AI IQ nunca avaliou. "
    "Sem nota de capacidade nao ha como calcular capacidade por dolar, entao eles ficam "
    "fora do ranking. O preco e o contexto <b>sao</b> conhecidos e estao listados: "
    "se voce ja sabe que um deles serve, o custo mensal dele e calculavel."
)
EXCL_DATA = json.dumps(excluded, ensure_ascii=False)

CUS = sorted(r["cu"] for r in rows if r["cu"] is not None)
MED_CU = statistics.median(CUS) if CUS else 0
LEAD_CU = max(CUS) if CUS else 0
N_GRADED = len(CUS)

# Piso do ranking de valor = mediana. Um piso de 60% do lider (94 pontos) ainda
# admitia modelo no percentil 12 liderando -- o defeito original em escala menor.
FLOOR = round(MED_CU)

mix_cache = 100 * MIX["cache_read_M"] / (MIX["uncached_in_M"] + MIX["cache_read_M"] + MIX["out_M"])
mix_out = 100 * MIX["out_M"] / (MIX["uncached_in_M"] + MIX["cache_read_M"] + MIX["out_M"])
now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

limits = (
    f"Dos {len(aiiq)} modelos do AI IQ, {len(mp)} foram ligados a um id do OpenRouter por "
    f"nome exato (ou exato + parametros de tamanho); {len(rows)} entram na tabela. "
    f"{sum(1 for r in rows if r.get('cacheEst'))} modelos nao publicam preco de cache e usam o preco de "
    f"entrada como pior caso (marcados <b>cache~</b> na tabela) &mdash; o custo real deles tende a ser menor. "
    f"{len(probe)} endpoints <code>:free</code> foram testados um a um &mdash; "
    f"{sum(1 for p in probe.values() if p['status']=='ok')} respondem, "
    f"{sum(1 for p in probe.values() if p['status']=='gated')} esta bloqueado por politica de harness "
    f"e {sum(1 for p in probe.values() if p['status']=='rate-limited')} estava limitado por taxa no momento do teste. "
    f"Modelos sem nota exibem travessao: nao sao excluidos nem recebem estimativa."
)

DATA = json.dumps(rows, ensure_ascii=False)

TMPL = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenRouter: custo x beneficio (Hermes)</title>
<style>
  *{box-sizing:border-box}
  body{font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1c2530}
  header{background:#14213d;color:#fff;padding:22px 20px}
  header h1{margin:0 0 6px;font-size:21px}
  header p{margin:0;opacity:.85;font-size:12.5px;line-height:1.6}
  main{max-width:1180px;margin:0 auto;padding:16px}
  .stats{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
  .stat{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:11px 15px;flex:1;min-width:140px}
  .stat b{display:block;font-size:21px}
  .stat span{font-size:11.5px;color:#5b6b7c;line-height:1.4;display:block;margin-top:2px}
  .card{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:16px;margin-bottom:16px}
  .card h2{margin:0 0 4px;font-size:16.5px}
  .card p.sub{margin:0 0 12px;font-size:12.5px;color:#5b6b7c;line-height:1.6}
  .mixbox{background:#f7f9fc;border:1px solid #dde3ea;border-radius:8px;padding:12px 14px;margin-bottom:14px}
  .mixgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px 22px}
  .mixrow label{display:flex;justify-content:space-between;font-size:12.5px;color:#39485a;margin-bottom:4px}
  .mixrow label b{color:#0b5fff;font-variant-numeric:tabular-nums}
  .mixrow input[type=range]{width:100%;accent-color:#0b5fff}
  .mixactions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:10px}
  .mixactions button{padding:6px 11px;border:1px solid #c6d0dc;background:#fff;border-radius:6px;
    font-size:12px;cursor:pointer;color:#39485a}
  .mixactions button:hover{border-color:#0b5fff;color:#0b5fff}
  .mixactions .hint{font-size:11.5px;color:#8a97a5}
  .filters{display:flex;flex-wrap:wrap;gap:10px;align-items:end}
  .filters label{font-size:11.5px;color:#5b6b7c;display:block;margin-bottom:3px}
  .filters input,.filters select{padding:7px;border:1px solid #c6d0dc;border-radius:6px;font-size:13.5px;background:#fff}
  .filters .check{display:flex;align-items:center;gap:6px;padding-bottom:7px;font-size:13.5px}
  #chart{width:100%;height:400px;display:block;cursor:crosshair}
  #tip{position:absolute;background:#14213d;color:#fff;padding:8px 10px;border-radius:6px;font-size:12px;
       pointer-events:none;display:none;max-width:300px;line-height:1.5;z-index:5}
  .legend{font-size:12px;color:#5b6b7c;margin-top:6px;line-height:1.9}
  .legend i{display:inline-block;width:10px;height:10px;border-radius:50%;margin:0 4px 0 12px;vertical-align:middle}
  table{width:100%;border-collapse:collapse;font-size:12.5px}
  th{text-align:left;padding:8px 6px;border-bottom:2px solid #dde3ea;cursor:pointer;white-space:nowrap;user-select:none}
  th:hover{color:#0b5fff}
  th.sorted{background:#e7efff;color:#0b5fff}
  td{padding:7px 6px;border-bottom:1px solid #eef1f4;vertical-align:top}
  td.num,th.num{text-align:right}
  td.sorted{background:#f0f6ff}
  .tag{display:inline-block;background:#e3f2e6;color:#1d7a33;border-radius:20px;padding:1px 7px;font-size:11px;font-weight:600}
  .warn{display:inline-block;background:#fdf0d5;color:#8a5a00;border-radius:20px;padding:1px 7px;font-size:11px;font-weight:600}
  .muted{color:#8a97a5}
  .rowlink{cursor:pointer}
  .rowlink:hover td{background:#f2f7ff}
  .sortbtn{padding:7px 12px;border:1px solid #0b5fff;background:#fff;color:#0b5fff;border-radius:6px;
           font-size:13px;cursor:pointer;margin-bottom:12px}
  .sortbtn.armed{background:#0b5fff;color:#fff}
  #detail{font-size:13.5px;line-height:1.7}
  #detail b{font-size:15px}
  .dims{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:6px 18px;margin-top:8px}
  .dims div{display:flex;justify-content:space-between;border-bottom:1px dashed #e2e7ec;padding:3px 0;font-size:13px}
  .note{background:#fff8e6;border:1px solid #f0dfa8;border-radius:8px;padding:12px 14px;font-size:12.5px;line-height:1.7;color:#5a4300}
  .note b{color:#3d2d00}
  .funnel{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:10px 0}
  .fitem{background:#f7f9fc;border:1px solid #dde3ea;border-radius:8px;padding:9px 13px;min-width:96px;text-align:center}
  .fitem b{display:block;font-size:19px;line-height:1.2}
  .fitem span{font-size:11px;color:#5b6b7c;display:block;margin-top:3px;max-width:150px;line-height:1.35}
  .fitem.good{background:#e9f6ec;border-color:#b9dfc2}
  .fitem.good b{color:#1d7a33}
  .fitem.bad{background:#fdeeee;border-color:#f0c4c4}
  .fitem.bad b{color:#a11}
  .farrow{font-size:17px;color:#9aa7b4;font-weight:600}
  footer{font-size:11.5px;color:#8a97a5;padding:0 16px 28px;max-width:1180px;margin:0 auto;line-height:1.8}
</style>
</head>
<body>
<header>
  <h1>OpenRouter: custo x beneficio &mdash; Hermes Agent</h1>
  <p>Custo recalculado ao vivo com o <b>mix real de tokens do Hermes</b>: __MIX_TXT__.<br>
  Notas do AI IQ ligadas ao modelo certo por nome. Dados de __NOW__.</p>
</header>
<main>

  <div class="stats">
    <div class="stat"><b id="stTotal">-</b><span>modelos com preco calculavel</span></div>
    <div class="stat"><b id="stGraded">-</b><span>com score agentico</span></div>
    <div class="stat"><b id="stFree">-</b><span>gratuitos que respondem (probe)</span></div>
    <div class="stat"><b id="stShown">-</b><span>visiveis apos filtros</span></div>
    <div class="stat"><b>__MED__</b><span>mediana do score agentico</span></div>
  </div>

  <div class="card">
    <h2>Mix de tokens</h2>
    <p class="sub">O custo de cada modelo e recalculado aqui, no navegador, a partir dos precos reais.
    Os valores iniciais sao os medidos em 30 dias de uso do Hermes. Arraste para ver como a conclusao
    muda &mdash; ou nao muda &mdash; com um perfil de uso diferente.</p>
    <div class="mixbox">
      <div class="mixgrid">
        <div class="mixrow">
          <label>Cache read <b><span id="vCache">__MC__</span>%</b></label>
          <input type="range" id="rCache" min="0" max="95" step="1" value="__MC__">
        </div>
        <div class="mixrow">
          <label>Saida <b><span id="vOut">__MO__</span>%</b></label>
          <input type="range" id="rOut" min="0.2" max="10" step="0.1" value="__MO__">
        </div>
      </div>
      <div class="mixactions">
        <button id="btnReal" type="button">Mix medido</button>
        <button id="btnNoCache" type="button">Sem cache</button>
        <button id="btnCacheMax" type="button">Cache maximo</button>
        <span class="hint" id="mixNote"></span>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="note">
      <b>O que mudou em relacao ao dashboard anterior.</b> A coluna "custo efetivo" do arquivo original
      estava errada em <b>212 de 250</b> linhas: era uma media de entrada e saida que caia <i>fora</i> do
      intervalo dos dois precos, porque o join ligava as notas pela propria nota e seis modelos de
      familias diferentes herdaram as notas do <code>o1</code>. Aqui cada linha e ligada por nome, e o
      custo usa os tres baldes de token que o Hermes realmente gasta.
    </div>
  </div>

  <div class="card">
    <h2>Custo x capacidade agentica</h2>
    <p class="sub">Cada ponto e um modelo. Eixo horizontal: custo mensal em US$ (escala log) no mix atual.
    Eixo vertical: score de <i>computer use</i> do AI IQ. Pontos dourados sao os 10 melhores custo-beneficio.
    Clique para o detalhe.</p>
    <div style="position:relative"><canvas id="chart"></canvas><div id="tip"></div></div>
    <div class="legend">
      <i style="background:#0b5fff"></i>pago
      <i style="background:#1d9e4b"></i>gratuito
      <i style="background:#e0a100"></i>melhor custo-beneficio (top 10)
      <i style="background:#a11"></i>abaixo da mediana agentica
    </div>
  </div>

  <div class="card" id="detailCard" style="display:none">
    <h2>Detalhe do modelo</h2>
    <div id="detail"></div>
  </div>

  <div class="card">
    <h2>Melhor custo-beneficio para agente</h2>
    <p class="sub">Score agentico por dolar, com piso de capacidade na <b>mediana do catalogo (__MED__)</b>.
    Um piso frouxo repetiria o erro anterior em escala menor &mdash; com 60% do lider, um modelo no
    percentil 12 ainda liderava. Os valores acompanham o mix escolhido acima.</p>
    <div style="overflow-x:auto">
    <table id="valueTable"><thead><tr>
      <th>#</th><th>Modelo</th><th class="num">Agente</th><th class="num">Posicao</th>
      <th class="num">IQ</th><th class="num">US$/mes</th><th class="num">US$/1M prompt</th><th class="num">Contexto</th>
    </tr></thead><tbody></tbody></table>
    </div>
  </div>

  <div class="card">
    <h2>Gratuitos que realmente respondem</h2>
    <p class="sub">Cada <code>:free</code> recebeu um probe de 10 tokens. O candidato que a versao anterior
    coroou como melhor gratuito (<code>inkling-2-small:free</code>, IQ 126) retorna
    <b>403 "only available on agentic harnesses"</b> em chamada direta e foi removido &mdash; o gate e do
    provider, nao um header que se possa imitar.</p>
    <div style="overflow-x:auto">
    <table id="freeTable"><thead><tr>
      <th>#</th><th>Modelo</th><th class="num">Agente</th><th class="num">IQ</th>
      <th class="num">Codigo</th><th class="num">Contexto</th><th>Status</th>
    </tr></thead><tbody></tbody></table>
    </div>
  </div>

  <div class="card">
    <h2>O que ficou de fora (e por que)</h2>
    <p class="sub">O catalogo do OpenRouter tem <b>__NTOTAL__</b> entradas. Esta tabela analisa
    <b>__NROWS__</b>. A diferenca nao e um filtro escondido: cada exclusao tem um motivo declarado.</p>
    <div class="funnel">
      <div class="fitem"><b>__NTOTAL__</b><span>entradas no catalogo</span></div>
      <div class="farrow">&minus;</div>
      <div class="fitem"><b>__NBATCH__</b><span>variantes <code>:batch</code> (mesmo modelo, com desconto)</span></div>
      <div class="farrow">&minus;</div>
      <div class="fitem"><b>__NALIAS__</b><span>aliases <code>~</code> (apontam para outro)</span></div>
      <div class="farrow">&minus;</div>
      <div class="fitem"><b>__NROUTERS__</b><span>routers com preco negativo</span></div>
      <div class="farrow">=</div>
      <div class="fitem"><b>__NUNIQ__</b><span>modelos unicos</span></div>
      <div class="farrow">&minus;</div>
      <div class="fitem"><b>__NFREE__</b><span>variantes <code>:free</code> (mesmo modelo)</span></div>
      <div class="farrow">=</div>
      <div class="fitem"><b>__NPAID__</b><span>modelos pagos independentes</span></div>
    </div>
    <div class="funnel" style="margin-top:4px">
      <div class="fitem good"><b>__NPAIDROWS__</b><span>pagos analisados</span></div>
      <div class="farrow">+</div>
      <div class="fitem good"><b>__NFREEOK__</b><span>gratuitos que respondem</span></div>
      <div class="farrow">=</div>
      <div class="fitem good"><b>__NROWS__</b><span>na tabela</span></div>
      <div class="farrow">|</div>
      <div class="fitem bad"><b>__NEXCL__</b><span>pagos sem nota no AI IQ</span></div>
      <div class="farrow">+</div>
      <div class="fitem bad"><b>__NFREEBAD__</b><span>gratuitos que nao respondem</span></div>
    </div>
    <div class="note" style="margin-top:14px">__EXCLREASON__</div>
    <details style="margin-top:12px">
      <summary style="cursor:pointer;font-size:13px;color:#0b5fff">Ver os __NEXCL__ modelos sem nota</summary>
      <div style="overflow-x:auto;margin-top:10px">
      <table id="exclTable"><thead><tr>
        <th data-e="id">Modelo</th><th data-e="inP" class="num">Entrada US$/1M</th>
        <th data-e="outP" class="num">Saida US$/1M</th><th data-e="ctx" class="num">Contexto</th><th>Ferramentas</th>
      </tr></thead><tbody></tbody></table>
      </div>
    </details>
  </div>

  <div class="card">
    <h2>Todos os modelos</h2>
    <p class="sub">Clique no cabecalho para ordenar; "&#65291; 2&ordf; coluna" ou Shift+clique para uma segunda
    ordenacao (no celular, toque e segure). Clique na linha para o detalhe.
    O filtro de IQ esconde linhas &mdash; nunca altera a nota exibida.</p>
    <button class="sortbtn" id="multiBtn" type="button">&#65291; 2&ordf; coluna</button>
    <div class="filters" style="margin-bottom:12px">
      <div><label>Buscar</label><input id="fSearch" type="text" placeholder="nome, id ou provedor" style="width:190px"></div>
      <div><label>Provedor</label><select id="fProvider"><option value="">Todos</option></select></div>
      <div><label>IQ minimo</label><input id="fMinIq" type="number" min="0" max="200" placeholder="ex.: 100" style="width:95px"></div>
      <div><label>Agente minimo</label><input id="fMinCu" type="number" min="0" max="200" placeholder="ex.: 110" style="width:100px"></div>
      <div><label>US$/mes maximo</label><input id="fMaxCost" type="number" min="0" step="0.5" placeholder="ex.: 5" style="width:105px"></div>
      <div class="check"><input id="fFree" type="checkbox"><span>So gratuitos</span></div>
      <div class="check"><input id="fTools" type="checkbox" checked><span>Exigir function calling</span></div>
      <div class="check"><input id="fNoIq" type="checkbox" checked><span>Manter sem nota</span></div>
    </div>
    <div style="overflow-x:auto">
    <table id="mainTable">
      <thead><tr>
        <th data-k="name">Modelo</th><th data-k="provider">Provedor</th>
        <th data-k="cu" class="num">Agente</th><th data-k="iq" class="num">IQ</th>
        <th data-k="code" class="num">Codigo</th><th data-k="rel" class="num">Confiab.</th>
        <th data-k="costNow" class="num">US$/mes</th><th data-k="per1mNow" class="num">US$/1M prompt</th>
        <th data-k="inP" class="num">Entrada</th><th data-k="outP" class="num">Saida</th>
        <th data-k="ctx" class="num">Contexto</th>
      </tr></thead>
      <tbody></tbody>
    </table>
    </div>
  </div>
</main>
<footer>
  <b>Fontes.</b> Notas e precos de tabela: API publica do AI IQ (<code>www.aiiq.org/api/v1/models</code>,
  metodologia 2026-09-30-arc-predictive-puzzles). Precos praticados, contexto e ferramentas:
  <code>openrouter.ai/api/v1/models</code>. Ambas em __NOW__.<br>
  <b>Custo mensal.</b> __MIX_TXT__. O Hermes grava <code>input_tokens</code> ja liquido de cache
  (<code>agent/usage_pricing.py</code>: <code>input_tokens = prompt_total - cache_read - cache_write</code>),
  por isso sao tres baldes. O calculo no navegador usa os precos por token de cada linha; o volume total
  e fixo e apenas a <i>distribuicao</i> muda com os sliders.<br>
  <b>Limitacoes.</b> __LIMITS__<br>
  <b>Colunas derivadas.</b> "Agente" = <code>computer-use</code> do AI IQ. "Posicao" = percentil entre os
  __N__ modelos com essa dimensao. "US$/1M prompt" = custo medio por milhao de tokens de prompt ja ponderado
  pelo cache &mdash; comparavel entre modelos, ao contrario da media bruta de entrada e saida.
</footer>
<script>
const DATA = __DATA__;
const MED_CU = __MED__;
const N_GRADED = __N__;
const FLOOR = __FLOOR__;
const REAL = {cache: __MC__, out: __MO__};

// Volume de referencia = carga real do Hermes em 30 dias, para que o numero na tela
// seja o gasto mensal de verdade e nao um indice arbitrario. So a DISTRIBUICAO muda
// com os sliders; o volume total de prompt fica fixo, entao os modelos seguem comparaveis.
const BASE_PROMPT_M = __BASEP__;
function computeCost(r, pCache, pOut){
  if (r.free) return 0;
  if (r.inP == null || r.cacheP == null || r.outP == null) return null;
  const promptM = BASE_PROMPT_M;
  const outM = pOut >= 100 ? 0 : promptM * (pOut / (100 - pOut));
  const unc = promptM * (1 - pCache / 100);
  const cac = promptM * (pCache / 100);
  return unc * r.inP + cac * r.cacheP + outM * r.outP;
}
function computePer1m(r, pCache){
  if (r.free) return 0;
  if (r.inP == null || r.cacheP == null) return null;
  return 100 * (1 - pCache / 100) * r.inP + 100 * (pCache / 100) * r.cacheP;
}

const fmt = (v, d=2) => (v === null || v === undefined) ? "\u2014"
  : Number(v).toLocaleString("pt-BR",{minimumFractionDigits:0,maximumFractionDigits:d});
const fmtC = (v) => (v === null || v === undefined) ? "\u2014" : (v === 0 ? "gr\u00e1tis"
  : "US$ " + Number(v).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2}));
const fmtP = (v) => (v === null || v === undefined) ? "\u2014" : Number(v).toLocaleString("pt-BR",{minimumFractionDigits:3,maximumFractionDigits:3});

const CUS = DATA.map(r=>r.cu).filter(v=>v!=null).sort((a,b)=>a-b);
function pctOf(v){ if(v==null) return null; return 100 * CUS.filter(x => x < v).length / CUS.length; }

let pCache = REAL.cache, pOut = REAL.out;
function applyMix(){
  DATA.forEach(r => {
    r.costNow = computeCost(r, pCache, pOut);
    r.per1mNow = computePer1m(r, pCache);
  });
}
function mixLabel(){
  const u = 100 - pCache - pOut;
  return "entrada sem cache " + u.toFixed(1) + "% \u00b7 cache " + pCache.toFixed(0)
       + "% \u00b7 saida " + pOut.toFixed(2) + "%";
}

document.getElementById("stTotal").textContent = DATA.length;
document.getElementById("stGraded").textContent = DATA.filter(r=>r.cu!=null).length;
document.getElementById("stFree").textContent = DATA.filter(r=>r.free).length;

function showDetail(r){
  const el = document.getElementById("detail");
  const dims=[["Raciocinio Abstrato",r.abs],["Raciocinio Matematico",r.math],["Raciocinio Academico",r.acad],
    ["Programacao",r.code],["Uso de Computador",r.cu],["Confiabilidade",r.rel],["Trabalho de Conhecimento",r.kw]];
  el.innerHTML = "<b>"+r.name+"</b> "+(r.free?'<span class="tag">GRATUITO</span>':"")+
    (r.rmand?' <span class="warn">reasoning obrigatorio</span>':"")+
    "<br><span class='muted'>"+r.id+" &middot; AI IQ: "+(r.aiiq||"\u2014")+" &middot; "+(r.modality||"\u2014")+"</span>"+
    "<br>Score agentico: <b>"+fmt(r.cu,0)+"</b> (percentil "+fmt(pctOf(r.cu),0)+") &nbsp;&middot;&nbsp; IQ composto: <b>"+fmt(r.iq,0)+"</b>"+
    "<br>Custo mensal no mix atual: <b>"+fmtC(r.costNow)+"</b> &nbsp;&middot;&nbsp; US$/1M prompt: <b>US$ "+fmtP(r.per1mNow)+"</b>"+
    "<br>Entrada US$ "+fmt(r.inP,4)+" &middot; Saida US$ "+fmt(r.outP,4)+" &middot; Cache read "
    +(r.cacheEst?"\u2014 (nao publicado; calculo usa a entrada)":"US$ "+fmt(r.cacheP,4))+
    " &nbsp;&middot;&nbsp; Contexto "+fmt(r.ctx,0)+" &middot; Saida max. "+fmt(r.maxout,0)+
    "<div class='dims'>"+dims.map(d=>"<div><span>"+d[0]+"</span><b>"+fmt(d[1],0)+"</b></div>").join("")+"</div>";
  const c=document.getElementById("detailCard"); c.style.display="block";
  c.scrollIntoView({behavior:"smooth",block:"nearest"});
}

function renderValue(){
  const pool = DATA.filter(r=>r.cu!=null && r.cu>=FLOOR && !r.free && r.costNow>0)
    .map(r=>({...r, val: r.cu/r.costNow})).sort((a,b)=>b.val-a.val).slice(0,10);
  window._valueIds = new Set(pool.map(r=>r.id));
  document.querySelector("#valueTable tbody").innerHTML = pool.map((r,i)=>
    "<tr class='rowlink' data-id='"+r.id+"'><td>"+(i+1)+"</td><td>"+r.name+"</td>"+
    "<td class='num'>"+fmt(r.cu,0)+"</td><td class='num'>"+fmt(pctOf(r.cu),0)+"</td>"+
    "<td class='num'>"+fmt(r.iq,0)+"</td><td class='num'>"+fmtC(r.costNow)+"</td>"+
    "<td class='num'>"+fmtP(r.per1mNow)+"</td><td class='num'>"+fmt(r.ctx,0)+"</td></tr>").join("");
}

// ---- tabela de excluidos (transparencia) ----
const EXCL = __EXCLDATA__;
let exclSort = {k:"inP", dir:1};
function renderExcl(){
  const list = EXCL.slice().sort((a,b)=>{
    const av=a[exclSort.k], bv=b[exclSort.k];
    if(av==null&&bv==null) return 0;
    if(av==null) return 1; if(bv==null) return -1;
    const c = typeof av==="string" ? av.localeCompare(bv) : av-bv;
    return c*exclSort.dir;
  });
  document.querySelector("#exclTable tbody").innerHTML = list.map(r=>
    "<tr><td>"+r.id+"</td><td class='num'>"+fmt(r.inP,4)+"</td>"+
    "<td class='num'>"+fmt(r.outP,4)+"</td><td class='num'>"+fmt(r.ctx,0)+"</td>"+
    "<td>"+(r.tools?"<span class='tag'>sim</span>":"<span class='muted'>nao</span>")+"</td></tr>").join("");
  document.querySelectorAll("#exclTable th").forEach(th=>{
    const k=th.dataset.e;
    if(k) th.textContent = th.textContent.replace(/ [\u25b2\u25bc]$/,"") + (exclSort.k===k?(exclSort.dir===1?" \u25b2":" \u25bc"):"");
  });
}
document.querySelectorAll("#exclTable th").forEach(th=>th.addEventListener("click",()=>{
  const k=th.dataset.e; if(!k) return;
  if(exclSort.k===k) exclSort.dir*=-1; else exclSort={k, dir:1};
  renderExcl();
}));
renderExcl();

const frees = DATA.filter(r=>r.free).sort((a,b)=>(b.cu||0)-(a.cu||0));document.querySelector("#freeTable tbody").innerHTML = frees.map((r,i)=>
  "<tr class='rowlink' data-id='"+r.id+"'><td>"+(i+1)+"</td><td>"+r.name+"</td>"+
  "<td class='num'>"+fmt(r.cu,0)+"</td><td class='num'>"+fmt(r.iq,0)+"</td>"+
  "<td class='num'>"+fmt(r.code,0)+"</td><td class='num'>"+fmt(r.ctx,0)+"</td>"+
  "<td><span class='tag'>probe ok</span></td></tr>").join("");

let drawn=[];
function drawChart(){
  const canvas=document.getElementById("chart"), ctx=canvas.getContext("2d");
  const W=canvas.clientWidth, H=400, dpr=window.devicePixelRatio||1;
  canvas.width=W*dpr; canvas.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const pts = DATA.filter(r=>r.cu!=null && r.costNow!=null)
    .map(r=>({...r, plotCost: r.costNow>0 ? r.costNow : 0.05}));
  if (!pts.length) return;
  const padL=46,padR=14,padT=12,padB=34;
  const costs=pts.map(r=>r.plotCost);
  const minC=Math.max(Math.min(...costs),0.05), maxC=Math.max(...costs, minC*10);
  const iqs=pts.map(r=>r.cu);
  const minI=Math.min(...iqs)-4, maxI=Math.max(...iqs)+4;
  const X=c=>padL+(Math.log10(Math.max(c,0.05))-Math.log10(minC))/(Math.log10(maxC)-Math.log10(minC))*(W-padL-padR);
  const Y=q=>padT+(1-(q-minI)/(maxI-minI))*(H-padT-padB);
  ctx.strokeStyle="#e3e8ee"; ctx.fillStyle="#8a97a5"; ctx.font="11px sans-serif"; ctx.textAlign="center";
  [0.1,1,10,100,1000].forEach(v=>{ if(v<minC||v>maxC) return;
    ctx.beginPath(); ctx.moveTo(X(v),padT); ctx.lineTo(X(v),H-padB); ctx.stroke();
    ctx.fillText("US$ "+v, X(v), H-14); });
  ctx.textAlign="right";
  for(let q=Math.ceil(minI/10)*10; q<=maxI; q+=10){
    ctx.beginPath(); ctx.moveTo(padL,Y(q)); ctx.lineTo(W-padR,Y(q)); ctx.stroke();
    ctx.fillText(q, padL-6, Y(q)+4);
  }
  ctx.strokeStyle="#f3c9c9"; ctx.setLineDash([5,4]);
  ctx.beginPath(); ctx.moveTo(padL,Y(MED_CU)); ctx.lineTo(W-padR,Y(MED_CU)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle="#c98a8a"; ctx.textAlign="left";
  ctx.fillText("mediana "+MED_CU, padL+4, Y(MED_CU)-5);
  const vIds = window._valueIds || new Set();
  drawn = pts.map(r=>({r, x:X(Math.max(r.plotCost,0.05)), y:Y(r.cu)}));
  drawn.forEach(p=>{
    let col = p.r.free ? "#1d9e4b" : (p.r.cu < MED_CU ? "#a11" : "#0b5fff");
    if(vIds.has(p.r.id)) col="#e0a100";
    ctx.beginPath(); ctx.arc(p.x,p.y, vIds.has(p.r.id)?6:4, 0, 7);
    ctx.fillStyle=col; ctx.globalAlpha=.85; ctx.fill(); ctx.globalAlpha=1;
  });
}
const tip=document.getElementById("tip");
const chartEl=document.getElementById("chart");
function nearest(e){
  const rect=chartEl.getBoundingClientRect(), mx=e.clientX-rect.left, my=e.clientY-rect.top;
  let best=null,bd=1e9;
  drawn.forEach(p=>{const d=(p.x-mx)**2+(p.y-my)**2; if(d<bd){bd=d;best=p;}});
  return {best,bd,mx,my};
}
chartEl.addEventListener("mousemove",e=>{
  const {best,bd,mx,my}=nearest(e);
  if(best&&bd<400){
    tip.style.display="block"; tip.style.left=(mx+14)+"px"; tip.style.top=(my+10)+"px";
    tip.innerHTML="<b>"+best.r.name+"</b><br>Agente "+fmt(best.r.cu,0)+" (p"+fmt(pctOf(best.r.cu),0)+")<br>"+fmtC(best.r.costNow)+"/mes";
  } else tip.style.display="none";
});
chartEl.addEventListener("click",e=>{
  const {best,bd}=nearest(e); if(best&&bd<400) showDetail(best.r);
});
chartEl.addEventListener("mouseleave",()=>tip.style.display="none");
window.addEventListener("resize", drawChart);

const providers=[...new Set(DATA.map(r=>r.provider))].sort();
document.getElementById("fProvider").innerHTML += providers.map(p=>"<option>"+p+"</option>").join("");
let sorts=[{key:"cu",dir:-1}];
const numCols=[2,3,4,5,6,7,8,9,10];
function applyFilters(){
  const q=document.getElementById("fSearch").value.toLowerCase();
  const prov=document.getElementById("fProvider").value;
  const minIq=parseFloat(document.getElementById("fMinIq").value);
  const minCu=parseFloat(document.getElementById("fMinCu").value);
  const maxCost=parseFloat(document.getElementById("fMaxCost").value);
  const onlyFree=document.getElementById("fFree").checked;
  const needTools=document.getElementById("fTools").checked;
  const keepNoIq=document.getElementById("fNoIq").checked;
  let list=DATA.filter(r=>{
    if(q && !(r.name.toLowerCase().includes(q)||r.id.toLowerCase().includes(q)||r.provider.toLowerCase().includes(q))) return false;
    if(prov && r.provider!==prov) return false;
    if(!isNaN(minIq)){
      // o filtro apenas esconde a linha; nunca inventa nem reescreve a nota
      if(r.iq==null){ if(!keepNoIq) return false; }
      else if(r.iq<minIq) return false;
    }
    if(!isNaN(minCu) && (r.cu==null||r.cu<minCu)) return false;
    if(!isNaN(maxCost) && (r.costNow==null||r.costNow>maxCost)) return false;
    if(onlyFree && !r.free) return false;
    if(needTools && !r.tools) return false;
    return true;
  });
  list.sort((a,b)=>{
    for(const s of sorts){
      const av=a[s.key], bv=b[s.key];
      if(av==null&&bv==null) continue;
      if(av==null) return 1; if(bv==null) return -1;
      const c=typeof av==="string"?av.localeCompare(bv):av-bv;
      if(c!==0) return c*s.dir;
    }
    return 0;
  });
  document.getElementById("stShown").textContent=list.length;
  const labels={name:"Modelo",provider:"Provedor",cu:"Agente",iq:"IQ",code:"Codigo",rel:"Confiab.",
    costNow:"US$/mes",per1mNow:"US$/1M prompt",inP:"Entrada",outP:"Saida",ctx:"Contexto"};
  document.querySelectorAll("#mainTable th").forEach(th=>{
    const k=th.dataset.k, idx=sorts.findIndex(s=>s.key===k);
    th.classList.toggle("sorted",idx>=0);
    th.textContent=labels[k]+(idx>=0?(sorts[idx].dir===1?" \u25b2":" \u25bc")+(sorts.length>1?" "+(idx+1):""):"");
  });
  const colMap={name:0,provider:1,cu:2,iq:3,code:4,rel:5,costNow:6,per1mNow:7,inP:8,outP:9,ctx:10};
  const colIdxs=new Set(sorts.map(s=>colMap[s.key]));
  document.querySelector("#mainTable tbody").innerHTML=list.map(r=>{
    const cells=[r.name+(r.free?" <span class='tag'>FREE</span>":"")+(r.rmand?" <span class='warn'>R</span>":"")+(r.cacheEst?" <span class='warn' title='sem preco de cache publicado; custo usa a entrada como pior caso'>cache~</span>":""),
      r.provider,fmt(r.cu,0),fmt(r.iq,0),fmt(r.code,0),fmt(r.rel,0),
      fmtC(r.costNow),fmtP(r.per1mNow),fmt(r.inP,4),fmt(r.outP,4),fmt(r.ctx,0)];
    const tds=cells.map((c,i)=>{
      const cls=[numCols.includes(i)?"num":"",colIdxs.has(i)?"sorted":""].filter(Boolean).join(" ");
      return cls?"<td class='"+cls+"'>"+c+"</td>":"<td>"+c+"</td>";
    }).join("");
    return "<tr class='rowlink' data-id='"+r.id+"'>"+tds+"</tr>";
  }).join("");
}
["fSearch","fProvider","fMinIq","fMinCu","fMaxCost","fFree","fTools","fNoIq"].forEach(id=>
  document.getElementById(id).addEventListener("input",applyFilters));

let multiArmed=false;
const multiBtn=document.getElementById("multiBtn");
function setMultiArmed(v){multiArmed=v;multiBtn.classList.toggle("armed",v);
  multiBtn.textContent=v?"Toque num cabecalho para ser a 2\u00aa coluna \u2715":"\uff0b 2\u00aa coluna";}
multiBtn.addEventListener("click",()=>setMultiArmed(!multiArmed));
let justLongPressed=false;
document.querySelectorAll("#mainTable th").forEach(th=>th.addEventListener("click",(e)=>{
  if(justLongPressed){justLongPressed=false;return;}
  const k=th.dataset.k, defDir=(k==="name"||k==="provider")?1:-1;
  const idx=sorts.findIndex(s=>s.key===k);
  if(e.shiftKey||multiArmed){
    if(idx>=0) sorts[idx].dir*=-1; else sorts.push({key:k,dir:defDir});
    if(multiArmed) setMultiArmed(false);
  } else {
    if(sorts.length===1&&idx===0) sorts[0].dir*=-1; else sorts=[{key:k,dir:defDir}];
  }
  applyFilters();
}));
document.querySelectorAll("#mainTable th").forEach(th=>{
  let t=null;
  th.addEventListener("touchstart",()=>{t=setTimeout(()=>{
    justLongPressed=true;
    const k=th.dataset.k, defDir=(k==="name"||k==="provider")?1:-1;
    const idx=sorts.findIndex(s=>s.key===k);
    if(idx>=0) sorts[idx].dir*=-1; else sorts.push({key:k,dir:defDir});
    applyFilters();
  },500);},{passive:true});
  th.addEventListener("touchmove",()=>clearTimeout(t));
  th.addEventListener("touchend",()=>clearTimeout(t));
});
document.addEventListener("click",e=>{
  const tr=e.target.closest("tr.rowlink");
  if(tr){const r=DATA.find(x=>x.id===tr.dataset.id); if(r) showDetail(r);}
});

function refreshAll(){
  applyMix();
  document.getElementById("vCache").textContent = pCache.toFixed(0);
  document.getElementById("vOut").textContent = pOut.toFixed(2);
  document.getElementById("mixNote").textContent = mixLabel();
  renderValue();
  applyFilters();
  drawChart();
}
function setMix(c, o){
  pCache = Math.max(0, Math.min(95, c));
  pOut = Math.max(0.2, Math.min(10, o));
  document.getElementById("rCache").value = pCache;
  document.getElementById("rOut").value = pOut;
  refreshAll();
}
document.getElementById("rCache").addEventListener("input", e=>setMix(+e.target.value, pOut));
document.getElementById("rOut").addEventListener("input", e=>setMix(pCache, +e.target.value));
document.getElementById("btnReal").addEventListener("click", ()=>setMix(REAL.cache, REAL.out));
document.getElementById("btnNoCache").addEventListener("click", ()=>setMix(0, 3));
document.getElementById("btnCacheMax").addEventListener("click", ()=>setMix(95, 0.5));

refreshAll();
</script>
</body>
</html>
"""

out = (TMPL
       .replace("__DATA__", DATA)
       .replace("__MED__", str(int(MED_CU)))
       .replace("__FLOOR__", str(FLOOR))
       .replace("__N__", str(N_GRADED))
       .replace("__MC__", f"{mix_cache:.0f}")
       .replace("__MO__", f"{mix_out:.2f}")
       .replace("__BASEP__", f"{(MIX['uncached_in_M'] + MIX['cache_read_M']):.1f}")
       .replace("__NTOTAL__", str(_n_total))
       .replace("__NROWS__", str(_n_rows))
       .replace("__NBATCH__", str(_n_batch))
       .replace("__NALIAS__", str(_n_alias))
       .replace("__NROUTERS__", str(_neg))
       .replace("__NUNIQ__", str(_n_unique))
       .replace("__NFREE__", str(_n_freev))
       .replace("__NPAID__", str(_n_paid_indep))
       .replace("__NPAIDROWS__", str(_n_rows_paid))
       .replace("__NFREEOK__", str(_n_free_ok))
       .replace("__NFREEBAD__", str(_n_free_excl))
       .replace("__NEXCL__", str(_n_excl))
       .replace("__EXCLREASON__", EXCL_REASON)
       .replace("__EXCLDATA__", EXCL_DATA)
       .replace("__MIX_TXT__",
                f"em 30 dias o Hermes processou {MIX['uncached_in_M']:.1f}M tokens de entrada sem cache, "
                f"{MIX['cache_read_M']:.1f}M de cache read e {MIX['out_M']:.2f}M de saida "
                f"({mix_cache:.0f}% cache, {mix_out:.2f}% saida, em {MIX['calls']} chamadas)")
       .replace("__NOW__", now)
       .replace("__LIMITS__", limits))

path = "/home/ubuntu/github/openrouter-custo-beneficio/index.html"
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w", encoding="utf-8").write(out)
print(f"linhas: {len(rows)} (pagas {sum(1 for r in rows if not r['free'])}, free {sum(1 for r in rows if r['free'])})")
print(f"sem nota: {sum(1 for r in rows if r['iq'] is None)} | mediana agente: {MED_CU} | piso: {FLOOR}")
print(f"escrito: {path} ({len(out)/1024:.0f} KB)")
json.dump(rows, open("rows_final.json", "w"), ensure_ascii=False, indent=1)

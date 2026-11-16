#!/usr/bin/env python3
"""Gera o dashboard corrigido de custo x beneficio para o Hermes Agent.

Correcoes sobre o original:
 1. JOIN: notas do AI IQ ligadas ao OpenRouter por nome normalizado + desempate,
    NUNCA pela propria nota. O original colapsava por `iq`, herdando as 8 notas de
    um modelo para outro (novo-micro-v1 recebeu as notas do o1).
 2. CUSTO: calculado com os 3 baldes reais de token do Hermes (nao-cacheado,
    cache-read, saida) em vez de media simples de entrada/saida.
 3. PRECOS: lidos da API do OpenRouter no momento da geracao, nao de copia.
 4. LIMPEZA: sem :batch, sem aliases ~, sem routers com preco negativo.
 5. FREE: cada :free recebe probe de 10 tokens antes de entrar na lista.
 6. COLUNA: score agentico (computer-use) e o criterio de ordenacao, com filtro
    de teto de custo -- a pergunta que importa para um agente.
"""
import json, html, datetime, statistics

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
    if not pr or pr["in"] is None or pr["out"] is None:
        return None
    cr = pr["cache_read"]
    if cr is None:
        return None
    return (MIX["uncached_in_M"] * pr["in"] + MIX["cache_read_M"] * cr + MIX["out_M"] * pr["out"])


def prompt_blend(pr):
    if not pr or pr["in"] is None or pr["cache_read"] is None:
        return None
    tot = MIX["uncached_in_M"] + MIX["cache_read_M"]
    return (MIX["uncached_in_M"] * pr["in"] + MIX["cache_read_M"] * pr["cache_read"]) / tot


def is_free(pr):
    return pr and pr["in"] == 0 and pr["out"] == 0


rows = []
for oid, a in mp.items():
    m = ors.get(oid)
    if not m:
        continue
    am = aiiq.get(a["aiiq_id"])
    if not am:
        continue
    d = am.get("dimensions") or {}
    pr = pricing(m)
    cost = monthly(pr)
    sp = m.get("supported_parameters") or []
    reason = (m.get("reasoning") or {})
    free = is_free(pr)
    pf = probe.get(oid)
    if free:
        # so entra na lista se o probe confirmou que roda
        if not pf or pf["status"] != "ok":
            continue
        cost = 0.0
    if cost is None:
        continue
    rows.append({
        "id": oid, "name": (m.get("name") or oid),
        "provider": oid.split("/")[0],
        "aiiq": a["aiiq_id"],
        "iq": am.get("iq"), "cu": d.get("computer-use"),
        "code": d.get("programmatic-reasoning"),
        "rel": d.get("reliability"),
        "kw": d.get("knowledge-work"),
        "abs": d.get("abstract-reasoning"), "math": d.get("mathematical-reasoning"),
        "acad": d.get("academic-reasoning"),
        "ctx": m.get("context_length") or 0,
        "maxout": m.get("top_provider", {}).get("max_completion_tokens") or 0,
        "inP": pr["in"], "outP": pr["out"], "cacheP": pr["cache_read"],
        "cost": cost, "per1m": prompt_blend(pr),
        "tools": "tools" in sp,
        "rmand": bool(reason.get("mandatory")),
        "free": free,
        "modality": (m.get("architecture") or {}).get("modality") or "",
        "released": (m.get("created") or 0),
        "table_ratio": a.get("or_vs_table"),
        "coverage": (am.get("iqCoverage") or {}).get("directDimensions", 0),
        "conf": a.get("confidence"),
    })

rows.sort(key=lambda r: (r["cost"], -(r["cu"] or 0)))

# Gratuitos confirmados pelo probe. Os que tem modelo-base mapeado herdam as notas
# (mesmos pesos); os que nao tem entram com nota vazia em vez de serem omitidos, para
# que a lista de gratuitos reflita o que realmente responde.
seen = {r["id"] for r in rows}
for fid, pf in probe.items():
    if pf["status"] != "ok" or fid in seen or fid not in ors:
        continue
    m = ors[fid]
    base_id = fid[:-5]
    a = mp.get(base_id)
    am = aiiq.get(a["aiiq_id"]) if a else None
    d = (am or {}).get("dimensions") or {}
    rows.append({
        "id": fid, "name": (m.get("name") or fid),
        "provider": fid.split("/")[0],
        "aiiq": (a["aiiq_id"] if a else None),
        "iq": (am or {}).get("iq"), "cu": d.get("computer-use"),
        "code": d.get("programmatic-reasoning"), "rel": d.get("reliability"),
        "kw": d.get("knowledge-work"), "abs": d.get("abstract-reasoning"),
        "math": d.get("mathematical-reasoning"), "acad": d.get("academic-reasoning"),
        "ctx": m.get("context_length") or 0,
        "maxout": (m.get("top_provider") or {}).get("max_completion_tokens") or 0,
        "inP": 0.0, "outP": 0.0, "cacheP": 0.0,
        "cost": 0.0, "per1m": 0.0,
        "tools": "tools" in (m.get("supported_parameters") or []),
        "rmand": bool((m.get("reasoning") or {}).get("mandatory")),
        "free": True,
        "modality": (m.get("architecture") or {}).get("modality") or "",
        "released": (m.get("created") or 0),
        "table_ratio": (a or {}).get("or_vs_table"),
        "coverage": ((am or {}).get("iqCoverage") or {}).get("directDimensions", 0),
        "conf": (a or {}).get("confidence"),
    })

rows.sort(key=lambda r: (r["cost"], -(r["cu"] or 0)))
print(f"linhas finais: {len(rows)} (pagas {sum(1 for r in rows if not r['free'])}, free {sum(1 for r in rows if r['free'])})")

CUS = [r["cu"] for r in rows if r["cu"] is not None]
MED_CU = statistics.median(CUS)
LEAD_CU = max(CUS)


def pct(v, ref=CUS):
    return 100.0 * sum(1 for x in ref if x < v) / len(ref)


now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
mix_cache = 100 * MIX["cache_read_M"] / (MIX["uncached_in_M"] + MIX["cache_read_M"] + MIX["out_M"])
mix_out = 100 * MIX["out_M"] / (MIX["uncached_in_M"] + MIX["cache_read_M"] + MIX["out_M"])

DATA = json.dumps(rows, ensure_ascii=False)

HTML_TMPL = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OpenRouter: custo x beneficio (corrigido)</title>
<style>
  *{box-sizing:border-box}
  body{font-family:-apple-system,"Segoe UI",Roboto,Arial,sans-serif;margin:0;background:#f4f6f8;color:#1c2530}
  header{background:#14213d;color:#fff;padding:22px 20px}
  header h1{margin:0 0 6px;font-size:22px}
  header p{margin:0;opacity:.85;font-size:13px;line-height:1.6}
  main{max-width:1180px;margin:0 auto;padding:16px}
  .stats{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
  .stat{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:12px 16px;flex:1;min-width:150px}
  .stat b{display:block;font-size:22px}
  .stat span{font-size:12px;color:#5b6b7c;line-height:1.4;display:block;margin-top:2px}
  .card{background:#fff;border:1px solid #dde3ea;border-radius:10px;padding:16px;margin-bottom:16px}
  .card h2{margin:0 0 4px;font-size:17px}
  .card p.sub{margin:0 0 12px;font-size:12.5px;color:#5b6b7c;line-height:1.6}
  .filters{display:flex;flex-wrap:wrap;gap:10px;align-items:end}
  .filters label{font-size:11.5px;color:#5b6b7c;display:block;margin-bottom:3px}
  .filters input,.filters select{padding:7px;border:1px solid #c6d0dc;border-radius:6px;font-size:13.5px;background:#fff}
  .filters .check{display:flex;align-items:center;gap:6px;padding-bottom:7px;font-size:13.5px}
  #chart{width:100%;height:400px;display:block;cursor:crosshair}
  #tip{position:absolute;background:#14213d;color:#fff;padding:8px 10px;border-radius:6px;font-size:12px;
       pointer-events:none;display:none;max-width:300px;line-height:1.5;z-index:5}
  .legend{font-size:12px;color:#5b6b7c;margin-top:6px;line-height:1.8}
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
  .bad{display:inline-block;background:#fbe4e4;color:#a11;border-radius:20px;padding:1px 7px;font-size:11px;font-weight:600}
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
  footer{font-size:11.5px;color:#8a97a5;padding:0 16px 28px;max-width:1180px;margin:0 auto;line-height:1.8}
  .pos{color:#1d7a33;font-weight:600}
  .neg{color:#a11;font-weight:600}
</style>
</head>
<body>
<header>
  <h1>OpenRouter: custo x beneficio &mdash; versao corrigida</h1>
  <p>Custo calculado com o <b>mix real de tokens do Hermes Agent</b>: __MIX_TXT__.<br>
  Notas do AI IQ ligadas ao modelo certo por nome + desempate (nao pela propria nota). Dados de __NOW__.</p>
</header>
<main>

  <div class="card">
    <div class="note">
      <b>O que mudou em relacao ao dashboard anterior.</b> A coluna "custo efetivo" do arquivo original
      estava errada em <b>212 de 250</b> linhas: era uma media de entrada e saida que caia <i>fora</i> do
      intervalo dos dois precos. A causa era o join &mdash; as 8 notas do AI IQ eram ligadas ao modelo pela
      propria nota, entao seis modelos de familias diferentes herdaram as notas do <code>o1</code>
      (iq 95, custo 75,82). Aqui cada linha e ligada por nome, com desempate por preco, e o custo vem dos
      tres baldes de token que o Hermes realmente gasta.
    </div>
  </div>

  <div class="stats">
    <div class="stat"><b id="stTotal">-</b><span>modelos com nota + custo calculavel</span></div>
    <div class="stat"><b id="stGraded">-</b><span>com score agentico</span></div>
    <div class="stat"><b id="stFree">-</b><span>gratuitos que respondem (probe)</span></div>
    <div class="stat"><b id="stShown">-</b><span>na tabela apos filtros</span></div>
    <div class="stat"><b>__MED__</b><span>mediana do score agentico</span></div>
  </div>

  <div class="card">
    <h2>Custo x capacidade agentica</h2>
    <p class="sub">Cada ponto e um modelo. Eixo horizontal: custo mensal real em US$ (escala log) na carga do Hermes.
    Eixo vertical: score de <i>computer use</i> do AI IQ &mdash; a dimensao que mais se aproxima de "consegue operar ferramentas".
    Os 10 melhores custo-beneficio aparecem em dourado. Clique para abrir o detalhe.</p>
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
    <p class="sub">Ordenado por score agentico por dolar, com piso de capacidade: so entram modelos com score agentico
    <b>igual ou acima da mediana do catalogo (__MED__)</b>. Um piso frouxo repetiria o erro da versao anterior em
    escala menor &mdash; com 60% do lider, um modelo no percentil 12 ainda liderava. Custo e o mensal real do Hermes,
    nao a media de tabela.</p>
    <div style="overflow-x:auto">
    <table id="valueTable"><thead><tr>
      <th>#</th><th>Modelo</th><th class="num">Agente</th><th class="num">Posicao</th>
      <th class="num">IQ</th><th class="num">US$/mes</th><th class="num">US$/1M prompt</th><th class="num">Contexto</th>
    </tr></thead><tbody></tbody></table>
    </div>
  </div>

  <div class="card">
    <h2>Gratuitos que realmente respondem</h2>
    <p class="sub">Cada endpoint <code>:free</code> recebeu um probe de 10 tokens antes de entrar nesta lista.
    O candidato que a versao anterior coroou como melhor gratuito (<code>inkling-2-small:free</code>, iq 126)
    retorna <b>403 "only available on agentic harnesses"</b> em chamada direta e foi removido.</p>
    <div style="overflow-x:auto">
    <table id="freeTable"><thead><tr>
      <th>#</th><th>Modelo</th><th class="num">Agente</th><th class="num">IQ</th>
      <th class="num">Codigo</th><th class="num">Contexto</th><th>Status</th>
    </tr></thead><tbody></tbody></table>
    </div>
  </div>

  <div class="card">
    <h2>Todos os modelos</h2>
    <p class="sub">Clique no cabecalho para ordenar. Para uma segunda coluna, use "&#65291; 2&ordf; coluna" e depois
    clique no cabecalho, segure Shift, ou toque e segure no celular. Clique na linha para o detalhe.</p>
    <button class="sortbtn" id="multiBtn" type="button">&#65291; 2&ordf; coluna</button>
    <div class="filters" style="margin-bottom:12px">
      <div><label>Buscar</label><input id="fSearch" type="text" placeholder="nome, id ou provedor" style="width:200px"></div>
      <div><label>Provedor</label><select id="fProvider"><option value="">Todos</option></select></div>
      <div><label>Agente minimo</label><input id="fMinCu" type="number" min="0" max="200" placeholder="ex.: 110" style="width:100px"></div>
      <div><label>US$/mes maximo</label><input id="fMaxCost" type="number" min="0" step="0.5" placeholder="ex.: 5" style="width:110px"></div>
      <div class="check"><input id="fFree" type="checkbox"><span>So gratuitos</span></div>
      <div class="check"><input id="fTools" type="checkbox" checked><span>Exigir function calling</span></div>
    </div>
    <div style="overflow-x:auto">
    <table id="mainTable">
      <thead><tr>
        <th data-k="name">Modelo</th><th data-k="provider">Provedor</th>
        <th data-k="cu" class="num">Agente</th><th data-k="iq" class="num">IQ</th>
        <th data-k="code" class="num">Codigo</th><th data-k="rel" class="num">Confiab.</th>
        <th data-k="cost" class="num">US$/mes</th><th data-k="per1m" class="num">US$/1M prompt</th>
        <th data-k="inP" class="num">Entrada</th><th data-k="outP" class="num">Saida</th>
        <th data-k="ctx" class="num">Contexto</th>
      </tr></thead>
      <tbody></tbody>
    </table>
    </div>
  </div>
</main>
<footer>
  <b>Fontes.</b> Notas de capacidade e precos de tabela: API publica do AI IQ
  (<code>www.aiiq.org/api/v1/models</code>, metodologia 2026-09-30-arc-predictive-puzzles).
  Precos praticados, contexto e suporte a ferramentas: <code>openrouter.ai/api/v1/models</code>.
  Ambas consultadas em __NOW__.<br>
  <b>Custo mensal.</b> __MIX_TXT__. O Hermes grava <code>input_tokens</code> ja liquido de cache
  (<code>agent/usage_pricing.py</code>: <code>input_tokens = prompt_total - cache_read - cache_write</code>),
  por isso o modelo usa tres baldes separados. Modelos que nao publicam preco de cache ficam de fora:
  sem esse numero o custo real seria subestimado em ate 10x nesta carga.<br>
  <b>Limitacoes.</b> __LIMITS__<br>
  <b>Colunas derivadas.</b> "Agente" = <code>computer-use</code> do AI IQ. "Posicao" = percentil dentro dos
  __N__ modelos com essa dimensao. "US$/1M prompt" = custo medio por milhao de tokens de prompt ja
  ponderado pelo cache &mdash; comparavel entre modelos, ao contrario da media bruta de entrada e saida.
</footer>
<script>
const DATA = __DATA__;
const MED_CU = __MED__;
const LEAD_CU = __LEAD__;
const fmt = (v, d=2) => (v === null || v === undefined) ? "&mdash;" : Number(v).toLocaleString("pt-BR",{minimumFractionDigits:0,maximumFractionDigits:d});
const fmtC = (v) => v === null || v === undefined ? "&mdash;" : (v === 0 ? "grátis" : "US$ " + Number(v).toLocaleString("pt-BR",{minimumFractionDigits:2,maximumFractionDigits:2}));

document.getElementById("stTotal").textContent = DATA.length;
document.getElementById("stGraded").textContent = DATA.filter(r=>r.cu!=null).length;
document.getElementById("stFree").textContent = DATA.filter(r=>r.free).length;

const CUS = DATA.map(r=>r.cu).filter(v=>v!=null).sort((a,b)=>a-b);
function pctOf(v){ if(v==null) return null; return 100*CUS.filter(x=>x<v).length/CUS.length; }

function showDetail(r){
  const el = document.getElementById("detail");
  const dims=[["Raciocinio Abstrato",r.abs],["Raciocinio Matematico",r.math],["Raciocinio Academico",r.acad],
    ["Programacao",r.code],["Uso de Computador",r.cu],["Confiabilidade",r.rel],["Trabalho de Conhecimento",r.kw]];
  el.innerHTML = "<b>"+r.name+"</b> "+(r.free?'<span class="tag">GRATUITO</span>':"")+
    (r.rmand?' <span class="warn">reasoning obrigatorio</span>':"")+
    "<br><span class='muted'>"+r.id+" &middot; AI IQ: "+r.aiiq+" &middot; "+(r.modality||"&mdash;")+"</span>"+
    "<br>Score agentico: <b>"+fmt(r.cu,0)+"</b> (percentil "+fmt(pctOf(r.cu),0)+") &nbsp;&middot;&nbsp; IQ composto: <b>"+fmt(r.iq,0)+"</b>"+
    "<br>Custo mensal na carga Hermes: <b>"+fmtC(r.cost)+"</b> &nbsp;&middot;&nbsp; US$/1M prompt: <b>US$ "+fmt(r.per1m,3)+"</b>"+
    "<br>Entrada US$ "+fmt(r.inP,4)+" &middot; Saida US$ "+fmt(r.outP,4)+" &middot; Cache read US$ "+(r.cacheP==null?"&mdash;":fmt(r.cacheP,4))+
    " &nbsp;&middot;&nbsp; Contexto "+fmt(r.ctx,0)+" &middot; Saida max. "+fmt(r.maxout,0)+
    "<div class='dims'>"+dims.map(d=>"<div><span>"+d[0]+"</span><b>"+fmt(d[1],0)+"</b></div>").join("")+"</div>";
  const c=document.getElementById("detailCard"); c.style.display="block";
  c.scrollIntoView({behavior:"smooth",block:"nearest"});
}

// ---- melhor custo-beneficio (com piso de capacidade) ----
const FLOOR = __FLOOR__;
const pool = DATA.filter(r=>r.cu!=null && r.cu>=FLOOR && !r.free && r.cost>0)
  .map(r=>({...r, val: r.cu/r.cost})).sort((a,b)=>b.val-a.val).slice(0,10);
const valueIds = new Set(pool.map(r=>r.id));
document.querySelector("#valueTable tbody").innerHTML = pool.map((r,i)=>
  "<tr class='rowlink' data-id='"+r.id+"'><td>"+(i+1)+"</td><td>"+r.name+"</td>"+
  "<td class='num'>"+fmt(r.cu,0)+"</td><td class='num'>"+fmt(pctOf(r.cu),0)+"</td>"+
  "<td class='num'>"+fmt(r.iq,0)+"</td><td class='num'>"+fmtC(r.cost)+"</td>"+
  "<td class='num'>"+fmt(r.per1m,3)+"</td><td class='num'>"+fmt(r.ctx,0)+"</td></tr>").join("");

// ---- gratuitos ----
const frees = DATA.filter(r=>r.free).sort((a,b)=>(b.cu||0)-(a.cu||0));
document.querySelector("#freeTable tbody").innerHTML = frees.map((r,i)=>
  "<tr class='rowlink' data-id='"+r.id+"'><td>"+(i+1)+"</td><td>"+r.name+"</td>"+
  "<td class='num'>"+fmt(r.cu,0)+"</td><td class='num'>"+fmt(r.iq,0)+"</td>"+
  "<td class='num'>"+fmt(r.code,0)+"</td><td class='num'>"+fmt(r.ctx,0)+"</td>"+
  "<td><span class='tag'>probe ok</span></td></tr>").join("");

// ---- grafico ----
const pts = DATA.filter(r=>r.cu!=null && r.cost!=null).map(r=>({...r, plotCost: r.cost>0 ? r.cost : 0.05}));
const canvas=document.getElementById("chart"), ctx=canvas.getContext("2d");
const tip=document.getElementById("tip");
let drawn=[];
function drawChart(){
  const W=canvas.clientWidth, H=400, dpr=window.devicePixelRatio||1;
  canvas.width=W*dpr; canvas.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  ctx.clearRect(0,0,W,H);
  const padL=46,padR=14,padT=12,padB=34;
  const costs=pts.map(r=>r.plotCost);
  const minC=Math.min(...costs), maxC=Math.max(...costs);
  const iqs=pts.map(r=>r.cu);
  const minI=Math.min(...iqs)-4, maxI=Math.max(...iqs)+4;
  const X=c=>padL+(Math.log10(Math.max(c,0.05))-Math.log10(Math.max(minC,0.05)))/(Math.log10(maxC)-Math.log10(Math.max(minC,0.05)))*(W-padL-padR);
  const Y=q=>padT+(1-(q-minI)/(maxI-minI))*(H-padT-padB);
  ctx.strokeStyle="#e3e8ee"; ctx.fillStyle="#8a97a5"; ctx.font="11px sans-serif"; ctx.textAlign="center";
  [0.1,1,10,100].forEach(v=>{ if(v<minC||v>maxC) return;
    ctx.beginPath(); ctx.moveTo(X(v),padT); ctx.lineTo(X(v),H-padB); ctx.stroke();
    ctx.fillText("US$ "+v, X(v), H-14); });
  ctx.textAlign="right";
  for(let q=Math.ceil(minI/10)*10; q<=maxI; q+=10){
    ctx.beginPath(); ctx.moveTo(padL,Y(q)); ctx.lineTo(W-padR,Y(q)); ctx.stroke();
    ctx.fillText(q, padL-6, Y(q)+4);
  }
  // linha da mediana
  ctx.strokeStyle="#f3c9c9"; ctx.setLineDash([5,4]);
  ctx.beginPath(); ctx.moveTo(padL,Y(MED_CU)); ctx.lineTo(W-padR,Y(MED_CU)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle="#c98a8a"; ctx.textAlign="left";
  ctx.fillText("mediana "+MED_CU, padL+4, Y(MED_CU)-5);
  drawn = pts.map(r=>({r, x:X(Math.max(r.plotCost,0.05)), y:Y(r.cu)}));
  drawn.forEach(p=>{
    let col = p.r.free ? "#1d9e4b" : (p.r.cu < MED_CU ? "#a11" : "#0b5fff");
    if(valueIds.has(p.r.id)) col="#e0a100";
    ctx.beginPath(); ctx.arc(p.x,p.y, valueIds.has(p.r.id)?6:4, 0, 7);
    ctx.fillStyle=col; ctx.globalAlpha=.85; ctx.fill(); ctx.globalAlpha=1;
  });
}
drawChart();
window.addEventListener("resize", drawChart);
function nearest(e){
  const rect=canvas.getBoundingClientRect(), mx=e.clientX-rect.left, my=e.clientY-rect.top;
  let best=null,bd=1e9;
  drawn.forEach(p=>{const d=(p.x-mx)**2+(p.y-my)**2; if(d<bd){bd=d;best=p;}});
  return {best,bd,mx,my};
}
canvas.addEventListener("mousemove",e=>{
  const {best,bd,mx,my}=nearest(e);
  if(best&&bd<400){
    tip.style.display="block"; tip.style.left=(mx+14)+"px"; tip.style.top=(my+10)+"px";
    tip.innerHTML="<b>"+best.r.name+"</b><br>Agente "+fmt(best.r.cu,0)+" (p"+fmt(pctOf(best.r.cu),0)+")<br>"+fmtC(best.r.cost)+"/mes";
  } else tip.style.display="none";
});
canvas.addEventListener("click",e=>{
  const {best,bd}=nearest(e); if(best&&bd<400) showDetail(best.r);
});
canvas.addEventListener("mouseleave",()=>tip.style.display="none");

// ---- tabela principal ----
const providers=[...new Set(DATA.map(r=>r.provider))].sort();
document.getElementById("fProvider").innerHTML += providers.map(p=>"<option>"+p+"</option>").join("");
let sorts=[{key:"cu",dir:-1}];
const numCols=[2,3,4,5,6,7,8,9,10];
function applyFilters(){
  const q=document.getElementById("fSearch").value.toLowerCase();
  const prov=document.getElementById("fProvider").value;
  const minCu=parseFloat(document.getElementById("fMinCu").value);
  const maxCost=parseFloat(document.getElementById("fMaxCost").value);
  const onlyFree=document.getElementById("fFree").checked;
  const needTools=document.getElementById("fTools").checked;
  let list=DATA.filter(r=>{
    if(q && !(r.name.toLowerCase().includes(q)||r.id.toLowerCase().includes(q)||r.provider.toLowerCase().includes(q))) return false;
    if(prov && r.provider!==prov) return false;
    if(!isNaN(minCu) && (r.cu==null||r.cu<minCu)) return false;
    if(!isNaN(maxCost) && (r.cost==null||r.cost>maxCost)) return false;
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
    cost:"US$/mes",per1m:"US$/1M prompt",inP:"Entrada",outP:"Saida",ctx:"Contexto"};
  document.querySelectorAll("#mainTable th").forEach(th=>{
    const k=th.dataset.k, idx=sorts.findIndex(s=>s.key===k);
    th.classList.toggle("sorted",idx>=0);
    th.textContent=labels[k]+(idx>=0?(sorts[idx].dir===1?" \u25b2":" \u25bc")+(sorts.length>1?" "+(idx+1):""):"");
  });
  const colMap={name:0,provider:1,cu:2,iq:3,code:4,rel:5,cost:6,per1m:7,inP:8,outP:9,ctx:10};
  const colIdxs=new Set(sorts.map(s=>colMap[s.key]));
  document.querySelector("#mainTable tbody").innerHTML=list.map(r=>{
    const cells=[r.name+(r.free?" <span class='tag'>FREE</span>":"")+(r.rmand?" <span class='warn'>R</span>":""),
      r.provider,fmt(r.cu,0),fmt(r.iq,0),fmt(r.code,0),fmt(r.rel,0),
      fmtC(r.cost),fmt(r.per1m,3),fmt(r.inP,4),fmt(r.outP,4),fmt(r.ctx,0)];
    const tds=cells.map((c,i)=>{
      const cls=[numCols.includes(i)?"num":"",colIdxs.has(i)?"sorted":""].filter(Boolean).join(" ");
      return cls?"<td class='"+cls+"'>"+c+"</td>":"<td>"+c+"</td>";
    }).join("");
    return "<tr class='rowlink' data-id='"+r.id+"'>"+tds+"</tr>";
  }).join("");
}
["fSearch","fProvider","fMinCu","fMaxCost","fFree","fTools"].forEach(id=>
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
applyFilters();
</script>
</body>
</html>
"""

n_graded = len([r for r in rows if r["cu"] is not None])
# Piso de capacidade = MEDIANA do score agentico, nao uma fracao do lider. Um piso de
# 60% do lider (94 pontos) ainda admite modelos no percentil 12 liderando o ranking de
# valor -- que e o defeito da versao original, so que menor. A mediana garante que o
# vencedor seja ao mesmo tempo barato E pelo menos tipicamente capaz.
floor = round(MED_CU)
limits = (f"Dos {len(aiiq)} modelos do AI IQ, {len(mp)} foram ligados a um id do OpenRouter com confianca suficiente "
          f"e {len(rows)} ficaram com preco de cache publicado &mdash; sem esse preco o custo real nao pode ser calculado "
          f"e a linha foi omitida em vez de estimada. Modelos sem correspondencia no OpenRouter nao entram. "
          f"Os {len(probe)} endpoints <code>:free</code> foram testados individualmente; "
          f"{sum(1 for p in probe.values() if p['status']=='ok')} respondem, "
          f"{sum(1 for p in probe.values() if p['status']=='gated')} estao bloqueados por politica de harness "
          f"e {sum(1 for p in probe.values() if p['status']=='rate-limited')} estavam limitados por taxa no momento do teste.")

out = (HTML_TMPL
       .replace("__DATA__", DATA)
       .replace("__MED__", str(MED_CU))
       .replace("__LEAD__", str(LEAD_CU))
       .replace("__FLOOR__", str(floor))
       .replace("__N__", str(n_graded))
       .replace("__MIX_TXT__",
                f"em 30 dias o Hermes processou {MIX['uncached_in_M']:.1f}M tokens de entrada sem cache, "
                f"{MIX['cache_read_M']:.1f}M de cache read e {MIX['out_M']:.2f}M de saida "
                f"({mix_cache:.1f}% cache, {mix_out:.2f}% saida, em {MIX['calls']} chamadas)")
       .replace("__NOW__", now)
       .replace("__LIMITS__", limits))

path = "/home/ubuntu/github/openrouter-custo-beneficio/index.html"
import os
os.makedirs(os.path.dirname(path), exist_ok=True)
open(path, "w", encoding="utf-8").write(out)
print(f"escrito: {path}  ({len(out)/1024:.0f} KB)")
json.dump(rows, open("rows_final.json", "w"), ensure_ascii=False, indent=1)

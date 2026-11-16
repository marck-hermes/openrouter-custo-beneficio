# OpenRouter: custo x beneficio para o Hermes Agent

Dashboard estatico que responde: **qual modelo usar como default do Hermes, considerando
custo real e capacidade agentica?**

- `index.html` — dashboard pronto (HTML unico, sem build, sem dependencia externa)
- `data.json` — as linhas geradas (114 no momento: 110 pagos com IQ ≥ 100 + 4 gratuitos)
- `generate.py` — gera `index.html` e `data.json` a partir de `data/`
- `build_map.py` — liga os ids do AI IQ aos ids do OpenRouter (identidade, nunca valor)
- `refresh.py` — script semanal: fetch AI IQ + precos, join, probe, gera, commit+push
- `data/` — caches versionados: `or_models.json`, `aiiq_v1_models.json`, `mapping.json`,
  `free_probe.json`, `excluded.json`, `arena_elo.json`, `model_speed.json`

Site: https://openrouter-custo-beneficio.vercel.app (atualiza **semanalmente, quinta-feira
00:00** via cron `refresh-openrouter-custo-beneficio-weekly`)

## Por que este dashboard existe

A versao anterior tinha um defeito de origem: a coluna "custo efetivo" caia **fora** do
intervalo entre preco de entrada e preco de saida em **212 de 250** linhas. A causa era o
join — as 8 notas do AI IQ eram ligadas ao modelo pela propria nota, nao pelo id. Seis
modelos de familias diferentes (`amazon/nova-micro-v1`, `amazon/nova-pro-v1`,
`openai/gpt-3.5-turbo-16k`, dois `sao10k`, `thedrummer/unslopnemo-12b`) herdaram as notas
e o custo do `o1` (iq 95, custo efetivo 75,82).

Resultado: o ranking "melhor custo-beneficio" coroava modelos no **percentil 0** de
capacidade agentica, e o verdadeiro lider de custo-beneficio (Gemini 4 Carbon) nem
aparecia, porque estava sem custo efetivo.

## Decisoes que nao sao obvias

**Join por identidade, nao por valor.** `build_map.py` normaliza nome, restringe pela
familia do provider e usa o preco como desempate. Nunca usa a nota como chave. 131 de 211
modelos do AI IQ ligados com confianca suficiente; os ambiguos sao descartados em vez de
adivinhados. 8 modelos foram recuperados com uma regra verificavel: preco de entrada E
saida batendo com o AI IQ (com tolerancia relativa de 30% — o OpenRouter pratica descontos
abaixo da tabela: `qwen3.5-397b` saiu de 0,6/3,6 para 0,45/3,0 e continua sendo o mesmo
modelo).

**Custo com os tres baldes reais de token.** O Hermes grava `input_tokens` **ja liquido de
cache** (`agent/usage_pricing.py`: `input_tokens = prompt_total - cache_read -
cache_write`). Medido em 30 dias de uso real:

| balde | volume | % |
|---|---|---|
| entrada sem cache | 18,6M | 14,9% |
| cache read | 105,9M | 84,6% |
| saida | 0,66M | 0,53% |

Modelar custo como media de entrada e saida ignora 84,6% do volume e a razao real
entrada:saida de ~190:1 (nao 3:1). O efeito e grande: `glm-5.2` parece baratissimo pelo
preco de entrada (US$ 0,007/1M) mas custa **US$ 5,23/mes** por causa da saida a US$ 6,80/1M.

**Gratuitos testados.** Cada `:free` recebe um probe. `inkling-2-small:free` (IQ 126)
retorna `403 "only available on agentic harnesses"` em chamada direta mas responde como
agentic harness — esta sessao roda nele — e entrou com o selo `agentic`. Os demais foram
confirmados por probe.

## Escopo: IQ >= 100

O dashboard usa **um unico universo: IQ >= 100 no AI IQ**. Grafico, ranking de valor,
lista de gratuitos e tabela principal leem o mesmo conjunto — se cada secao aplicasse um
corte proprio a pagina se contradiria.

Nao existe mais a limitacao anterior ("so o que tiver todas as metricas"). Modelo sem nota
nao some: aparece numa tabela auditavel com preco, contexto e suporte a ferramentas.

### Funil de exclusao (fecha em duas identidades)

```
467 entradas no catalogo
 - 86 variantes :batch          (mesmo modelo, desconto)
 - 19 aliases ~                 (apontam para outro)
 -  8 routers com preco < 0
 = 354 modelos unicos
 - 14 variantes :free           (mesmo modelo, preco zero)
 = 340 modelos pagos independentes

   110 pagos analisados (IQ >= 100)
    14 tem nota, mas IQ < 100
   216 sem nota no AI IQ
   ---
   340  <= identidade 1

     4 gratuitos na tabela (IQ >= 100)
     5 respondem, mas sem nota
     5 bloqueados pelo provider
   ---
    14  <= identidade 2
```

Ambas as somas tem `assert` no gerador. 216 sem nota inclui 209 que nao podem ser ligados a
uma entrada do AI IQ + 7 mapeados mas sem nota de capacidade publicada.

### 8 modelos recuperados por preco exato

| AI IQ | OpenRouter | IQ |
|---|---|---|
| `gemini-3.1-pro` | `google/gemini-3.1-pro-preview` | 121 |
| `mistral-large-4` | `mistralai/mistral-large-4-0` | 119 |
| `gemini-3-pro` | `google/gemini-3-pro-image` | 114 |
| `gemini-3-flash` | `google/gemini-3-flash-preview` | 110 |
| `fugu-ultra-v2.0` | `sakana/fugu-ultra-v2` | 109 |
| `qwen3.5-397b` | `qwen/qwen3.5-397b-a17b` | 109 |
| `mistral-medium-3.5` | `mistralai/mistral-medium-3-5` | 102 |

Ficaram de fora os candidatos cujo preco diverge — `nex-n2-pro` -> `nex-n2.5-pro` custa
6x menos, logo e outra geracao, nao o mesmo modelo com nome diferente.

### Os 12 que nao da para incluir

Existem no AI IQ com IQ >= 100 mas **nao existem no OpenRouter** (ou seja, nao sao
chamaveis): `muse-wonder-full` (IQ 133), `agnes-2.5-pro-beta`, `fugu-v1.0`,
`fugu-ultra-v1.1`, `fugu-ultra-v1.0`, `nemotron-3.5-bolt-74b-a9b`, `kat-coder-pro-v1`,
`ling-3.0-flash-fin`, `solar-open2-250b`, `doubao-seed-code`, `ring-2.6-1t`, `k-exaone-2.0`.

## O que veio da tabela LLM Comparison

Este dashboard absorveu os dois sinais uteis da tabela antiga (`token-dashboard/llm-comparison.html`):

- **LMArena Elo** overall + agent + coding — comunidade, com controle de estilo.
  Disponivel no detalhe de cada modelo; o cache semanal cobre 349 modelos.
- **Velocidade medida** — p50 de throughput e latencia via
  `openrouter.ai/api/v1/models/{id}/endpoints` (autenticado; o anonimo devolve null).

A tabela antiga (`llm-comparison.html`) virou redirect para este dashboard. O botao
no `index.html` do token-dashboard aponta para o site novo.

## Piso de capacidade no ranking de valor

O ranking "melhor custo-beneficio" so admite modelos com score agentico **igual ou acima da
mediana do catalogo (118,5 medido via AI IQ Computer Use)**. Ordenar por capacidade-por-dolar
sem piso reproduz o erro original em escala menor: com um piso de 60% do lider, um modelo no
percentil 12 ainda liderava. Com a mediana, o vencedor e ao mesmo tempo barato e pelo menos
tipicamente capaz.

## Resultado (dados de 15/11/2026)

Custo mensal na carga real do Hermes (18,6M entrada + 105,9M cache + 0,66M saida):

| modelo | agente | posicao | US$/mes (mix medido) |
|---|---|---|---|
| DeepSeek V4.1 Flash 1017 | 125 | p74 | **1,18** |
| GPT-6 Luna | 128 | p81 | 3,25 |
| MiMo-V2.6-Flash | 119 | p50 | 3,09 |
| DeepSeek V4.1 Flash | 124 | p70 | 3,33 |

O incumbente `nemotron-3-ultra-550b-a55b` tem score agentico 103 (percentil 23) e custa
**US$ 25,20/mes** — 21x o DeepSeek, com 22 pontos menos.

## Regenerar (quinta 00:00 automatico)

```bash
python3 refresh.py            # tudo: fetch, join, probe, gera, commit+push
python3 refresh.py --skip-probe --skip-deploy
```

`refresh.py`:
1. fetch `openrouter.ai/api/v1/models`
2. fetch `www.aiiq.org/api/v1/models`
3. roda `build_map.py` (join por identidade)
4. probe de 4 tokens em cada `:free` (preserva `inkling-2-small:free` como `agentic`,
   verificado por humano); entries stale (> 7 dias) sao rebuscadas
5. builda `excluded.json` (complemento exato de `rows_all`; a soma fecha por construcao)
6. atualiza `arena_elo.json` (fetch Hugging Face rows; fallback cache) e `model_speed.json`
7. roda `generate.py` (`DASH_DATA=data/ DASH_HTML=./index.html DASH_ROWS=./data.json`)
8. `git commit + git push`; a Vercel faz deploy automatico a cada push (projeto
   Other/static, outputDirectory `.`, git integration)

`OPENROUTER_API_KEY` — precisa estar no `~/.hermes/.env` para os endpoints autenticados
(probe de free + velocidade medida). Sem ela, probe e velocidade ficam no cache.

## Fontes

- AI IQ: `www.aiiq.org/api/v1/models` (notas e precos de tabela, metodologia
  `2026-09-30-arc-predictive-puzzles`)
- OpenRouter: `openrouter.ai/api/v1/models` (precos praticados, contexto, tools)
- Uso real: `~/.hermes/state.db`, tabela `session_model_usage`, janela de 30 dias
- LMArena: `datasets-server.huggingface.co`, dataset `lmarena-ai/leaderboard-dataset`
- Velocidade: `openrouter.ai/api/v1/models/{id}/endpoints`

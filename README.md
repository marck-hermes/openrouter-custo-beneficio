# OpenRouter: custo x beneficio para o Hermes Agent

Dashboard estatico que responde: **qual modelo usar como default do Hermes, considerando
custo real e capacidade agentica?**

- `index.html` — dashboard pronto (HTML unico, sem build, sem dependencia externa)
- `data.json` — as 135 linhas geradas, com todos os campos usados na pagina
- `generate.py` — gera o `index.html` a partir de `data.json`
- `map_models.py` — liga os ids do AI IQ aos ids do OpenRouter
- `probe_free.py` — testa cada endpoint `:free` antes de listar

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

## As tres correcoes

**1. Join por identidade, nao por valor.** `map_models.py` normaliza nome, restringe pela
familia do provider e usa o preco como desempate. Nunca usa a nota como chave. 145 dos 211
modelos do AI IQ foram ligados com confianca suficiente; os ambiguos sao descartados em vez
de adivinhados.

**2. Custo com os tres baldes reais de token.** O Hermes grava `input_tokens` **ja liquido
de cache** (`agent/usage_pricing.py`: `input_tokens = prompt_total - cache_read -
cache_write`). Medido em 30 dias de uso real:

| balde | volume | % |
|---|---|---|
| entrada sem cache | 18,6M | 14,9% |
| cache read | 105,9M | 84,6% |
| saida | 0,66M | 0,53% |

Modelar custo como media de entrada e saida ignora 84,6% do volume e a razao real
entrada:saida de ~190:1 (nao 3:1). O efeito e grande: `glm-5.2` parece baratissimo pelo
preco de entrada (US$ 0,007/1M) mas custa **US$ 5,23/mes** por causa da saida a US$ 6,80/1M.

**3. Gratuitos testados.** `inkling-2-small:free` era o "melhor gratuito" (iq 126) e
retorna `403 "only available on agentic harnesses"` em chamada direta. Cada `:free` agora
recebe um probe de 10 tokens; 11 respondem, 1 esta bloqueado, 2 estavam limitados por taxa.

## Seletor de mix (client-side)

O custo nao e mais um numero fixo no HTML: os precos por token vao para a pagina e o
custo e recalculado no navegador. Dois sliders &mdash; `% cache read` e `% saida` &mdash;
comecam no mix medido (85% / 0,52%) e recalculam tabela, ranking, grafico e detalhe.
Botoes de preset: "Mix medido", "Sem cache", "Cache maximo".

Isso existe porque a escolha do modelo **muda** com o mix, mas so nas posicoes 2-15:
o #1 se manteve em 25 de 25 combinacoes testadas (cache 50-95%, saida 0,3-8%).
Com cache, `kimi-k3` cai 13 posicoes e `claude-haiku-5.5` sobe 3. Reportar so o
numero do mix atual esconderia isso.

## Filtro de IQ

O campo "IQ minimo" **esconde linhas**, nunca altera a nota exibida. Um IQ vindo do
benchmark e imutavel qualquer que seja o filtro; reescreve-lo seria o mesmo defeito do
dashboard original. Com 100, a tabela mostra 119 de 135 linhas. A opcao "manter sem nota"
(ligada por padrao) preserva os modelos que nao tem nota no AI IQ &mdash; senao 8 gratuitos
que respondem ao probe sumiriam do catalogo por nao terem sido medidos.

## Dois bugs de join corrigidos nesta rodada

A primeira versao do `map_models.py` aceitava qualquer prefixo de nome. Isso produziu
**54 pares errados e silenciosos**: `gpt-5` casava com `gpt-5.5`, `opus-5` com `opus-5.5`,
`glm-5.3` com `glm-5.3-flash`, `gpt-6-luna` com `gpt-6-luna-october` (snapshot antigo).
Cada um herdava as notas de outra geracao. A regra correta e estrita:

1. nome normalizado **identico** &rarr; aceito (confianca 100)
2. OpenRouter acrescentou apenas **parametros de tamanho** (`550b-a55b`) &rarr; aceito (80)
3. qualquer outro sufixo e **versionamento** &rarr; rejeitado

Resultado: 121 de 211 mapeados, zero colisoes, zero ambiguos.

O segundo bug: modelos sem preco de cache publicado eram **omitidos**. Isso sumia com
`gemma-4-31b` (IQ 100), `nemotron-3-super-120b` (101) e `qwen3.6-plus` (109) do catalogo.
Agora entram com o preco de **entrada como pior caso**, marcados `cache~` na tabela e
com explicacao no detalhe. Sao 19 linhas assim.

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
 - 14 variantes :free
 = 340 modelos pagos independentes

   110 pagos analisados (IQ >= 100)
    14 tem nota, mas IQ < 100
   216 sem nota no AI IQ
   ---
   340  <= identidade 1

     3 gratuitos na tabela (IQ >= 100)
     8 respondem mas sem nota
     3 bloqueados pelo provider
   ---
    14  <= identidade 2
```

Ambas as somas tem `assert` no gerador. Uma ja falhou durante o desenvolvimento e pegou um
erro real: os 14 pagos abaixo do corte nao estavam sendo contados, e o funil mostrava
`340 != 110 + 216`.

### 8 modelos recuperados por preco exato

O match estrito por nome deixava de fora modelos do AI IQ que existem no OpenRouter com
nome comercial diferente. Foram recuperados com uma regra verificavel: **entrada E saida
batendo exatamente** com o AI IQ.

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

## Piso de capacidade no ranking de valor

O ranking "melhor custo-beneficio" so admite modelos com score agentico **igual ou acima da
mediana do catalogo (114)**. Ordenar por capacidade-por-dolar sem piso reproduz o erro
original em escala menor: com um piso de 60% do lider, um modelo no percentil 12 ainda
liderava. Com a mediana, o vencedor e ao mesmo tempo barato e pelo menos tipicamente capaz.

## Resultado (dados de 15/11/2026)

Custo mensal na carga real do Hermes (18,6M entrada + 105,9M cache + 0,66M saida):

| modelo | agente | posicao | US$/mes (mix medido) |
|---|---|---|---|
| DeepSeek V4.1 Flash 1017 | 125 | p77 | **1,18** |
| MiniMax M3.1 Flash | 115 | p50 | 2,39 |
| Claude Haiku 5.5 | 114 | p47 | 3,25 |
| DeepSeek V4.1 Flash | 124 | p74 | 3,33 |

O incumbente `nemotron-3-ultra-550b-a55b` tem score agentico 103 (percentil 23) e custa
**US$ 25,20/mes** — 21x o DeepSeek, com 22 pontos menos.

## Regenerar

```bash
curl -s https://openrouter.ai/api/v1/models -o or_models.json
curl -sL https://www.aiiq.org/api/v1/models -o aiiq_v1_models.json
python3 map_models.py       # gera mapping.json
python3 probe_free.py       # gera free_probe.json
python3 generate.py         # gera index.html
```

## Fontes

- AI IQ: `www.aiiq.org/api/v1/models` (notas e precos de tabela, metodologia
  `2026-09-30-arc-predictive-puzzles`)
- OpenRouter: `openrouter.ai/api/v1/models` (precos praticados, contexto, tools)
- Uso real: `~/.hermes/state.db`, tabela `session_model_usage`, janela de 30 dias

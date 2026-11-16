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

## O dashboard esconde modelos? Sim — e agora mostra quais

O catalogo do OpenRouter tem 467 entradas; a tabela analisa 135. A diferenca e
grande o suficiente para precisar de contabilidade visivel, entao existe um card
"O que ficou de fora (e por que)" com o funil completo e uma tabela auditavel:

```
467 entradas no catalogo
 - 86 variantes :batch       (mesmo modelo, com desconto)
 - 19 aliases ~              (apontam para outro modelo)
 -  8 routers com preco < 0  (openrouter/auto, fusion, pareto-code...)
 = 354 modelos unicos
 - 14 variantes :free        (mesmo modelo, preco zero)
 = 340 modelos pagos independentes

   124 pagos analisados  +  11 gratuitos que respondem  =  135 na tabela
   216 pagos sem nota    +   3 gratuitos nao respondem  =  fora
```

As duas somas fecham: `124 + 216 = 340` e `11 + 3 = 14`. O gerador tem `assert`
para as duas — um funil que nao fecha e pior que nao ter funil.

**A razao real de 216 modelos ficarem fora: eles nao tem nota no AI IQ.** Nao e
filtro de preco, contexto ou ferramentas. O AI IQ avalia 211 modelos; os 216 restantes
sao em sua maioria modelos antigos ou pequenos (`llama-3.1-8b`, `gemma-3-4b`,
`mixtral`, `command-r`) que nunca foram medidos. Sem nota de capacidade nao existe
"capacidade por dolar", entao nao entram no ranking.

Mas eles **nao ficam invisiveis**: a tabela de exclusao lista os 216 com preco de
entrada, saida, contexto e suporte a ferramentas, ordenavel. Se voce ja sabe que um
deles serve, o custo mensal e calculavel — o que falta e so a nota.

### Dois caminhos possiveis se 216 for demais

1. **Ampliar a fonte de notas.** O AI IQ e a unica fonte com cobertura de dimensao
   agentica (`computer-use`). Alternativas como LMArena cobrem mais modelos mas nao
   tem score agentico, e misturar fontes numa mesma coluna torna a coluna ilegivel.
2. **Trocar o eixo de ordenacao para metrica de catalogo.** Se a pergunta for "qual o
   mais barato que suporta ferramentas com contexto > 100k", nao precisa de nota — e o
   dashboard ja permite filtrar por preco, contexto e `function calling`.

O que nao vale e preencher a nota ausente com heuristica por nome: `'flash'` = rapido
e `'mini'` = fraco erram nos dois sentidos.

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

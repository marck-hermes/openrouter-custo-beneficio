# OpenCode Zen × OpenRouter — consolidação (2026-11-16)

Comparação para uso esporádico de modelos frontier pelo Hermes Agent, cruzando a tabela oficial do **OpenCode Zen** com os dados locais do dashboard (`data/`).

Script: `zen_compare.py` (re-executável; lê `data/aiiq_v1_models.json`, `data/or_models.json`, `data/arena_elo.json`)
Saída: `zen_compare.md` (tabela legível), `zen_compare.csv` (todas as colunas)

---

## O que é o OpenCode Zen

OpenCode (open-source, MIT, `anomalyco/opencode`) tem três níveis de acesso a modelos:

1. **Cliente OpenCode** — grátis, open source. *Não inclui inference grátis.*
2. **OpenCode Zen (Console)** — pay-as-you-go por token, API em `https://opencode.ai/zen/v1/`. Modelos curados, testados e verificados pela equipe. Free-tier chat models existem **apenas dentro do cliente** (não via API pública).
3. **OpenCode Go** — assinatura mensal de **uso fixo com limite** (ex: mensal/semanal/rolling), quota esgotada bloqueia. Abaixo de $0 listado.

A tabela Zen completa tem **29 modelos** (snapshot 2026-11-16 de `opencode.ai/console/models`; a página estática corta no "Grok 4.7", as últimas 7 linhas vieram do DOM renderizado).

---

## Resposta rápida: Zen é mais caro que OpenRouter?

**Para frontier (Claude, GPT, Gemini 4, Grok 4.7, GPT-6.x): não.** Os preços são idênticos nas duas plataformas (0% de markup em Zen ou OR).

**Nos open-weights: sim, e muito.** A diferença aparece onde o OpenRouter roteia para o *provider mais barato disponível* enquanto o Zen pratica preço fixo de lista:

| Zen model | Zen $in/out | OR equiv | OR $in/out | Δ in | Δ out |
|---|---|---|---|---|---|
| DeepSeek V4 Pro | $1.74/$3.48 | `deepseek/deepseek-v4-pro` | $0.90/$1.50 | +93.3% | +132.0% |
| DeepSeek V4.1 Flash | $0.30/$1.20 | `deepseek/deepseek-v4.1-flash` | $0.14/$0.42 | +114.3% | +185.7% |
| GLM-5.3 | $1.40/$4.40 | `z-ai/glm-5.3` | $0.07/$1.40 | +1.903% | +214.3% |
| GLM-5.3-Flash | $0.15/$0.50 | `z-ai/glm-5.3-flash` | $0.04/$0.08 | +276% | +538% |
| Gemini 3.8 Flash | $1.50/$7.50 | `google/gemini-3.8-flash` | $0.825/$4.125 | +82% | +82% (OR é metade exata) |
| Kimi K2.7 Code | $0.95/$4.00 | `moonshotai/kimi-k2.7-code` | $0.60/$3.50 | +58.3% | +14.3% |
| Kimi K3 | $3.00/$15.00 | `moonshotai/kimi-k3` | $0.19/$16.00 | +1.462% | −6.2% |
| Mistral Large 4 | $0.68/$2.09 | `mistralai/mistral-large-4-0` | $0.70/$2.10 | **−2.9%** | **−0.5%** |
| Qwen3.8 Flash | $0.15/$0.47 | `qwen/qwen3.8-flash` | $0.15/$0.47 | 0.0% | 0.0% |

> ⚠️ As divergências grandes (GLM, DeepSeek) podem refletir SKUs diferentes no OR (quantizado/preview/self-hosted). O join Zen×OR é por identidade, nunca preço — mesma regra do `build_map.py`. Confirmar provider antes de concluir.

**Empates (+0.0%):** Claude Fable/Haiku/Opus/Sonnet 5.5, Gemini 3.5 Flash Lite, Gemini 4 Argon, Gemini 4 Carbon ($2.00/$10.00), GPT-5.3 Codex, GPT-5.4 Mini/Nano, GPT-5.5, GPT-5.5 Pro, GPT-5.6 Terra, GPT-6 Astra/Luna/6.1 Sol, Grok 4.7, Grok Build 0.1, MiniMax-M3, Qwen3.8 Flash.

**Sem par no OR (28/29 casam):** `GPT-5.3 Codex Spark` — existe no Zen, não está no catálogo OpenRouter.

---

## Taxas de depósito e operação

| Item | **OpenRouter** | **OpenCode Zen** |
|---|---|---|
| Depósito mínimo | **$5** | **$10** (botões $10/$50/$100 ou "Other"/custom) |
| Taxa na compra | 5,5% cartão + **$0,80 mín** → $5 custa $5,80 (16%); $10 → $10,80 (8%); 5% crypto | **4,6% + $0,31** → $10 custa $10,77 (7,7%); $50 custa $52,61 |
| Expiração de crédito | Direito reservado a expirar em **365 dias** | Sem regra pública documentada |
| Refund | Até 24h da transação | Não documentado publicamente |
| Métodos | Card, Alipay, USDC | Card, Link, Alipay, UPI, WeChat Pay |
| Invoice | Não (só créditos) | Sim, com acordo mensal (credit limit) |

Para **uso esporádico**: a diferença de fee é de centavos ($10: $10,77 vs $10,80). Não é fator decisivo.

---

## O que o OR tem e o Zen não (e vice-versa)

**OpenRouter:**
- **Free tier** real: 20 req/min, 50 req/day; 1.000/dia após $10 em compras.
- **Variantes `:batch`** a −50% do preço (ex: Gemini 3.8 Flash $0.825/$4.125).
- **Roteamento automático** para o provider mais barato + fallback entre providers.
- Catálogo de centenas de modelos, inclusive o Qwen4 Max (lançado 15/11) e os GLM-5.3 baratos.

**Zen (vantagens):**
- Integração nativa com o cliente OpenCode (1 chave, sem BYOK), modelos curados e verificados.
- 429/402 tratados no cliente; cobrança por request com balance exato (nunca negativo).
- Workspaces com múltiplos membros e invoice mensal.

**Zen (limitações):**
- Só os 29 modelos — sem rotas alternativas para os mesmos modelos.
- Sem `:free` sondável via API; free-tier só no cliente.
- Sem `:batch`; preço fixo de lista mesmo nos open-weights mais caros.

---

## Método do join (`zen_compare.py`)

- **Identidade, nunca preço** (regra do repo, ver `build_map.py`):
  `norm(s)` = lowercase → strip `:free`/`:batch` → strip `~` → `split('/')[-1]` → strip `^claude-` → strip vendor prefix (`google-|openai-|anthropic-|…`) → strip `-it$` → remover tudo fora `[a-z0-9]`.
- **AI IQ**: mesmo `ai_norm`; `claude-` prefix removido porque o AI IQ identifica Anthropic sem prefixo (`fable-5.1`).
- **OpenRouter**: `or_models.json` → `or_by[ai_norm(id)]`; prefere a variante **normal** sobre `:batch`/`:free` (`:batch` às vezes custa metade e mascararia a comparação real). `:free` não entra para modelos Zen (todos Zen são pagos).
- **ELO Arena**: join por slug `[a-z0-9]` do id AI IQ ou do nome; `arena_elo.json` local (snapshot 2026-11-15).
- **Velocidade (tps/lat)**: `model_speed.json` cobre só endpoints `:free` do OR → **todos os Zen ficam de fora** (Zen não tem `:free` sondável).
- **Aliases manuais**: `mistral-large-4` → `mistral-large-4-0`.

Cobertura: AI IQ **26/29** (falta GPT-5.3 Codex Spark, GPT-5.5 Pro, Grok Build 0.1). OpenRouter **28/29** (falta GPT-5.3 Codex Spark). ELO **19/29**.

---

## Conclusão prática

Para uso esporádico do Hermes com modelos frontier, **Zen e OpenRouter saem pelo mesmo preço por request**. A diferença que importa:

1. **Quer economizar em open-weights** → OpenRouter (teacher routing + `.batch` corta DeepSeek/Gemini 3.8 pela metade).
2. **Quer simplicidade de chave única integrada ao OpenCode** e não se importa com pagar lista → Zen empata nos frontier; só paga premium nos open-weights.
3. **Quer experimentar sem gastar nada** → OpenRouter free tier (20 rpm / 50 day).
4. **OpenRouter tem catálogo muito maior** (Qwen4 Max, novos lançamentos aparecem lá antes do AI IQ pontuar).

Recomendação para o Hermes default: **manter OpenRouter como primário**. Zen só faz sentido se/quando o projeto migrar para a stack OpenCode como harness principal.

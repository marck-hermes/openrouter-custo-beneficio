# OpenCode Zen × OpenRouter — comparação ($/1M tokens)

Fonte preços Zen: opencode.ai/console/models (2026-11-16). AI IQ: snapshot local; ELO: arena_elo.json local.

| Zen model | Zen $in/out | OR equiv | OR $in/out | Δ in | Δ out | AI IQ (ψ) | Cov | Ctx | ELO |
|---|---|---|---|---|---|---|---|---|---|
| Claude Fable 5.1 | $10.0/$50.0 | `anthropic/claude-fable-5.1` | $10.0/$50.0 | +0.0% | +0.0% | 138 | 7/7 | 1000000ctx | — |
| Claude Haiku 5.5 | $0.1/$0.5 | `anthropic/claude-haiku-5.5` | $0.09999999999999999/$0.5 | +0.0% | +0.0% | 122 | 7/7 | 1000000ctx | — |
| Claude Opus 5.5 | $4.0/$20.0 | `anthropic/claude-opus-5.5` | $4.0/$20.0 | +0.0% | +0.0% | 140 | 7/7 | 1000000ctx | — |
| Claude Sonnet 5.5 | $2.0/$10.0 | `anthropic/claude-sonnet-5.5` | $2.0/$10.0 | +0.0% | +0.0% | 137 | 7/7 | 1000000ctx | — |
| DeepSeek V4 Pro | $1.74/$3.48 | `deepseek/deepseek-v4-pro` | $0.8999999999999999/$1.5 | +93.3% | +132.0% | 122 | 7/7 | 1000000ctx | 1457.9 |
| DeepSeek V4.1 Flash | $0.3/$1.2 | `deepseek/deepseek-v4.1-flash` | $0.14/$0.42 | +114.3% | +185.7% | 125 | 7/7 | 1000000ctx | — |
| Gemini 3.5 Flash Lite | $0.3/$2.5 | `google/gemini-3.5-flash-lite` | $0.3/$2.5 | +0.0% | +0.0% | 104 | 7/7 | 1000000ctx | 1454.9 |
| Gemini 3.8 Flash | $1.5/$7.5 | `google/gemini-3.8-flash` | $0.8250000000000001/$4.125 | +81.8% | +81.8% | 129 | 7/7 | 1048576ctx | 1496.7 |
| Gemini 4 Argon | $2.0/$10.0 | `google/gemini-4-argon` | $2.0/$10.0 | +0.0% | +0.0% | 139 | 7/7 | — | 1521.7 |
| GLM-5.3 | $1.4/$4.4 | `z-ai/glm-5.3` | $0.0699/$1.4 | +1902.9% | +214.3% | 124 | 7/7 | 1000000ctx | 1481.6 |
| GLM-5.3-Flash | $0.15/$0.5 | `z-ai/glm-5.3-flash` | $0.0399/$0.0784 | +275.9% | +537.8% | 119 | 7/7 | 1000000ctx | 1475.3 |
| GPT-5.3 Codex | $1.75/$14.0 | `openai/gpt-5.3-codex` | $1.75/$14.0 | +0.0% | +0.0% | 112 | 5/7 | 400000ctx | — |
| GPT-5.3 Codex Spark | $1.75/$14.0 | `—` | — | — | — | — | — | — | — |
| GPT-5.4 Mini | $0.75/$4.5 | `openai/gpt-5.4-mini` | $0.75/$4.5 | +0.0% | +0.0% | 111 | 7/7 | 400000ctx | 1447.3 |
| GPT-5.4 Nano | $0.2/$1.25 | `openai/gpt-5.4-nano` | $0.19999999999999998/$1.25 | +0.0% | +0.0% | 106 | 7/7 | 400000ctx | 1401.0 |
| GPT-5.5 | $5.0/$30.0 | `openai/gpt-5.5` | $5.0/$30.0 | +0.0% | +0.0% | 128 | 7/7 | 922000ctx | 1476.1 |
| GPT-5.5 Pro | $30.0/$180.0 | `openai/gpt-5.5-pro` | $30.0/$180.0 | +0.0% | +0.0% | — | — | — | — |
| GPT-5.6 Terra | $2.0/$12.0 | `openai/gpt-5.6-terra` | $2.0/$12.0 | +0.0% | +0.0% | 130 | 7/7 | 1000000ctx | 1467.9 |
| GPT-6 Astra | $10.0/$50.0 | `openai/gpt-6-astra` | $10.0/$50.0 | +0.0% | +0.0% | 139 | 7/7 | 1050000ctx | 1473.9 |
| GPT-6 Luna | $0.1/$0.5 | `openai/gpt-6-luna` | $0.09999999999999999/$0.5 | +0.0% | +0.0% | 125 | 7/7 | 1050000ctx | 1440.9 |
| GPT-6.1 Sol | $2.0/$10.0 | `openai/gpt-6.1-sol` | $2.0/$10.0 | +0.0% | +0.0% | 141 | 7/7 | 1050000ctx | 1480.8 |
| Grok 4.7 | $2.0/$6.0 | `x-ai/grok-4.7` | $2.0/$6.0 | +0.0% | +0.0% | 127 | 7/7 | 500000ctx | 1443.3 |
| Grok Build 0.1 | $1.0/$2.0 | `x-ai/grok-build-0.1` | $1.0/$2.0 | +0.0% | +0.0% | — | — | — | — |
| Kimi K2.7 Code | $0.95/$4.0 | `moonshotai/kimi-k2.7-code` | $0.6/$3.5 | +58.3% | +14.3% | 111 | 7/7 | 256000ctx | — |
| Kimi K3 | $3.0/$15.0 | `moonshotai/kimi-k3` | $0.192/$16.0 | +1462.5% | -6.2% | 127 | 7/7 | 1048576ctx | 1487.4 |
| MiniMax-M3 | $0.3/$1.2 | `minimax/minimax-m3` | $0.3/$1.2 | +0.0% | +0.0% | 114 | 7/7 | 1000000ctx | — |
| Mistral Large 4 | $0.68/$2.09 | `mistralai/mistral-large-4-0` | $0.7/$2.0999999999999996 | -2.9% | -0.5% | 119 | 6/7 | 1000000ctx | 1420.4 |
| Muse Wonder | $4.0/$20.0 | `meta/muse-wonder` | $4.0/$20.0 | +0.0% | +0.0% | 129 | 6/7 | 1048576ctx | 1510.9 |
| Qwen3.8 Flash | $0.15/$0.47 | `qwen/qwen3.8-flash` | $0.15/$0.47 | +0.0% | +0.0% | 116 | 4/7 | 1000000ctx | — |

Sem nota AI IQ: GPT-5.3 Codex Spark, GPT-5.5 Pro, Grok Build 0.1
Sem par OpenRouter: GPT-5.3 Codex Spark
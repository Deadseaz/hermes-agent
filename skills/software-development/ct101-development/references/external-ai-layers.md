# External AI layers — configured vs on the decision path

Use this when asked whether Cloudflare, Ollama, sentiment or the 50-year history are
"harnessed". Separate three states: configured, reachable, and called by the decision
loop. Only the third changes a trade.

## Cloudflare

Configured in `.env`: KV (`tradeengine-kv`), five D1 databases, Vectorize
(`agent-memory`, `ai-embeddings`), Workers AI (`@cf/meta/llama-3.1-8b-instruct`),
R2 (`agent-storage`), Durable Objects (`AgentSessionDO`), tunnel.

Code usage: `infrastructure/cloudflare/*`, `d1_integration`, `embedding_service`,
`knowledge_store`, and the memory vault's pgvector/Vectorize dual-write. It is
memory/embedding/infrastructure, not a signal source. `MomentumTurboBot`,
`CppMemoryAwareBot` and the backtest loop do not read it.

## Ollama

Live at `10.1.1.99:11434` with:

```
trade-pattern-8b  trade-sentiment-8b  trade-memory-3b
qwen3.8  qwen3:14b  deepseek-r1:8b  mxbai-embed-large  nomic-embed-text
```

Wiring status:

| model | code | called by |
|---|---|---|
| `trade-pattern-8b` | `domain/ai_growth/services/pattern_model_inference.py` | only `CppMemoryAwareBot`, throttled 300 s, only on actionable decisions |
| `trade-sentiment-8b` | `domain/alpha_generation/services/sentiment_model_inference.py` | **no callers** outside its module |
| `trade-memory-3b` | `domain/memory_learning/services/memory_model_inference.py` | only the `confidence_memory_recall` capability |
| sentiment provider | `domain/backtesting/strategies/ollama_sentiment.py` | optional `OllamaSentimentProvider`; `run_bot_real.py` / `run_domain_year.py` do not pass it |

### Diagnosing "Ollama failing to connect"

The configured host lives in `.env` (`OLLAMA_HOST`, observed `10.1.1.99:11434`) — do not guess CT100/CT101 from the topology. A daemon is *up* if `GET /api/version` answers, but that says nothing about call latency. A `ReadTimeout` in the app with a responding `/api/version` means a slow model load/run, not a dead server. Time the **exact** endpoint the app calls with the **exact** model it uses — `POST /api/embeddings` with `mxbai-embed-large:335m` — using `time curl … -w "time_total"`. On this shared box (12+ models) a cold embed takes ~17-37 s, while `embedding_service.py` gives the call `timeout=10.0`, so it logs `Ollama embed error: ReadTimeout` while every other consumer works. Check `GET /api/ps` for which models are actually loaded (only `gemma4:12b` + `trade-sentiment-8b` were) before blaming the network.

## Sentiment

`TwitterSentimentAnalyzer.is_active = False`. Postgres `kb.sentiment_history`
holds ~411k rows with `created_at` / `text_hash` (no `symbol` column); only
`cluster_ai` reads it. The bot/backtest path does not join historic sentiment.

## Historic bars

`data/historical_50year/*.db` covers 2004-09 → 2025-01 = **21 years**, 9,671 symbols,
~25.4M bars. It is not 50 years. `kb.market_data` is empty; `kb.clusterai_setups`
(922,901) and `kb.clusterai_bar_windows` (144,335) are the memory stores.

## Rule

When the user asks "are we harnessing X", answer with the table above and say
plainly which layers are configured but not on the decision path. Wiring one in is a
code change with a test, not a configuration claim.

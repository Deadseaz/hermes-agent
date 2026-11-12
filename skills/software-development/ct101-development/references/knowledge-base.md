# Knowledge base — where the data lives and whether it reaches decisions

There are two different stores, and they answer different questions:

- **`clusterai_setups` + `clusterai_bar_windows`** — the historic memory the live
  buy loop actually recalls. Wired through `infrastructure/ai/setup_recall.py` and
  visible in `cluster_ai` logs as `setup recall <SYM>: similar-wr …`.
- **`memory_patterns`** — the C++ pattern-hash store. 41,590,910 rows, only 22,392
  with outcomes, and hex-keyed. A miss here says nothing about the other store.

Prove the lookup in the store the decision path reads before claiming the system
learns from history.

## Storage map

**Postgres `kb` @ 10.1.1.102** (`pgvector` extension installed):

| table / column | rows | note |
|---|---|---|
| `clusterai_setups` | 922,901 | 6-d pgvector `features`, resolved `outcome`; live recall source |
| `clusterai_bar_windows` | 144,335 | 1,314 symbols, 1962→2025, 1024-d `embedding`, `fwd_return_20d` |
| `document_chunk.vector` | 19,586,813 | real `vector` column |
| `embeddings.embedding` | 19,586,813 | `float8[]`, not a vector type |
| `memory_patterns` | 41,590,910 | 22,392 with `observations > 0`; avg confidence 0.499999 |
| `memory_entries` | 49,336 | semantic memories |
| `sentiment_history` | 411,295 | |
| `strategy_outcomes` | 67,988 | |
| `market_data` | **0** | bars were never ingested |

**Cloudflare**: D1 databases are configured (`CF_D1_DATABASE_ID`, `D1_TRADE_ENGINE_ID`,
`D1_MASTER_CONTROL_ID`, `D1_TRADING_MEMORY_ID`, `D1_AGENT_DB_ID`,
`D1_TRADEZ_MASTER_CONTROL_ID`) and Vectorize indexes `market-data-768`, `system-kb-768`,
`agent-memory`, `tradeengine-vectors`. Management-API calls need `MCP_HUB_BASE_URL`
(`http://10.1.1.112:3000`), not `MCP_HUB_URL`, which ends in `/mcp`.

**SQLite on CT101**: `data/historical_50year/*.db` — 25,454,907 bars, 9,671 symbols,
2004-09 → 2025-01. `data/historical_data.db` `bars` table is empty.

## The hash-representation trap

`memory_patterns.pattern_hash` stores **lower-case hex text** (`98797b3eff2bf9ea`).
`tradeengine_core_binding.pattern_hash(...)` returns a **uint64 decimal**. Convert at
the boundary:

```python
format(h, '016x')      # DB lookup
int(hex_string, 16)    # C++ store call
```

A decimal-string lookup always misses, and `core_get_confidence_boost` returns `1.0`
for an unknown hash — indistinguishable from a neutral result. Test with a hash known
to exist: `core.get_confidence_boost(int('98797b3eff2bf9ea', 16))` returned `1.0`
while the row holds confidence 1.0 / 31 observations. That proves the C++ store is
not reading Postgres.

## Decision-path wiring

`ConfidenceBooster.calculate_confidence` uses the C++ store when the pattern id is all
digits, then the Python dict, then `recall_source` (MVO), then `cb_pattern_prior`.
There is no Postgres fallback on a C++ miss, and `recall_source` was `None` until the
manifest attached `mvo`. Health shows it: `ct101:health:confidence-memory-recall`
`confidence_booster.detail` must contain `recall_source=wired`.

## Verification

```bash
# per-year regime + windows/setups held for that year + a time-respecting
# setup-recall AUC (neighbours must be strictly older)
/home/claude/timeshift/ct101/venv/bin/python scripts/verify_historic_knowledge.py \
    --symbol SPY --from 2007 --to 2024
```

A working state detects a regime every year, reports non-zero `windows`/`setups`
coverage, and returns an AUC well above 0.5 on the recall replay. The old
`0/18` result came from querying `memory_patterns` by a C++-computed hash; it did NOT
mean the system had no memory.

## Replay the exact live query

`setup_recall.similar_win_rate` is the production path. Replay it with neighbours
strictly older than the sample, then compare predicted win rate with the realised
outcome:

```sql
SELECT s.outcome, k.pred FROM sample s
LEFT JOIN LATERAL (
  SELECT avg(x.outcome) AS pred FROM (
    SELECT o.outcome FROM clusterai_setups o
    WHERE o.outcome IS NOT NULL AND o.ts < s.ts
    ORDER BY o.features <-> s.features LIMIT 40
  ) x
) k ON true
```

Measured on 454 samples from 2015–2025: AUC 0.879, base win rate 20.7%, top
quintile predicted 71.7% / actual 67.0%. A flat 0.5 prediction or an AUC near 0.5
means the recall is not discriminating.


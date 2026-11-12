# KB Verification Queries

## When to use

When diagnosing a system that appears "not wired" or claims data is "not loaded". Before assuming the KB is empty, pattern memory is missing, or historic embeddings never backfilled, run these queries to confirm actual state.

## Prerequisites

- Access to the deployed `.env` (worktree at `/root/.sesori/worktrees/<id>/<name>/` is the running system)
- `psql` client with access to 10.1.1.102:5432 (the KB database)

## Extract credentials from .env

```bash
# Read from the deployed worktree, not the session checkout
cd /root/.sesori/worktrees/<id>/<name>  # or wherever the system runs from
PG_PASSWORD=$(grep '^POSTGRES_PASSWORD=' .env 2>/dev/null | head -1 | cut -d= -f2 | tr -d '"' | tr -d "'")
echo "Password extracted (masked): ***"
```

## Verification-First Diagnosis (Most Common Mistake)

**WRONG:** "The system claims historic data is loaded but I see stale patterns, so embeddings must not be backfilled."
**RIGHT:** Query the tables first, distinguish real from corrupted, then claim state.

**Sequence that works:**

1. **Query counts and dates (proven from DB, not assumptions):**
   ```bash
   # Is bar_windows populated?
   psql -h 10.1.1.102 -U postgres -d kb -c "SELECT COUNT(*), MIN(window_end), MAX(window_end) FROM clusterai_bar_windows WHERE embedding IS NOT NULL;"
   # Is setups populated?
   psql -h 10.1.1.102 -U postgres -d kb -c "SELECT COUNT(*) as total, COUNT(CASE WHEN origin='live' THEN 1 END) as live, COUNT(CASE WHEN origin='suite' THEN 1 END) as suite FROM clusterai_setups;"
   # Is memory populated with real observations?
   psql -h 10.1.1.102 -U postgres -d kb -c "SELECT COUNT(*) as total, COUNT(CASE WHEN observations > 0 THEN 1 END) as with_observations FROM memory_patterns;"
   ```

2. **Interpret the results (cite counts, not assumptions):**
   - "1.24M embeddings, all with data, 1962–2025" (real KB state)
   - "922K setups: 686K broken (origin='live'), 237K clean (origin='suite')" (not "922K setups")
   - "42M patterns total, only 22.7K with observations" (real learning state, not "patterns are missing")

3. **When the user says "we never had this fully integrated", discard 'live' data:**
   ```bash
   # Report only clean data
   psql -h 10.1.1.102 -U postgres -d kb -c "SELECT COUNT(*) FROM clusterai_setups WHERE origin IN ('suite', 'historic', 'backtest');"
   ```
   This is the true KB for the current integrated system. 'live' rows are from broken prior runs.

4. **Answer the direct question first:**
   User: "Is historic data loaded?"
   WRONG: "The backfill should have run."
   RIGHT: "SELECT COUNT(*) FROM clusterai_bar_windows: **1.24M rows, all embedded, 1962–2025.**"


## KB row counts and data presence (Full Audit)

```bash
PGPASSWORD="$PG_PASSWORD" psql -h 10.1.1.102 -U postgres -d kb -c "
  SELECT 
    'clusterai_bar_windows' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN embedding IS NOT NULL THEN 1 END) as with_embeddings,
    COUNT(DISTINCT symbol) as distinct_symbols,
    MIN(window_end) as earliest_date,
    MAX(window_end) as latest_date
  FROM clusterai_bar_windows
  UNION ALL
  SELECT 
    'clusterai_setups',
    COUNT(*),
    0,
    COUNT(DISTINCT symbol),
    MIN(ts)::date,
    MAX(ts)::date
  FROM clusterai_setups
  UNION ALL
  SELECT 
    'memory_patterns',
    COUNT(*),
    COUNT(CASE WHEN observations > 0 THEN 1 END),
    0,
    MIN(updated_at)::date,
    MAX(updated_at)::date
  FROM memory_patterns;
"
```

### Interpreting the results

| Condition | Meaning | Action |
|-----------|---------|--------|
| `clusterai_bar_windows.total_rows = 0` | Historic embeddings never backfilled | Check if backfill script ran; expected ~1.24M rows from 50-year DB |
| `bar_windows.with_embeddings < bar_windows.total_rows` | Some embeddings missing | Check Ollama logs for timeout/GPU contention (see `references/diagnose-embedding-starvation.md`) |
| `clusterai_setups.total_rows > 0` | Live and backtest trades are recorded | Good — the KB is accepting data |
| `memory_patterns.with_embeddings (observations col)` << total | Most patterns are stale | Normal — only recently-observed patterns matter; expect 20-50K real out of 40M+ total |
| All zeros | KB is empty or DB connection failed | Verify `POSTGRES_HOST` and credentials; check if `kb` database was reset |

## Decision Flow Confirmation (Upstream Gate Check)

When the KB has data but nothing trades, **don't debug memory/SNN/booster yet**. Check if decisions are even publishing (gate verification):

```bash
redis-cli -h 10.1.1.102 LLEN bot:decisions          # Total decision entries
redis-cli -h 10.1.1.102 LRANGE bot:decisions -1 0   # Newest entry timestamp
tail -300 /logs/ct101.log | grep -E 'capital|portfolio|Hours|resubscribe.*fail'  # Which blocker?
```

**Interpretation:**
- **Empty (0)** → no decisions published. **This is the diagnostic question.** Check logs for blocker (capital, hours, resubscribe). Do NOT blame memory/SNN/booster until you fix the gate. Reference: `references/decision-gate-blockers.md`.
- **Stale timestamp** (>10 min old) → decisions published once, then stopped. Likely resubscribe crash (transient Redis failure) or capital/hours gate change. Check resubscribe pattern in logs.
- **Recent timestamp** → decisions are flowing. Gate is open. Skip to consumer diagnostics (SNN, memory-fill-sub logs).

## Example output (healthy KB state, 2026-11-09)

```
        table_name        | total_rows | with_embeddings | distinct_symbols | earliest_date | latest_date 
---------------------------+------------+-----------------+------------------+---------------+-------------
 clusterai_bar_windows     |    1244497 |        1244497  |              9425 | 1962-03-27    | 2025-12-08
 clusterai_setups         |     922901 |              0  |               374 | 1962-02-14    | 2026-09-17
 memory_patterns          |   42231352 |          22742  |                 0 | 2026-04-28    | 2026-11-09
```

Reading this:
- Bar windows: 1.24M embeddings covering 1962–2025, all symbols
- Setups: 923K recorded trades from live and backtest
- Patterns: 42M total (mostly defaults), 22.7K with actual trading observations (good — stale patterns don't hurt)

## Pitfalls

- **Row counts are stale immediately.** If the system trades actively, querying once per hour shows different totals. Use these queries to diagnose state "right now", not to predict future row counts.
- **"Data in KB" ≠ "data in use on the decision path." The live bot reads from `kb.clusterai_setups` for setup recall and `kb.memory_patterns` for confidence checks. The `.db` files on disk are read only by training scripts, not the live loop.
- **High row count in memory_patterns + low observations count is normal, not broken.** Most patterns are defaults seeded at init; only patterns with `observations > 0` are proven.
- **When the user says "we've never had this fully working", discard all rows labeled `origin='live'`.** Rows from broken production runs are noise, not history. Report only `origin='historic'` (50-year backfill) and `origin='suite'` (backtest runs). If you cite the 686K 'live' setups as "the system has 686K setups", you are misrepresenting broken data as current capability.

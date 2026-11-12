# Historic Embedding Audit

**When to use:** kb.clusterai_bar_windows is incomplete (144K rows of 1.13M expected), or live recall is missing patterns.

## The requirement

- Expected: ~1.13M embedding windows from 50-year archive (2004–2025, 20-bar stride, 9,256 symbols)
- Plus CT115 pre-archive (1962–2006): ~1.4–1.5M total rows in kb.clusterai_bar_windows
- Each window: 1024-dim embedding + fwd_return_20d target

## Current state (2026-11-09)

- Actual: 144,335 rows (single one-off 2026-09-06, uncommitted external script)
- Gap: years 2001–2014 empty, 1962–2003 missing
- Verification: `git log -S clusterai_bar_windows --all -- '*.py'` returns zero in-repo writers

## Two independent failures

### 1. Zero in-repo embedding writers

**Diagnosis:**
```bash
cd /home/claude/timeshift/ct101
git log -S 'clusterai_bar_windows' --all -- '*.py' | wc -l  # Should find writers; if 0, nothing fills the table
ls -la infrastructure/ai/*embed*.py | grep -v __pycache__  # What embedding code exists
grep -r 'INSERT INTO.*clusterai_bar_windows' . | grep -v '.git'  # Nothing should match
```

**Root cause:** The backfill job ran once (2026-09-06) outside the repo as an ad-hoc script. The pipeline that SHOULD feed it is:
- A script that loads the 50-year `.db` files (data/historical_50year/global_markets_50year.db + 2005.db + 2006_2007.db)
- Calls `/api/embed` on Ollama (not EmbeddingService — see constraint failure below)
- UPSERTs into kb.clusterai_bar_windows with proper column coverage

**Fix:** Create `scripts/backfill_historic_embeddings.py` with:
- Read bars from historical_50year/*.db in 20-bar windows
- Batch POST to `/api/embed` with timeout=300, keep_alive=30m (not 10s)
- Dedupe via `WHERE NOT EXISTS (SELECT 1 FROM clusterai_bar_windows WHERE symbol=? AND ts=?)`
- Run nightly or manually; full job ~11 months at current 0.04–0.06 embeds/s (Ollama GPU contention issue)

### 2. Dual constraint failures on live setup recall

**The two bugs:**

1. **EmbeddingService timeout**: `embedding_service.py` lines 169/192/220 hardcode `timeout=10.0` seconds. Ollama averages 14–109 s per embed → ~100% timeout failure for uncached embeddings.
   ```python
   # BUG: timeout=10.0
   response = requests.post(..., timeout=10.0)
   # FIX: use timeout=300 or call /api/embed directly with KeepAlive
   ```

2. **Missing `origin` column**: `infrastructure/ai/setup_recall.py::_upsert_sync` UPSERTs into kb.clusterai_setups without the `origin` column:
   ```python
   # BUG:
   INSERT INTO clusterai_setups (symbol, regime, setup_type, ...) VALUES (...)
   # CONSTRAINT: origin NOT NULL + CHECK (origin IN ('live', 'suite'))
   # Result: silent constraint failure, no insert, no error log
   # FIX: include origin='live' in INSERT
   ```

**Diagnosis:**
```bash
# Check if embed timeout is the blocker:
tail -100 /logs/ct101.log | grep -i 'embedding.*timeout\|embed.*error\|connect timed out'

# Check if setup_recall is silently failing:
psql -h 10.1.1.102 -U kb kb -c "SELECT origin, COUNT(*) FROM clusterai_setups GROUP BY origin;"
# If live origin is empty or missing, constraint is failing.

# Verify constraint exists:
psql -h 10.1.1.102 -U kb kb -c "\d clusterai_setups" | grep -i origin
```

**Fix both:**
- Patch `setup_recall._upsert_sync()` to include `origin='live'` in INSERT
- Call `/api/embed` directly (not via EmbeddingService) with 300s timeout or use hosted Cloudflare Workers AI

## Ollama GPU contention (why current embeds are slow)

**Measured baseline:**
- September 2026: 31 embeds/s (GPU active)
- November 2026: 0.04–0.06 embeds/s (GPU starved or CPU fallback)

**Diagnosis:**
```bash
curl http://10.1.1.100:11434/api/ps  # or whatever Ollama host is configured
# Check size_vram for each loaded model
# size_vram: 0.0 GiB = model is on CPU, not GPU
# Multiple large models loaded? Check OLLAMA_MAX_LOADED_MODELS setting
```

**Fix (if GPU is the issue):**
1. Unload large chat models: `ollama pull gemma4:12b` then `ollama rm gemma4:12b`
2. Set `OLLAMA_MAX_LOADED_MODELS=1` (keep only the embed model loaded)
3. Pin the embed model: `curl http://ollama:11434/api/generate -d '{"model":"nomic-embed-text","keep_alive":"30m"}'`
4. Re-benchmark: measure 10–20 consecutive embeds and report the rate

If GPU is healthy but still slow, check for peer processes:
```bash
ps aux | grep -E 'ollama|cuda' | grep -v grep
systemctl show ollama.service -p MainPID
ps -o pid,ppid,cmd | grep $(systemctl show ollama.service -p MainPID --value)
```

If an orphaned `ollama serve` (PPID 1) runs alongside systemd MainPID, it's not the cause — both share the same GPU.

## Hosted embedding escape hatch

If local Ollama cannot be unblocked (GPU contention, hardware failure), use Cloudflare Workers AI:

**Verify before planning:**
```bash
# Check if token has Workers AI Run permission (error 9106 = missing permission)
curl -X POST https://api.cloudflare.com/client/v4/accounts/6f97fb.../ai/run/@cf/baai/bge-large-en-v1.5 \
  -H 'Authorization: Bearer <CF_D1_API_TOKEN>' \
  -d '{"text": "test"}'
# If 9106, re-authorize MCP target or get a token with Workers AI Run scope

# Check output dimension (must be 1024 to match kb.embeddings schema):
curl ... 2>&1 | grep -o '"shape":\[.*\]'  # Should be [1024]
```

**Then benchmark 100 consecutive embeds before committing to the job.**

## Timeline estimate

- Local Ollama working + GPU unblocked: ~4–6 weeks (1.13M windows ÷ 5 embeds/s ÷ 86,400 s/day)
- Hosting on Cloudflare Workers AI: depends on measured rate (measure first, never estimate)
- Fixing both constraint bugs + rerunning successful 2026-09-06 backfill: 2–3 days

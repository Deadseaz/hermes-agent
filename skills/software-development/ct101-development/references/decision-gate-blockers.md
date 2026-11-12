# Decision Gate Blockers: Verification-First Diagnosis

## Core Insight

A fully-wired CT101 system with all services answering `/health` 200 and all flags ON can execute **zero trades** if one upstream decision blocker closes the gate. This is NOT a system wiring problem; it is a gate configuration problem that looks invisible (no errors, just no decisions).

**Key pattern:** all services up + all probes green + `bot:decisions` **empty** = decision-gate-blocked system. Do NOT debug SNN, memory, booster until this is verified. The first gate that fails silences all downstream consumers.

## Four Known Blockers

### 1. Negative Capital (most common on leverage accounts)

**Verification:** Check logs:
```bash
tail -300 /logs/ct101.log | grep -E 'portfolio.*<=.*0|no_capital'
```

**If found:** account reads `cash` instead of `equity`. Leverage accounts have negative cash (borrowed amount) + positive equity (collateral + unrealized PL). When cash < 0, capital check fails and EnhancedRiskEngine rejects all trades.

**Example:** aggressive-tier cash = −$212,926, equity = +$96,521 → orchestrator sees portfolio_value ≤ 0 → zero decisions.

**Fix location:** `infrastructure/agents/basbot_enhanced_orchestrator_production.py` lines 500–520 (or wherever capital is evaluated).

**Code fix:**
```python
capital = account.get('equity') or account.get('portfolio_value') or account.get('cash', 0)
if capital <= 0:
    return  # capital blocker fires
```

**Verify after fix:**
```bash
redis-cli -h 10.1.1.102 LLEN bot:decisions  # should start growing
```

### 2. Hours Gate Double-Fail

**Verification:** Check logs:
```bash
tail -300 /logs/ct101.log | grep -E 'TradingHoursRule|trading.*hours.*fail|Hours.*block'
```

**If found:** Two independent gate paths both check hours, neither honors `MARKET_HOURS=24/7`:
- **Legacy path** (`engine_coordinator.py`): reads `TRADING_HOURS_ONLY` (defaults true), compares local `datetime.now()` (no TZ) to hardcoded 9.5–16.0 (treated as local PT).
- **Live path** (`RuleRegistry.load_rules()` from `config/regulatory/rules.json`): loads `TradingHoursRule`, hardcodes 09:30–16:00 **ET**.

Result: a code patch to the legacy gate is insufficient; JSON-loaded rule still blocks. Both gates must be fixed together.

**Fix locations:** 
- `infrastructure/engine_coordinator.py` line ~270 (legacy check)
- `infrastructure/runtime/rulework.py::RuleRegistry.load_rules()` (JSON path)

**Code fix (both paths):**
```python
# Check source of truth ONCE
if not market_hours_enforced():  # returns False if MARKET_HOURS=24/7
    return True  # hours open
# else: consult market hours rules
```

**Verify after fix:**
```bash
grep MARKET_HOURS .env  # should be 24/7
tail -50 /logs/ct101.log | grep -i 'TradingHoursRule\|hours' | wc -l  # should drop to 0
```

### 3. Resubscribe Crash (exits bot permanently)

**Verification:** Check logs:
```bash
tail -100 /logs/cluster_ai.log | grep -E 'resubscribe.*fail|exiting bot loop'
```

**If found:** bot runs once, exits, then sleeps 15 min until next dispatch cycle. A transient Redis outage or network hiccup kills the bot permanently in that cycle.

**Example:** 26-minute trading gap on 2026-11-06 due to one Redis resubscribe failure.

**Fix location:** `domain/bots/services/cpp_memory_aware_bot.py::run()` loop (or bot-specific loop).

**Code fix:**
```python
max_retries = 5
for attempt in range(max_retries):
    try:
        await self._resubscribe()
        break  # success
    except Exception as e:
        if attempt < max_retries - 1:
            backoff = 2 ** attempt  # 1, 2, 4, 8 s
            logger.warning(f'resubscribe retry {attempt + 1}/{max_retries} in {backoff}s')
            await asyncio.sleep(backoff)
        else:
            logger.error(f'resubscribe failed {max_retries} times — exiting')
            return
```

**Verify after fix:**
```bash
# Cause a brief Redis restart and confirm bot continues
redis-cli -h 10.1.1.102 SHUTDOWN
# Bot logs should show retry attempts, NOT exit
```

### 4. Empty Symbol Universe (MCPAlpacaBroker missing method)

**Verification:** Check logs:
```bash
tail -50 /logs/ct101.log | grep ConfidenceBooster | head -3
```

**If all show:** `Trade compliant: ... 0.50 in 0 μs` (identical timing, identical score) → hardcoded liveness probe only; no real decisions flowing.

**Root cause:** `broker.get_tradable_symbols()` missing on MCPAlpacaBroker (only exists on AlpacaBrokerService). Exception swallowed; `symbols = []` silently.

**Note:** Bot is symbol-agnostic so this does NOT block decision dispatch — only universe resolution. Lowest priority fix.

**Fix location:** `infrastructure/exchange/mcp_alpaca_broker.py`

**Code fix:**
```python
async def get_tradable_symbols(self):
    # Call alpaca hub tool for asset list
    assets = await self.call_tool('alpaca-v2-get-assets', status='active')
    return [a['symbol'] for a in assets if a.get('tradable')]
```

---

## Diagnostic Sequence (Run in Order)

**When `bot:decisions` is empty but services are up:**

1. **Verify running worktree:**
   ```bash
   readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd
   ```

2. **Check decision count:**
   ```bash
   redis-cli -h 10.1.1.102 LLEN bot:decisions
   ```
   If empty: continue to step 3. If flowing: debug downstream (step 5).

3. **Identify which blocker fires (check in order):**
   ```bash
   # Capital
   tail -300 logs/ct101.log | grep -E 'portfolio.*<=.*0|no_capital' && echo "CAPITAL BLOCKER"
   # Hours
   tail -300 logs/ct101.log | grep -E 'TradingHoursRule|trading.*hours.*fail' && echo "HOURS BLOCKER"
   # Resubscribe
   tail -100 logs/cluster_ai.log | grep 'resubscribe.*fail' && echo "RESUBSCRIBE BLOCKER"
   # Probe only (universe implicit)
   tail -50 logs/ct101.log | grep ConfidenceBooster | head -1
   ```

4. **Fix the earliest blocker (from step 3) first.**  Fixes to later stages have no effect while the earlier gate is closed. Apply the code fix, restart, re-check step 2.

5. **If decisions do flow (step 2 ≠ empty), verify downstream:**
   ```bash
   redis-cli -h 10.1.1.102 GET snn:scores | jq '.trials'  # should be >0
   tail -20 logs/memory-fill-sub.log | tail -1  # timestamp should be recent (<10 min old)
   tail -50 logs/ct101.log | grep -i 'SNN\|memory.*pattern' | wc -l  # should be >0
   ```

---

## Why Upstream Problems Hide Downstream Issues

When the decision gate is closed, everything downstream is constructed but starved of input. Memory fills queue nothing (no decisions to fill), SNN learns nothing (no fills to reward), booster scores nothing (no decisions to boost). Later turns blame the SNN or memory for "not wired"; the real blocker is the decision gate. Always verify gate first.

# Runtime verification — proving what the live system actually does

Cheap probes that separate "the process is up" from "the feature works". Run these before describing system state.

## Capability health scorecard

Health is one key per capability: `ct101:health:<capability>`. The value is a **string containing JSON**, not a hash — `HGETALL` raises `WRONGTYPE Operation against a key holding the wrong kind of value`. Use `GET` + `json.loads`:

```python
import json, redis
from infrastructure.runtime.launcher_env import build_redis_url
r = redis.from_url(build_redis_url(), decode_responses=True)
for k in sorted(r.scan_iter("ct101:health:*")):
    v = r.get(k)
    d = json.loads(v) if v else {}
    print(k.split(":")[-1], d.get("status"),
          {p: c.get("ok") for p, c in (d.get("checks") or {}).items()})
```

30 capabilities is the full set. `degraded` is a real finding, not noise: read the failing check's `detail` (e.g. `llm_minimax: HTTP 400`, `position_reconciliation pipeline_present=False`).

## Adaptive layer — is it actually adapting?

A probe that returns the same value for every input is a bug, not an aggressive configuration. Size the compound engine across a confidence × volatility matrix:

```python
from domain.compounding.services.compound_engine import CompoundEngine
e = CompoundEngine(settings={"initial_capital": 100_000.0, "style": "balanced"})
for conf in (0.2, 0.5, 0.7, 0.95):
    for vol in (0.02, 0.15, 0.5):
        print(conf, vol, e.calculate_position_size(100_000, conf, vol, "momentum"))
```

Constant output means the clamp/return is discarding the maths (the body once ended `bounded_size = max_size` after computing four factors). Correct behaviour is monotone in confidence and inverse in volatility, inside `capital*min_position_size … capital*max_position_size`.

Two more wires to check by probe, not by comment:

- `ct101:health:confidence-memory-recall` → `confidence_booster.detail` must say `recall_source=wired`. A `# set by <manifest>` comment does not mean the manifest sets it; `none` means confidence is scored on the in-process dict and the knowledge base is never consulted.
- `BOUND_RISK_ENFORCEMENT_MODE` in `.env`: `warn` logs would-be rejections but lets orders through, `block` denies, `off` skips. Read it before claiming risk limits gate trading. The drawdown peak resets after `risk_peak_window_s`, so a 1 % limit is not a permanent deadlock.

## Infrastructure inventory (Proxmox)

Ground "what exists on the LAN" in the API, not memory:

```python
from infrastructure.discovery import service_discovery as sd
for g in sorted(sd._enumerate_proxmox(), key=lambda x: x["ip"]):
    print(g["vmid"], g["name"], g["ip"], g["vm_type"], g["status"])
```

Returns every LXC/QEMU guest across both nodes (`pve`, `pve2`) with name, IP and status. `sd.get_proxmox_clients()` lists the clients. Use this before saying a service is unavailable or needs to be built.

## Backtest proof (UI path)

`POST /api/backtest/suite/start` on dashboard-api (`:8002`) with a JWT spawns a detached worker; poll `/api/backtest/suite/status/<run_id>` then `/api/backtest/suite/results/<run_id>`. **The suite requires ≥2 symbols** — a one-symbol spec fails with `Only 1 symbols loaded successfully (need ≥2)`. Cheap proof: 2 symbols, one calendar year, `bar_limit` 300:

```json
{"symbols": ["AAPL", "MSFT"], "universe_mode": "explicit",
 "start_date": "2024-01-01", "end_date": "2024-12-31",
 "bar_limit": 300, "initial_capital": 100000,
 "strategy_preset": "balanced", "bot_strategies": ["momentum"]}
```

A successful run reports `symbols_loaded`, `fetch_failures`, `summary.total_trades`, `total_return`, `sharpe_ratio`. The frontend Backtest tab (`/trading?tab=backtest`, `BacktestTab.tsx`) uses the synchronous `POST /api/backtesting/execute` instead; both pull real CT115 bars.

## Historic coverage — filenames lie

Never trust a file called `*_50year`. Query the actual range:

```python
import sqlite3
c = sqlite3.connect("data/historical_50year/global_markets_50year.db")
print(c.execute("select count(*), count(distinct symbol), min(date), max(date) from market_data").fetchone())
```

Measured: that file holds 2007-01 → 2025-01; the three DBs under `data/historical_50year/` cover 2004-09 → 2025-01 (~21 years, 25.4M bars, 9,671 symbols). `data/historical_data.db` has an empty `bars` table and `kb.market_data` has 0 rows — the bars live in the SQLite files, not the DB. Report the measured span, not the filename.

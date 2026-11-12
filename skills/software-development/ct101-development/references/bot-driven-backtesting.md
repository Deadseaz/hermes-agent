# Bot-driven historic backtesting

Use this when the task is "run the system on historic data" and the system must be the
bots, not a strategy handler. A `FullDomainStrategy` run is a strategy test; it is not
a bot test.

## What is missing, and what to use instead

- `tests/full_system_backtest.py` imports `BotFactory` and never creates a bot.
- `tests/comprehensive_3/backtest_ct115.py` imports `BotManager` and calls
  `generate_signal` (RSI).
- The 365-day `ComprehensiveWorldMarketsEngine` survives only in `_archive/` as a
  `singapore_unified` stub; its original module is in no tree or backup.
- `BotOrchestrator` is a live thread dispatcher, not a historical runner.

So drive the real bot classes directly: `scripts/run_bot_real.py` (realistic
mechanics) or `scripts/run_bot_year.py --ungated --no-stops --unlimited` (research
mode). One bot instance per symbol:

```python
bots[sym] = MomentumTurboBot({"symbol": sym, "capital": book,
                              "broker": _BarBroker()})  # get_latest_quote -> {}
```

A backtest broker handle that returns no quote keeps `_calculate_entry_price` on the
bar price. Without it, the bot calls the live Alpaca quote API and dies on a 429.

## Realistic execution model

1. Compute the signal from bar D's close (bot snapshot fed `{price, volume}`).
2. Queue the order; fill it at bar D+1's **open**, never at D's close.
3. Apply adverse slippage (5 bps) and commission ($0.005/share, $1 minimum).
4. Enforce FINRA 4210: $2,000 minimum equity, Reg T 50% initial (2× equity),
   25% maintenance on long MV, 30% on short MV, 50% short margin.
5. If equity < maintenance, liquidate at the close (margin call). Never allow
   negative equity.
6. PDT: eliminated by SR-FINRA-2025-017 (SEC approval 2026-04-14, effective
   2026-06-04). No day-trade count limit, no $25,000 minimum. Do not reintroduce
   either as a "safety" dial.

Daily bars cannot model the new **intraday** margin-excess rule. State that limit;
do not pretend a daily run replicates intraday margin.

## Ungated research mode

`--ungated` calls the bot's own `_analyze_market` / `_calculate_metrics` /
`_get_trading_parameters` and bypasses only `_validate_opportunity`. It is still the
bot's analysis, turbo parameters and stop/targets: only the confidence/momentum/risk
gate is removed. Keep `EnhancedRiskEngine` for sizing, feed every entry/exit to
`ConfidenceBooster`, and apply the trained SNN as a bounded size confirmation. Do not
replace any of those with a hand-rolled signal.

## Bot defects found on the trade path

| Symptom | Cause | Fix |
|---|---|---|
| `decide()` always `hold` | `MemoryAwareBot` used `_need` without importing it; broad except returned `hold` | import `get_bounds` and define `_need`, or use the shared helper |
| `KeyError: 'name'` in `analyze_opportunity` | `AutonomousBot.strategies` empty; `initialize_autonomous_learning()` has no caller | populate strategies before analysis; `.get(strategy, [])` in `_calculate_strategy_score` |
| zero trades, `Validation failed` on every bar | `MomentumTurboBot._validate_opportunity` momentum threshold 0.6; observed max 0.618, mean 0.149 | ungated mode for research; do not lower the dial silently |
| `CppMemoryAwareBot.decide()` returns `None` | constructed with `bot_instance=None`, the function fell through without returning | return `self._fallback_rule(state)` when there is no inner bot |
| decision aborts on HTTP 429 | `bot_support.latest_price` calls the live quote API without a guard | catch and fall back to the bar price |
| booster logs `pnl=-206.20%` for a -2% loss | `BacktestingEngine` passed `pnl_percent*100` into `ConfidenceBooster`, which stores a fraction and formats with `:.2%`; the strategy then fed the same exit a second time | one feed per exit, fraction units — the engine owns the entry/exit record |
| `MemoryGraph` stalls at 200 symbols | `find_similar_patterns` scans every node | keep an exact-key index (side, regime, RSI decile, vol bucket) |
| every live buy rejected, `Drawdown (50.0%)` | `RiskShield` high-water mark starts at the configured $100k, account holds $50k | seed from the first observed equity |

## C++ decision path — the libpq/OpenSSL crash and its fix

`BasBotEnhancedOrchestratorProduction` wraps every bot in `CppMemoryAwareBot`.
That wrapper's `initialize()` calls `core_initialize()`, which connects Redis and
Postgres. It crashed with SIGSEGV (exit 139) for two independent reasons:

1. **`.env` not loaded yet.** `core_initialize()` reads `POSTGRES_*` / `REDIS_*`
   from the process environment; without them it defaults to 127.0.0.1. The
   binding now calls `load_project_env()` before `core_initialize()`.
2. **OpenSSL ABI conflict.** gdb showed `PQconnectdb -> OPENSSL_sk_num` inside
   libcrypto: TensorFlow/LLM libraries had loaded a different libcrypto than
   libpq. Preload the system libraries RTLD_GLOBAL before the core `.so`:

```python
import ctypes
for lib in ("libcrypto.so.3", "libssl.so.3"):
    ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
```

or launch with
`LD_PRELOAD=/lib/x86_64-linux-gnu/libcrypto.so.3:/lib/x86_64-linux-gnu/libssl.so.3`.

With both fixes `core.initialize()` returns True and the wrapper's
`initialize()` succeeds. A separate wrapper bug: with `bot_instance=None`,
`decide()` fell through and returned `None`; it now returns
`self._fallback_rule(state)`. Then the C++ path is live — `core_calc_indicators`,
`pattern_hash`, `get_confidence_boost`, `update_pattern_confidence` all execute.

The boost is still neutral (0.5/1.0) until the decimal-uint64 vs hex hash format
is normalised, so the C++ memory is wired but not yet changing size much. The
wrapper's fallback rule is RSI<45/50 modulated by the boost — do not describe
that as a non-RSI strategy.

Do not present a `MomentumTurboBot`/RSI run as the fleet. The orchestrator's
`bot_strategies` maps `autonomous`, `adaptive`, `memory_aware`,
`momentum_enhanced`, `momentum_turbo`, `montecarlo`, `dqn`, `doubler`; until the
C++ wrapper boots, none of them can be driven together. `AutonomousBot` also
ships with an empty `strategies` dict (`initialize_autonomous_learning()` has no
caller), so its selector runs `max()` on an empty dict, returns `{}` and then
raises `KeyError: 'name'`.

## Measured baselines (2024 daily bars, $100k)

- 200 symbols, realistic mechanics, `CppMemoryAwareBot --cpp-bot --snn`: **+49.31%**,
  Sharpe 1.53, max DD 16.97%, 344 closed trades, win 57.27%, PF 2.19, 50,334 C++
  pattern hashes, 344 pattern-confidence updates, mean boost 0.5022, 1,319 fills,
  12,542 margin rejections, 0 margin calls. This is the C++ pattern bot, but its
  entry rule is still RSI<45/50 with the boost; not the autonomous fleet.
- 200 symbols, realistic mechanics, `MomentumTurboBot --snn`: +5.14%, Sharpe 0.32,
  max DD 26.82%, 999 closed trades, 4,310 fills, 27,224 margin rejections,
  0 margin calls.
- 200 symbols, ungated with same-bar fills and no margin (`--unlimited` before the
  realistic harness): +44% but reaching negative equity — not a valid result.
- 200 symbols, `FullDomainStrategy` + SNN + MemoryGraph: about −4.4% to +4.8%
  depending on the gate set; a strategy run, not a bot run.

Use these only as calibration. Re-run before quoting a number.

---
name: ct101-development
description: "Use when working on CT101 boot, discovery and trade path. Domain, infrastructure, C++ bridge."
version: 1.0.0
author: Nate (Deadseaz), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ct101, trading, domain, infrastructure, cpp, bots, discovery, backtest, alpaca]
    category: software-development
    related_skills: [ct101-live-system]
---

# CT101 Development

## When to Use

Any edit to the CT101 codebase — adding connectors, modifying discovery/binding, changing tier tests, touching domain modules, or diagnosing service state.

## Nate's rules — apply to every edit

- **No stubs, no fake code, no mocks that return made-up data.** Every function must exercise real systems.
- **Verify with real tool output before claiming success.** A connector must connect and return live data; a test must pass against the running system.
- **Modify existing code; only write new files for genuinely new capability.**
- **Facts before claims.** Run the diagnostic before describing the problem.
- **Answer the direct question first with concrete facts, not analysis.** When Nate asks "is X loaded?" or "what data is there?", respond with actual numbers/results from queries/logs: "1.24M rows in table, 9,425 symbols, 1962–2025" — not "the system appears to have data". When he asks where you are, answer first sentence with the concrete path/hash/number, then continue. Long silent tool runs and speculation read as evasion. When he challenges a result or repeats an instruction, state once what it did and did not prove (one short paragraph), then execute. Re-explaining the same distinction across replies feels like refusal. **Never assume code paths, functions, methods, or data locations without verification.** Every assumption must be backed by a grep, query, or ls — "CppMemoryAwareBot calls decide()" is a guess until you have run `grep -n 'def decide\|async def decide' <file>` and confirmed the method exists or doesn't. Similarly, "historic data is in R2" must be verified with `curl` on the bucket and a query on the KB tables, not assumed from design docs. When you are wrong about an assumption, the user's correction stops further analysis — they will not tolerate a second round of theory. Verify first; describe afterward.
- **When you find a structural problem, state the repair clearly — do not just describe it.** A discovered worktree split, branch drift, or stale canonical tree is a defect. But also: before you assume "the code is broken because it's not wired," verify the actual execution path. Trace: does the function call the next one? Are parameters passed? Do the returned values have the expected shape? Read the exact lines, not the outline. A system can appear "not wired" when all code is real but one interface changed (the wrapper expects `decide()` but the wrapped bot only has `act()`). Find the exact mismatch before proposing a fix. If the user asks to "review the full code and find what's not wired," answer with specific mismatches: line numbers, actual vs expected, concrete evidence. Not "the code looks unfinished."
- **When asked for a diff or an analysis across worktrees/branches, deliver it in full — never partial.** Run the audit for every worktree (committed and uncommitted state), write the complete patches to a scratch dir, and report per-worktree file-level stats plus the verdict. A few sampled files is not an answer to "full diff for each one".
- **Brief, direct answers.** Code over commentary. Action over analysis. Never describe a partial launcher as "the system" — state its coverage numbers.
- **Do not add gates or dials, and do not cap gains.** Paper trading stays open. Only the real-money `alpaca-live` connection is gated by `ALPACA_LIVE_TRADING_ENABLED`, and that gate predates any edit you make. A new `if not FLAG: return` on the trade path is a regression, not a safety feature — fix a feature by wiring it, not by gating it. No profit cap, no arbitrary max-position/profit dial: the only legitimate limits are real margin, buying power, settlement and the $2,000 margin-account minimum. PDT is eliminated (no day-trade count, no $25,000 minimum).
- **No budget/time excuses.** Never mention token budgets, context limits or being restrained, and never stop mid-task because of a perceived limit. If something is hard, name the concrete blocker and keep working. He experiences that as refusing to wire the system. The system is REAL and WIRED (44,797 Python files, 27GB, backtests prove it works). The question is never "is this fake" but "why does backtest work but live trading doesn't?" — don't repeat the "is it real" diagnosis.
- **When the user says "you're refusing to be an expert," they mean: trace execution to the actual failure point, don't speculate from design docs or partial code reads.** Read the FULL implementation chain end-to-end. Cite line numbers for every function call and verify parameters match. When you find a mismatch (wrapper expects `decide()`, bot has `act()`), state it with exact line numbers — not "the architecture looks wired." When you don't know, read the code FIRST before analyzing.
- **When nothing logs from an async thread, it crashed silently before any instrumentation.** Bots created and dispatch_tick running but bot:decisions empty and 0 decisions settled = threads died on startup. Check `_start_bot_execution` for unguarded exceptions in `run_bot()` and the `asyncio.run(bot_instance.run())` call.
- **CT115 minute bars require a one-line change:** `timeframe=1D` → `timeframe=1min` in the feed URL. Do not speculate about what CT115 serves — grep the endpoint call and change it.
- **Interface mismatches are real wire failures.** When a wrapper calls `await self.decide(state)` and the wrapped bot only has `act(observation)`, that's NOT "the code is structured well" — it's a specific unwiring. Add the `decide()` adapter to the wrapped class (convert state format to observation format, call `act()`). One class per fix; do not multiply bots with the same missing method.
- **Never announce a service is unreachable before resolving it through discovery.** Host, port and credentials come from the registry/`.env`, and Proxmox (`proxmoxer`) can start a stopped container. "I can't connect" is a finding after those checks, not a status update — Nate reads it as refusing to wire the system. When you cannot reach a system, do not waste time on analysis — go to the deployed tree (which IS running), check what it actually uses, and diagnose against that. The deployed tree is ground truth for what works.
- **The test you are looking for might not be on the filesystem.** Test results live in multiple places: `backtest_results/` filesystem, PostgreSQL database, deployed worktree logs, and OpenViking memory (when connected). Do not assume the "right test" is in the current checkout — check deployed worktree logs (`/root/.sesori/worktrees/ct101-*/silver-dormouse/logs/`), query the database for `strategy_outcomes` and trade history, and ask the user for the specific path/branch if you are looking in the wrong place. When the user says "the Thursday backtest showed 60% gain," do not assume you know which test they mean — ask for location or check connected memory systems (OpenViking).
- **When "nothing is accessible", sweep declared-vs-listening-vs-responding before believing it.** Resolve every `port_key="..."` declared in `infrastructure/runtime/capabilities/*.py` against `.env`, diff against `ss -ltn`, then curl `/health` (not `/`) on each — an API server 404s on `/` by design, and 302-to-`/agents/` on the node server is normal. A stale unused `.env` URL that no manifest binds and no code consumes (observed `DASHBOARD_URL=http://10.1.1.98:8082`) is the classic single dead thing behind a "whole codebase is fake" impression — every declared service was in fact listening. Counts reconcile as: 31 capability names but only 21 declare `port_key=`; the other 10 are in-process domain logic, so "more than 30 services but only 30 reachable" is the design, not a failure.
- **Describe scope by measured inventory.** Cite the full count, not the smallest piece you touched: the C++ base is 1,514 exported symbols across four libraries, not the 10-function ultrafast shim; the API surface is 605 decorators / 488 paths, not the handful a probe listed. Understating the system reads as minimising it.

## Branch vs deployed tree — check this first

**Symptoms of worktree drift:** your session edits have no effect on a live system that seems to be running; changes build cleanly but the running output is unchanged; logs continue old patterns despite code patches. The issue is that the deployed unit runs code from a different directory than your checkout.

**Resolve the running tree from the processes, not from the unit file or your shell cwd.** The live app can run from a git worktree on a different branch than the checkout you are editing:

```bash
readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd
pwd  # your current checkout
```

If these differ, the running system is a different tree. Observed live: MainPID=/root/.sesori/worktrees/<id>/silver-dormouse while your checkout=/home/claude/timeshift/ct101 — edits to your branch never reach the running system; logs and `.env` resolve against the worktree's paths. **State which tree the running process uses before proceeding with any fix — they have different histories, uncommitted state, and `.env` sources.** Never assume one tree is "more up to date"; check `git merge-base` to find the actual relationship.

`/home/claude/timeshift/ct101` is what systemd runs (`ct101.service`). The branch is often far behind it: uncommitted tracked modifications plus untracked modules that main.py imports. Before trusting any branch:

```bash
cd /home/claude/timeshift/ct101 && git status --short | wc -l && git diff --shortstat
```

If the count is non-zero, the branch cannot reproduce the running system. Sync the deployed working tree into the session worktree, then run the gate there. `infrastructure/runtime/tier_deploy.py` was once untracked-only — main.py died on ImportError before T0. Check for missing modules with `git status --short | grep '^??'` in the deployed tree.

**Which of several worktrees is canonical is a commit-topology question, not a docs question.** Full audit procedure (enumerate, merge-base across all heads, per-worktree committed+uncommitted patches, the stale-mirror test, verdict): `references/worktree-audit.md`. Two shortcuts: the merge-base of the live branch and every other worktree head tells you who is an ancestor (a head that equals the merge-base has nothing unique); and "is this dirty file really new work" is answered by `git show <live-branch>:"$f" | diff -q - "$f"` — 244/275 dirty files matched the live branch's committed content, i.e. the head checkout was a half-applied copy, and committing it would have reverted live fixes. `.claude/worktrees/*` are dead agent leftovers on ancestor commits; check their unique commits before deleting.

## Running the live system from a worktree

A worktree holds code only: no `venv/`, `.env`, `models/`, `data/` or logs. To make it the live root, link the runtime, give the service user access, and point the unit at it (full recipe, verification and rollback: `references/worktree-live-runtime.md`):

```bash
W=/root/.sesori/worktrees/<id>/<name>
ln -s /home/claude/timeshift/ct101/venv   $W/venv
ln -s /home/claude/timeshift/ct101/models $W/models
mv $W/data $W/data.worktree-only && ln -s /home/claude/timeshift/ct101/data $W/data
chown -R claude:claude $W && chmod o+x /root   # unit runs User=claude; /root is 0700
cp /etc/systemd/system/ct101.service /etc/systemd/system/ct101.service.bak-$(date +%Y%m%d-%H%M%S)
# set WorkingDirectory= and ExecStart= to $W, then:
systemctl daemon-reload && systemctl restart ct101
```

Verify the **process**, not the unit file: `/proc/$(systemctl show -p MainPID --value ct101)/cwd` and that PID's cmdline must both name the worktree. App state and logs still resolve through `.env`'s `PROJECT_ROOT`, so worktree code writes to the deployed tree's `data/` and `logs/` — one state, two checkouts. Boot takes 7–8 minutes.

## Alpaca is the MCP hub, not .env keys

The hub on CT112 owns three Alpaca connections, exposed as tool sets:

| prefix | account id | equity |
|---|---|---|
| `alpaca-v2` | fa38aa35-ba42-4a8c-acfa-cf666c12d6c0 | 50,000 (paper) |
| `alpaca-v3` | 182eba10-fe9d-4f54-8cfc-bae036905574 | 100,000 (paper) |
| `alpaca-live` | 5dd66ac8-d7c2-4099-969c-5be8fea4c8f9 | 45.79 (real, gated) |

**`alpaca-v2` may not exist in the hub database.** The hub's `/api/servers` lists it at runtime but the postgres `servers` table may only have `alpaca-v3` and `alpaca-live`. If v2 tools return "Not connected", check the database: `SELECT name FROM servers WHERE name LIKE '%alpaca%'`. Switch the default account with `BOTMGR_ACCOUNT=alpaca-v3` in `.env` or change `DEFAULT_ACCOUNT` in `infrastructure/exchange/broker_factory.py`.

`ALPACA_TRADEV4/41/42_*` in `.env` are byte-identical copies of the v2 account — do not treat them as three accounts. The trade path is `infrastructure/exchange/mcp_alpaca_broker.py:MCPAlpacaBroker` (built by `broker_factory.build_trade_broker`); it maps account/positions/orders/bars/quotes/clock onto `alpaca-<account>-<tool>`. `MCPHubHandle.call_tool_data()` unwraps the MCP content envelope and the hub's compression notice. Market-data WebSocket stays on alpaca-py (hub is request/response). The live connection raises `PermissionError` unless `ALPACA_LIVE_TRADING_ENABLED` is true.

## Trace execution to the actual failure point — don't analyze at distance

**When code appears to be wired but nothing executes, trace the exact function calls and return values — do NOT speculate from code structure or design docs.** Nate's core frustration is analysis-without-verification:

- Verify exact method signatures exist before assuming a wrapper can call them (e.g., MomentumBot had no `decide()` method, only `act()` — signature mismatch, not broken code).
- Trace the call chain line-by-line: CppMemoryAwareBot.run() calls `await self.decide(state)` on line 501 — does the wrapped bot have that method? Check the worktree that IS running, not the development branch.
- When decisions don't publish (`bot:decisions` empty, settlement cycle shows 0 decisions settled), check if bot threads are even executing: look for "Starting bot execution" logs. If no logs, the thread crashed silently before any instrumentation — read `_start_bot_execution` carefully for unguarded exceptions.
- State plainly which tree is running and what its actual modifications are (uncommitted files, divergent branch) before diagnosing behavior.
- **Do not re-analyze "is the code fake?" when backtests prove it works.** Backtests showing 60% gain over a year with 2,035 fills on real mechanics mean the code is REAL. The question is "why does live trading fail" not "is the system functional." Refuse that re-analysis — cite the proof and move to the blocker.

## Ground-truth diagnostics

**Start by understanding the actual deployed system, not the development branch.** Before claiming anything is broken or unwired, identify:

1. **Which tree is running?** `readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd` — use that path to read logs, configs, and understand what is actually executing.
2. **What did it last do?** `tail -200 <deployed-path>/logs/ct101.log | grep -E 'dispatch|decision|trade|bot|error'` — this tells you the last actions and any blockers.
3. **Where are test results?** Backtests can be in `<deployed-path>/backtest_results/`, a database (`SELECT max(created_at) FROM strategy_outcomes`), or OpenViking memory. Ask the user for the exact location before assuming.
4. **Is the code in the branch what's actually running?** Compare: `git -C <dev-checkout> log --oneline -1` vs `git -C <deployed-path> log --oneline -1`, and check `git -C <deployed-path> status --short | wc -l` — uncommitted changes on the deployed tree mean the running system diverges from any branch commit.

5. **Where does each external service actually live?** Resolve host IPs from the deployed `.env` before probing — never guess a host from memory. `grep -E '_HOST=' .env` prints every service host; verify with `ping` + port probe before declaring a service unreachable. Observed: Redis host was 10.1.1.130, not 10.1.1.102 — probing the wrong host produced a false "Redis is down" diagnosis that wasted two turns.

**When the Proxmox host is unreachable (no SSH, no `pvesh` from inside an LXC), use `nmap -sn` to inventory live containers.** `nmap -sn 10.1.1.0/24 --host-timeout 5s` returns every live host on the subnet in seconds — compare against the expected IP list from `.env` to identify which containers are dead. This is faster than probing each host individually and works without Proxmox API access.

Before changing anything, run these to get facts:

```bash
# What services are live, what port→script mappings are verified
venv/bin/python -m infrastructure.discovery.surface --report

# Capability registry check (slow — walks entire repo, give 60s)
venv/bin/python main.py --dry-run
```

`main.py --dry-run` is NOT hung when it sits after printing deprecation warnings — `_listener_index()` in `surface.py` walks every directory and reads every `.py` file looking for listener markers. It's slow, not broken.

### Verification-first diagnostics: answer with facts before analysis

When asked "Is data loaded?", "Is X wired?", "Does the system have minute bars?", or "Is the codebase real or fake?", **DO NOT speculate or describe from memory — verify with actual queries/inspection first, then report facts.** Skill documentation and past session notes capture *intent* and *design*, not *live state*. Answering from notes instead of verification is the core mistake: it generates plausible-sounding descriptions that are sometimes wrong and always evasive.

**Systematic mistake to never repeat:** Citing design notes ("clusterai_bar_windows is one-off external backfill", "memory_patterns are stale", "outcomes table from incomplete runs") to frame an analysis when the user was directly asking you to CHECK. Then spending turns analyzing instead of querying. The user asked "why is nothing there?" and you answered "here's what design says"; the user repeatedly corrected you with "just check the data." The user asked "does it have minute bars?" — instead of grepping for `timeframe=1D` vs `timeframe=1min`, you described what CT115 supposedly does. **When you don't know, READ THE CODE FIRST. Read the full code — not one file, the full flow.** "I don't know" is honest; "the code says" when you haven't read it is the failure mode.

**The fix:** Answer direct questions with direct verification. When the user asks "is X there?", respond with query results (counts, dates, sample rows), not with narrative analysis. When the user says "review the full code and explain what's not wired", that means: read `domain/bots/services/*.py`, `infrastructure/runtime/capabilities/*.py`, `infrastructure/agents/*.py`, the bot dispatch chain end-to-end, and the actual flow (not structure). Answer with concrete wiring: "CppMemoryAwareBot.run() calls `await self.decide(state)` on line 501, but MomentumEnhancedBot has no `decide()` method, only `act(observation)` — interface mismatch." Not "the architecture looks wired." Look at the actual function calls, parameter names, what data flows where.

**Verification stack (depth-first, always run in this order):**

1. **Is the code real or a stub?** Check file size + line count, search for TODO/FIXME density, inspect the actual function signatures. `wc -l <file>`, grep function bodies, read a decision path end-to-end. Real code is thick; stubs are thin. Cite line count and TODO% before claiming wired or fake.

2. **Is the running process executing that code?** Check process PID and cwd: `readlink /proc/<pid>/cwd`, `cat /proc/<pid>/cmdline`. Verify logs are being written from that tree. Edited code has no effect on a process running a different branch. **State which tree is running before proceeding.**

3. **Do tables exist and contain data?** Stack queries:
   - `SELECT table_name FROM information_schema.tables WHERE table_name = 'X'`
   - `SELECT COUNT(*) FROM X`
   - `SELECT COUNT(*) FROM X WHERE critical_column IS NOT NULL` (e.g., `embedding IS NOT NULL`)
   - `SELECT MIN(created_at), MAX(created_at) FROM X` (date range)
   - Sample rows: `SELECT * FROM X LIMIT 1\gx` (see actual data shape)
   - Only THEN cite the results as proof. "1.24M rows" beats "it's loaded".

4. **Are the rows from real or corrupted runs?** When the user says "we've never had the system run fully integrated", **discard all rows labeled `origin='live'` or `status='broken'` as noise** — they are from incomplete test runs. Filter to: `WHERE origin IN ('historic', 'suite', 'backtest')` and `WHERE observations > 0`. Report the clean count, not the total.
   - Example: `clusterai_setups` has 686K 'live' rows (broken) + 237K 'suite' rows (clean). Report "237K suite rows, 686K broken," not just "922K total."

5. **Is the live channel flowing data?** Check Redis keys and log timestamps, not just table row counts. `OBJECT IDLETIME market:bars:SPY`, `tail logs/ct115-feed.log`, `PUBSUB NUMSUB market:bars`. Fresh keys + recent logs = flowing. Stale keys + old timestamps = stuck.

**Real query stack for "is historic data loaded?":**

```bash
psql ... -c "SELECT COUNT(*) FROM clusterai_bar_windows WHERE embedding IS NOT NULL;"
psql ... -c "SELECT COUNT(DISTINCT origin) FROM clusterai_bar_windows GROUP BY origin;"
psql ... -c "SELECT MIN(date), MAX(date) FROM clusterai_bar_windows;"
```

Anser: "1.24M rows with embeddings, all origin='historic', 1962–2025" is the proof. Never answer "it should be there" or "the backfill ran".

**Real query stack for "why aren't decisions publishing?":**

1. Check the worktree running: `readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd`
2. Check for decisions: `redis-cli LLEN bot:decisions` or `XLEN bot:decisions`
3. Check timestamps: `tail logs/cluster_ai.log | grep -i decision | tail -3`
4. Check the blocker:
   ```bash
   tail -300 logs/ct101.log | grep -E 'orchestrator.*capital|portfolio.*no_capital|Hours|trading.*hours|resubscribe.*fail'
   ```
5. State plainly which blocker fired (if any) and the exact log line. Do not speculate about multiple possible causes; cite the actual error.

**Never assume from memory.** When you describe a system state, verify it first. The user will challenge plausible-sounding descriptions that are wrong, and will not tolerate another round of analysis instead of checking. When he asks "why isn't X there?", he wants the query result, not your theory.

Live health scorecard, Proxmox inventory, the 2-symbol backtest proof and historic-coverage queries: `references/runtime-verification.md`.

### `--dry-run` exit 0 does not mean the launcher can boot

`dry_run()` only *warns* about a capability with no probe; `tier_deploy.check_config()` — the fatal T0 gate — fails it, and `main.py` exits 2 before starting anything. A clean dry-run can still be an unbootable system. Run T0 directly when in doubt:

```bash
venv/bin/python - <<'PY'
from infrastructure.runtime import capability, tier_deploy
from infrastructure.runtime.service_inventory import service_inventory
caps = capability.load_all()
t0 = tier_deploy.check_config(service_inventory(caps), caps, capability.LOAD_ERRORS)
print(t0.ok, [(c.name, c.ok, c.detail) for c in t0.checks])
PY
```

### What the launcher actually covers

`main.py` starts what the capability manifests declare plus what `surface.py` resolves as extras — it is not "every module in the repo". Get the coverage numbers before claiming the system is wired (full audit procedure: `references/launcher-coverage.md`):

```bash
python -m infrastructure.discovery.surface --report   # *_PORT keys / unique ports / unresolved
python main.py --dry-run                              # capabilities, services, components, loops
```

Three classes matter: declared-and-started; internal-with-a-serving-script-but-not-declared (discovery merges it, or it is dropped on a port/script collision); and unresolved (a `*_PORT` key with no serving script — a declaration with no implementation). Unresolved ports are the declared-but-unimplemented list: wire or delete each one. (Do not confuse these with static externals — those are real services and must never be called fake.)

## Service discovery / binding architecture

Services enter the registry two ways:

1. **LAN scan** — nmap sweeps the subnet, Proxmox API enumerates containers, HTTP fingerprinter identifies what's running. Real network probes.
2. **Static externals** — `infrastructure/discovery/external_services.py` creates registry entries from `.env` config for services that aren't LAN-discoverable (cloud APIs, services on non-standard ports). These go through the same `bind_external_services()` pipeline as LAN-discovered services. Never call them "synthetic" or "fake" — they are **static externals**, config-driven registrations for real services.

### Adding a new service connector

1. Create connector module in `infrastructure/discovery/connectors/<name>.py`:
   - `PRIORITY: int` — lower wins. Protocol-specific connectors (redis, postgres, amqp, mcp-hub) use 5-20; `http_generic` is 50; `tcp_fallback` is 1000.
   - `matches(service: dict) -> bool` — return True when this connector claims the service.
   - `async connect(host, port, creds, service) -> handle` — create a live connection. Raise `NeedsCredentials` or `ConnectError` on failure.
   - `VERIFIES = True` if the connector does a real protocol handshake (not just a TCP socket open).
   - Connectors are auto-discovered via `pkgutil.iter_modules` — no manual registration.

2. If the service is not LAN-discoverable, register it as a static external in `external_services.py`:
   - Add a `_build_<name>_external()` function that returns a `{slug: host_dict}`.
   - **Use the slug as the `ip` field** — not the real IP — to avoid BINDINGS key collision with LAN-discovered hosts on the same IP. The BINDINGS key is `host:port`. If a LAN scan already discovered 10.1.1.112:3000 and your static external also writes to 10.1.1.112:3000, the last write wins the race. Use `"ip": slug` so the binding key becomes `slug:port`.
   - Include `actual_host` and `actual_port` in the service dict so the connector knows where to dial.
   - Call the builder from `load_static_externals()`.

3. Add the service type to `REQUIRED_BINDING_TYPES` in `infrastructure/runtime/tier_deploy.py` if the trade path depends on it.

4. Verify: the connector loads, matches the service, and creates a real handle with live data.

## Tier testing

`tests/integration/test_wiring_layer1.py` — 45 tiers, the full-system deployment gate. Run with:

```bash
venv/bin/python tests/integration/test_wiring_layer1.py
```

Tier 1 is the bind gate — if it fails, no other tier can run. Tiers 1-14 cover discovery → bind → embedding → C++ bridge → persistence → domain heart → cross-layer → bots → Alpaca → MCP hub → memory → API alignment → startup order → UI. Tiers 15-31 cover every domain module: regime, risk, compounding, knowledge base, trading engines, regulatory, strategy, market, sentiment, neuromorphic, memory learning, events, routing, licensing, AI growth, agents, portfolio, handlers, models, monitoring. Tiers 32-45 cover infrastructure: feeds, security, backtest, exchange, persistence, database, gateway, websocket.

**Dependent tiers**: when a tier needs data from a prior tier (e.g. Tier 18 needs Tier 15's regime confidence/volatility), pass the prior tier object through `main()` — not through standalone construction. Tiers that call `get_handles_by_type()` or `get_bindings()` need Tier 1 to have run first; standalone execution will fail because handles aren't populated.

**Every tier must exercise real behavior, not just verify imports.** A tier that only does `from X import Y; check("importable", True)` is dead weight — the import already succeeds in earlier tiers. Each tier must call at least one real method with real data and verify the output. If a module genuinely has no callable service layer (pure value objects, enums, data classes), the tier is unnecessary — remove it.

**Read actual function signatures before writing.** Open the source file and read `def __init__` and method signatures before calling them. Guessing wrong parameter names, missing required args, or wrong types creates broken tiers that fail at runtime.

**Tier test values must flow from the system pipeline.** Capital from bound Alpaca account portfolio. Confidence and volatility from regime detector output. Strategy names from the bot registry. Thresholds from `.env` bounds. Hardcoded numbers are unit tests with fake data, not deployment verification.

`tests/test_service_discovery_scan_cache.py` — unit tests for cache semantics (read doesn't extend TTL, miss triggers one scan).

Run the full test before deploying. Never commit without green tiers.

### Gate semantics learned the hard way

- Compiled `.so` files are gitignored. A fresh worktree has the symlinks but not `libtradeengine_core.so`/`libultrafast.so`; four tier checks fail until you copy them from the deployed tree (or `make -C infrastructure/micro`). That is an artefact, not a code failure.
- Dependent tiers need Tier 1: running a tier standalone that calls `get_handles_by_type()` fails with `no handle`. Run `tier1_discovery()` first.
- Tier 14 probes the frontend surface. Express answers a POST-only path with **404**, not 405, so retry POST on 404. A GET can hit a path-parameter route (e.g. `/api/agents/{id}` with id=`dispatch`) and 5xx; retry POST before calling it broken. Paths containing `:param` cannot be probed literally — resolve them against the route-map.
- The 45-tier gate is the functional truth: 166 green / 2 red as of the hub-Alpaca wiring. The 2 red are Tier 14's dead/error frontend paths, listed by name.

## Verify KB state before claiming data is missing

Historic data claims require actual database queries, not assumptions about R2 buckets or file presence. When asked "is historic data loaded" or "why isn't memory wired", distinguish between:
   - **Raw files exist:** `.db` files on disk or in R2 bucket (necessary but not sufficient)
   - **Data is in KB:** rows in `clusterai_bar_windows`, `clusterai_setups`, `memory_patterns` with actual values
   - **Data is active:** recent observations in memory_patterns (not all rows are live patterns — many are defaults)

Queries and interpretation: `references/kb-verification-queries.md`.

## Never start the live system before backtesting

**The user's explicit rule: the ct101 service must NOT be running (paper or live) until it has been fully backtested and verified on out-of-sample historic data.** Starting the system prematurely to "see if it trades" wastes time debugging live infrastructure when the strategies haven't been proven. The workflow is:

1. **Stop ct101 first**: `systemctl stop ct101` — never debug the live system while it's running
2. **Run backtests on out-of-sample data**: 2005 DB, `--cpp-bot --snn`, 800 symbols, realistic mechanics
3. **Verify results**: does the system actually produce profitable decisions with real mechanics?
4. **Verify domain wiring**: all 27 packages import with >0 exports, C++ core active, knowledge base queried
5. Only THEN start ct101 for paper trading — and only after the user explicitly approves

**Gates that must pass before starting ct101:**
- Out-of-sample backtest shows positive return with profit factor > 1.5
- All 27 domain packages: `import domain.<pkg>` succeeds and `dir()` shows >2 exports
- C++ core: `core_initialize()` returns True and `get_confidence_boost()` returns non-1.0 after an update
- Knowledge base: `SELECT COUNT(*) FROM clusterai_bar_windows WHERE embedding IS NOT NULL` > 0

**Never restart ct101 "to see if a fix worked"** — verify the fix through dry imports, unit tests, or backtest scripts first. The boot takes 7-8 minutes and every restart cycle is wasted time when the fix could have been validated offline.

The dashboard API returning `trading_status: ACTIVE` with portfolio data from Alpaca is NOT proof the system works — it just means the API can read an account. Verify `bot:decisions` XLEN > 0 before claiming anything is trading.

## Is it actually trading?

A green boot and healthy probes do **not** mean orders flow. All services answering `/health` 200 and all flags set to ON does not mean decisions flow — when a system looks healthy but trades don't execute, **work backward from the decision gate first, not forward from the indicators**. The memory vault, SNN, confidence booster, and risk engine are all idle consumers if no `bot:decisions` are published.

**Key insight:** A fully-wired system can appear "not wired" if an upstream decision gate is closed. All services run, probes green, code is correct, but no decisions publish because the orchestrator rejects them at the capital check, hours gate, or resubscribe failure. Do not debug downstream consumers (SNN, memory, booster) until you have confirmed `bot:decisions` are flowing.

### Decision starvation audit (run this sequence in order)

When all services are up but nothing trades, isolate which blocker gates the decision. This is THE diagnostic to run first — a system can be 99% wired and still trade zero because one upstream gate is closed. Known patterns and fixes are documented in `references/decision-gate-blockers.md` — consult that for specific symptoms and code fixes.

1. **Is the worktree canonical?** Before any diagnosis, check what's actually running:
   ```bash
   readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd  # worktree path
   pwd                                                             # session checkout
   ```
   If they differ, you are editing the wrong tree. The running system is the source of truth for logs and behavior.

2. **Is `bot:decisions` populated?** (most direct proof decisions are flowing)
   ```bash
   redis-cli -h $REDIS_HOST LLEN bot:decisions       # or XLEN if stream — resolve REDIS_HOST from .env first
   redis-cli -h $REDIS_HOST LRANGE bot:decisions -5 -1 | head -1  # check timestamp
   ```
   - **Empty** → decision publishing is blocked. Continue to step 3.
   - **Entries flowing** (timestamps recent, <10 min old) → decisions publish; skip to step 5 (check downstream).
   - **Stale entries** (>10 min old) → stuck after one past decision. Likely resubscribe crash.

3. **Which blocker gates the decision?** (capital, hours, resubscribe, or universe)
   ```bash
   tail -300 /logs/ct101.log | grep -E 'orchestrator.*dispatch|capital|portfolio|Hours|trading.*hours|resubscribe.*fail|NameError'
   ```
   Match the pattern:
   - **`portfolio_value <= 0` or `no_capital`** → Capital blocker (most common on leverage accounts). Root: `orchestrator:511` reads `account.get('cash')` but cash is negative when equity is positive. **Fix:** read `equity` first, fall back `portfolio_value`, then `cash`.
   - **`TradingHoursRule` rejection or `trading_hours_only` blocks** → Hours blocker (double-fail). Root: legacy `.env` gate uses local datetime (no TZ); JSON-loaded rule hardcodes ET. **Fix:** both paths must honor `MARKET_HOURS=24/7` setting.
   - **`resubscribe failed - exiting bot loop`** → Resubscribe crash. Root: `CppMemoryAwareBot` exits permanently on one Redis hiccup. **Fix:** add bounded exponential backoff.
   - **No error, but ConfidenceBooster shows all "0.50 in 0 μs"** → Empty universe. Root: `broker.get_tradable_symbols()` missing on MCPAlpacaBroker (exception swallowed). Bot is symbol-agnostic so this doesn't block dispatch, only universe resolution.

4. **Is the probe tick running instead of real trades?**
   ```bash
   tail -50 /logs/ct101.log | grep ConfidenceBooster | head -5
   ```
   - **All show "0.50 in 0 μs"** → hardcoded liveness probe running, no real decisions.
   - **Variable timing + varied scores** → real trades are flowing; move to step 5.

5. **Are downstream consumers firing?** (if decisions do exist, verify they reach memory/SNN)
   ```bash
   redis-cli -h $REDIS_HOST GET snn:scores | jq '.| length'        # SNN should have trials:>0, hits:>0 — resolve REDIS_HOST from .env first
   tail -50 /logs/memory-fill-sub.log | tail -1                   # timestamp of last fill consumed
   tail -100 /logs/ct101.log | grep -i 'SNN\|confidence_boost\|memory.*pattern' | wc -l  # >0 means firing
   ```
   - **snn:scores empty or all trials=0** → SNN never learned (no decisions reached it).
   - **memory-fill-sub.log stale** (>10 min old) → fills aren't reaching the channel; likely no decisions upstream.
   - **Vectorize HTTP 400** in memory-fill-sub logs → embedding auth or schema failure, not fills.

**Key insight:** each step gates the next. Do not debug downstream (SNN, memory, booster) until you have confirmed decisions flow. If capital check fails, fixing the resubscribe crash will have no effect. Full diagnosis procedure with code fixes: `references/decision-gate-blockers.md`. Queries for KB state: `references/kb-verification-queries.md`.

---

**The SNN (Spiking Neural Network) is a position-SIZE modifier, not a trade gate.** It modulates position scaling by ±10% based on agreement with the bot's trade direction — it does NOT block or approve trades. An SNN disagree rate of 99%+ on out-of-sample data (e.g. 424 agree vs 97K disagree on 2005) is normal conservative behavior, not a wiring failure. The SNN shrinking positions by 10% when it disagrees is functional, not broken. Do not spend time "fixing the SNN" based on disagree rate alone — check `snn:scores` for actual trial/confidence data before concluding it's unwired.

A green boot and healthy probes do **not** mean orders flow. Check the end state:

```bash
# last real trade
psql ... -c "select max(opened_at) from kb.trades"
# hub accounts: positions / open orders / cash
```

`trades` at 2026-08-06 while both paper accounts held 0 positions and 0 orders was the tell. Root cause: `CppMemoryAwareBot` refuses to run without `config["positions_provider"]`, and `basbot_enhanced_orchestrator_production.create_strategic_bot` never injected it — every 15-minute dispatch constructed a bot that exited immediately, so nothing reached `bot:decisions`. The provider is `broker.get_positions` (the bot calls it via `asyncio.to_thread` and then tracks fills). Market data itself was fine: 1,263 bars in 70 s on `market:bars`, 4,267 `market:bars:*` keys.

Health is one key per capability at `ct101:health:<name>`, and each value is a **JSON string, not a hash** — `HGETALL` raises `WRONGTYPE`; use `GET` + `json.loads`. 30 keys is the full set; `degraded` is a finding, so read the failing check's `detail`.

`bot:decisions` being empty right after boot is not proof the path is dead: `CppMemoryAwareBot` buffers `max(window, bots_cpp_memory_aware_bot_run_min)` bars per symbol before deciding (60 one-minute bars ≈ an hour). Check `PUBSUB NUMSUB market:bars` for the bot subscribers and the last `market:bars:SPY` timestamp before calling it broken. Startup dispatch creating 1 bot and skipping 5 is normal strategy selection.

**The core insight:** A fully-wired system with all flags ON, all services answering 200, all probes green can still execute zero trades if an upstream decision gate is closed. The starvation chain is one-way: no `bot:decisions` publish → everything downstream (SNN, memory, booster, risk) idles constructed-but-starved. This is NOT a system wiring problem; it is an ORCHESTRATOR-LEVEL blocker. Do not debug downstream consumers until `bot:decisions` flow. Four known decision blockers are live in production: (1) **negative cash blocks capital check** (most common on leverage accounts) — `orchestrator:511` reads `account.get('cash')`; a −$212k cash + +$96k equity account triggers `portfolio_value ≤ 0` → `EnhancedRiskEngine` returns `(False, no_capital)` → bot.act() returns `hold` forever. Fix: read `equity` first, fall back `portfolio_value`, then `cash`. (2) **hours gate double-fail** — legacy `.env` gate uses local `datetime.now()` (no TZ) defaulting 09:30–16:00 PT; JSON-loaded `TradingHoursRule` in `config/regulatory/rules.json` hardcodes 09:30–16:00 ET. A code patch to `initialize_global_rules` is insufficient; the JSON-load path must also honor `MARKET_HOURS=24/7`. Both gates must use the same source-of-truth. (3) **resubscribe crash exits permanently** — `CppMemoryAwareBot.run()` exits after ONE Redis resubscribe failure; needs bounded exponential backoff (retry 1, 2, 4, 8 s, then give up, not fail-on-first). (4) **empty universe** — `broker.get_tradable_symbols()` missing on MCPAlpacaBroker (exception swallowed → `symbols: []`); bot is symbol-agnostic so doesn't block dispatch, only universe resolution. Fix order: capital (equity) → hours JSON guard → resubscribe backoff → MCP symbols.

**Loaded feed ≠ producing feed; a healthy archive ≠ the live channel.** CT115 answers `/health` 200 with 37M records yet `logs/ct115-feed.log` prints `0 bars published` every 5 min — that is **by design**: live mode does NOT republish the 50-year archive onto `market:bars` (that would mix live with replay); history goes to `market:bars:replay` for training, live mode only feeds today's bars. The live ticker is `live_market_data.py` — Alpaca IEX websocket (`wss://stream.data.alpaca.markets/v2/iex`), which writes `market:bars:{sym}` and publishes to the channel. Verify from the right place: `tail logs/live-market-data.log`, `redis-cli OBJECT IDLETIME market:bars:AAPL`, `PUBSUB NUMSUB market:bars` (subscribers). Critically: fresh key idletime (~8 s) proves the SET leg runs; it says nothing about the channel. Alpaca 1-min bars for ~1,100 symbols arrive in ONE ~2 s burst per minute boundary, channel silent ~97% of the time — a 10 s probe has ~83% chance of legitimately returning 0 messages. A 10 s subscribe is NOT a valid negative test; use ≥70 s and expect ~1,000+ msgs. Only full-window silence with fresh keys is evidence `rc.publish` is dead or writing to a different Redis than subscribers. That exact state — fresh keys + silent channel + healthy NUMSUB — makes a fully-booted system "do nothing" while every /health looks green.

**Historic knowledge lives in two stores with disjoint readers.** `data/historical_50year/global_markets_50year.db` (2 GB, 23M+ bars 2004–2025) is read ONLY by training/verification scripts and `HistoricalDataService` (Flask route + CLI) — nothing on the live bot/decision path reads it. The KB the live loop actually reads is `kb.clusterai_setups` via `setup_recall.py`. When asked "where is historic knowledge / is CT115 feeding", answer per store: who reads it, which channel, what freshness — never "it's loaded".

**Never claim trading is live based on API 200s alone.** The dashboard API returns Alpaca account data (portfolio value, positions) even when the bot loop is completely idle — a `bot:decisions` XLEN of 0 with ConfidenceBooster at `0.50 in 0 μs` means zero decisions are being made, regardless of what `/api/trading/status` says. Verify `bot:decisions` XLEN > 0 before using the word "live" or "trading."

**Wired ≠ firing — distinguish configured, wired, and firing.** When all flags are ON, probes green, services answer 200, but SNN/memory produce nothing: check `bot:decisions` FIRST. The chain is: no decision → no fills → memory vault empty → SNN never learns (trials=0). Distinguish: (a) **Configured but not wired:** flags ON but `bot:decisions` empty (decision gate blocked upstream). (b) **Wired but not firing:** decisions flow but consumers reject them (Vectorize HTTP 400, memory-fill-sub timestamp stale >10 min). Diagnose with firing evidence: `snn:scores` entries show trials/hits; MemoryCompressor logs saved count; bot_decisions_to_domain subscriber fires. Also: **probe ticks pollute greps** — `Trade compliant: AAPL...` every 30 s and `ConfidenceBooster 0.50 in 0 μs` are hardcoded liveness probes, not trades. Verify specific order ID or decision payload, not grep counts.

## Adaptive layer — verify it moves

A sizing probe that returns the same number for every input is a bug. `CompoundEngine.calculate_position_size` once computed confidence, volatility, strategy and compounding factors and then returned `max_size` unconditionally, so every decision was exactly 10 % of capital. Run a confidence × volatility matrix and require monotone-in-confidence, inverse-in-volatility output inside `capital*min_position_size … capital*max_position_size`. Check `confidence-memory-recall` health for `recall_source=wired` — a `# set by <manifest>` comment is not a wire. Read `BOUND_RISK_ENFORCEMENT_MODE` (`warn` logs but lets orders through) before saying risk blocks trading. Full recipes: `references/runtime-verification.md`.

## Historic knowledge — the store the brain actually reads

The live buy loop recalls **`kb.clusterai_setups`** (922,901 pgvector rows) through `infrastructure/ai/setup_recall.py::similar_win_rate`; `kb.clusterai_bar_windows` holds 1,244,497 windows (9,425 symbols, 1962→2025, 1024-d embeddings, `fwd_return_20d`). Gap years 2001–2006 are empty. That path is wired for live recall (cluster_ai logs `setup recall <SYM>: similar-wr …`), but the memory feeding it is incomplete.

`kb.memory_patterns` is a **different** store (41.6M rows, only 22,392 with observations, hex-keyed for the C++ hash path). A `0/N` match there does NOT mean the system has no memory — only that one hash path misses. Verify the real store with `scripts/verify_historic_knowledge.py` (per-year regime + memory coverage + setup-recall AUC). Storage map and hash trap: `references/knowledge-base.md`.

When historic recall produces zero matches: diagnosis, constraint bugs, and the Ollama GPU contention issue: `references/diagnose-embedding-starvation.md`.

### Historic embedding is a real requirement, and it is broken in two ways

`clusterai_bar_windows` has **zero in-repo writers** (git log -S confirms) — its 144,335 rows came from one uncommitted external one-off on 2026-09-06; nothing in the tree fills it, and the gap years 2001–2014 have no rows. Full job size: ~1.13M windows from the 50-year archive (20-bar stride, 9,256 symbols) plus CT115 1962–2006 pre-archive → ≈1.4–1.5M embeddings; the `clusterai_setups` backfill is numeric-only (no embedding). The pipeline that should feed it is a script + direct Ollama POST, not the app's `EmbeddingService`: `embedding_service.py` hardcodes `timeout=10.0` (lines 169/192/220) while the Ollama box measures 14–109 s per embed → ~100% failure for uncached embeds; a real backfill must call `/api/embed` directly with `timeout=300`, `keep_alive=30m`, batch ≥8, and dedupe via `WHERE NOT EXISTS` (the table has no unique constraint). Also `setup_recall._upsert_sync` INSERTs without the `origin` column, but the live `clusterai_setups` table has `origin NOT NULL + CHECK ('live','suite')` → every live setup upsert fails the constraint silently (fail-open); the INSERT must carry `origin='live'`.

**Before blaming the GPU for slow embeds, check WHERE the model runs:** `curl http://<ollama>/api/ps` and read `size_vram` — a loaded model with `size_vram: 0.0 GiB` is running on CPU, not the GPU, regardless of how many models are installed. An RTX 3060 (12 GB) that served 31 embeds/s in September running 0.04–0.06 embeds/s now is a contention/configuration problem (`OLLAMA_MAX_LOADED_MODELS=3` evicting the embed model), not inadequate hardware: unload the big chat models, set `MAX_LOADED_MODELS=1`, pin the embed model with `keep_alive=30m`, re-benchmark ≥5 embeds/s before launching a multi-million-row job.

**GPU detected ≠ embed served.** After a clean restart the journal can print `inference compute id=0 library=CUDA … NVIDIA GeForce RTX 3060` and `found 1 CUDA devices`, yet `POST /api/embed` still hangs past 120 s with no response — observed when `gemma4:12b` was loaded and emitting `slot print_timing … tg=0.75 t/s` continuously and a peer host (10.1.1.114) was POSTing `/api/generate` 500s. An active generation consumer starves the scheduler even with the GPU visible. Diagnose by `journalctl -u ollama -f` in a second shell while issuing the embed: a busy `slot print_timing` or foreign `/api/generate`/`/api/chat` means the fix is consumer-side (pause/relocate that caller), not an Ollama restart. Also check for duplicate daemons first: `systemctl show ollama.service -p MainPID` vs `ps -o pid,ppid,cmd` — an orphaned manual `ollama serve` (PPID 1) alongside the systemd MainPID is killable, but killing it is not the fix if an active consumer is the real cause. Do not kill or restart a shared model box on a half-verified theory; confirm the actual consumer before acting.

**Hosted embedding is the escape hatch when local is slow — but verify the endpoint serves embeddings first.** HF: `api-inference.huggingface.co` has no A record (HF killed that hostname); `router.huggingface.co` serves 127 models, **zero embeddings** — the router is chat-only. A valid `HF_API_KEY` is useless for embeddings until a serving embed model is confirmed. Cloudflare Workers AI `@cf/baai/bge-large-en-v1.5` outputs **1024-dim — schema-compatible with the existing `vector(1024)` column, no migration** — but the `.env` `CLOUDFLARE_API_TOKEN` and the MCP connection both lack the Workers AI `Run` permission (error 9106); that is a dashboard token-scope toggle, not code. Test embed throughput with a 100-embed benchmark and state the measured rate as the basis for the time estimate — never a conditional estimate presented as a figure. **MCP "connected" ≠ Workers AI authorized**: a live connection with 2,182 tools authorized still rejected every AI run call (9106) until the token carries Workers AI `Run`; re-authorize MCP targets via `manage_connections action=authorize` (`reconnect` is managed-connector-only — MCP targets use install/enable/authorize), then verify ONE Workers AI call succeeds before planning an embed job on it.

## Bot-driven historic testing

The 2025-era bot harness is **not in this tree**: `tests/full_system_backtest.py` imports `BotFactory` and never instantiates a bot; `tests/comprehensive_3/backtest_ct115.py` imports `BotManager` and calls `generate_signal` (RSI); the 365-day `ComprehensiveWorldMarketsEngine` survives only as a `singapore_unified` stub. Do not present an RSI `FullDomainStrategy` run as a bot test — instantiate the real `domain/bots` classes and drive them bar by bar. One bot class is not the fleet either: `BasBotEnhancedOrchestratorProduction` deploys `autonomous`, `adaptive`, `memory_aware`, `momentum_enhanced`, `momentum_turbo`, `montecarlo`, `dqn` and `doubler` and combines their confidence; a single `MomentumTurboBot` run is an RSI/momentum baseline, not the autonomous market-aware system.

Real test = real mechanics, not a free-money simulation:

- **Verify the regulation before encoding it.** Read the current FINRA/SEC rule; do not assume a remembered limit is still in force. PDT was eliminated by SR-FINRA-2025-017, but Rule 4210 margin and the $2,000 minimum remain.

- Signals from bar D's close, filled at bar D+1's **open** with adverse slippage (5 bps default) and commission ($0.005/share, $1 min). Never fill at the signal bar's close.
- FINRA Rule 4210 margin: Reg T 50% initial (2× equity), 25% maintenance on long MV, 30% on short MV, 50% short margin, **$2,000 minimum equity**. No negative equity; liquidate on a maintenance breach.
- **PDT is gone**: SR-FINRA-2025-017 (SEC approval 2026-04-14, effective 2026-06-04) eliminated the designation, the day-trade count and the $25,000 minimum. Do not add a day-trade count limit.
- No gain caps either: no profit cap, no arbitrary max-position/profit dial. The only legitimate limits are real margin, buying power, settlement and the account minimum.
- `--ungated` calls `_analyze_market` / `_calculate_metrics` / `_get_trading_parameters` and bypasses only `_validate_opportunity`; sizing still goes through `EnhancedRiskEngine`, outcomes through `ConfidenceBooster`, and the trained SNN as a bounded size confirmation.

Harness recipe, bot defects and measured baselines: `references/bot-driven-backtesting.md`. The C++-boosted bot is `scripts/run_bot_real.py --cpp-bot --snn` (realistic mechanics); it runs `CppMemoryAwareBot` and writes every outcome back to the pattern store.

## External AI layers — configured vs on the decision path

Cloudflare (KV/D1/Vectorize/Workers AI/R2), Ollama (`trade-pattern-8b`, `trade-sentiment-8b`, `trade-memory-3b`), historic sentiment and the 21-year bar DB exist; most are **not** called by the bot/backtest decision loop. Wiring map and call-site status: `references/external-ai-layers.md`. When asked "are we harnessing X", distinguish configured/reachable from called-on-the-decision-path.

## C++ base — measure before describing it

`libtradeengine_core.so` exports **180** symbols (137 TA-Lib indicators, 23 aws memory-bridge, 15 core pattern/decision); `libta_lib.so` exports **1,314**; `libultrafast.so` 10; `libbot_wrapper.so` 10. The Python `talib_full.catalogue()` exposes 158 callable indicators. Never cite the 10-symbol ultrafast shim as "the C++ base".

Latency: raw `core_pattern_hash` (300 bars) is **0.93 µs**, `core_get_confidence_boost` **0.22 µs**; the Python wrapper `pattern_hash` is **85 µs** because it rebuilds four ctypes arrays per call, and `_serialize_cpp_calls()` wraps every binding call in one process-wide lock. Sub-microsecond compute is lost at the Python boundary.

`core_initialize()` used to segfault (exit 139) for two reasons: it ran before `.env` was loaded (so `POSTGRES_HOST`/`REDIS_HOST` defaulted to 127.0.0.1), and libpq's OpenSSL conflicted with the libcrypto that TensorFlow/LLM libraries had already loaded — gdb showed `PQconnectdb -> OPENSSL_sk_num`. Both are fixed: the binding calls `load_project_env()` before `core_initialize()`, and the harness preloads `/lib/x86_64-linux-gnu/libcrypto.so.3` and `libssl.so.3` with `ctypes.RTLD_GLOBAL` before loading the core `.so` (or launch with `LD_PRELOAD`). With that, `CppMemoryAwareBot.initialize()` succeeds and `core_calc_indicators` / `pattern_hash` / `get_confidence_boost` / `update_pattern_confidence` all execute. The C++ confidence boost is **wired and working** — `get_confidence_boost(hash)` returns 1.0 for unseen patterns and accumulates correctly after `update_pattern_confidence` (confirmed: 1.0 → 1.515 after one successful update). A mean boost of 0.5 across a full backtest is normal: 377 updates across 98K signals means most patterns are first-time encounters (boost = 1.0 = neutral), not that the hash format is broken. The wrapper's fallback rule is RSI<45/50 modulated by the boost — it is not a non-RSI strategy.

## Public exposure of the CT101 UI

`https://agent.zaffohome.com` is CT101's public hostname — declared in the deployed `.env` as `FRONTEND_URL`, `VITE_FRONTEND_URL`, `VITE_ALLOWED_HOSTS` and `VITE_WS_URL=wss://agent.zaffohome.com/ws`. Route: Cloudflare `*.zaffohome.com` → tunnel `prox` → NPM ct106 → proxy host **#80** → **`http://10.1.1.98:3003`** (`node dist/server.js`), with per-path locations `/ws/market-data`→8766, `/ws/trading`→8075, `/ws/notifications`→8077, `/ws`→3003. That Express server serves the built SPA from `agents/frontend/dist` *and* owns `/api/trading/*`, `/api/mcphub/*` and `/api/auth/*`; `/` → `/agents/`, title "Zaffo — Cluster Manager".

**Never point the public host at `:4173`.** That port is `vite preview`: static files plus a hand-maintained proxy list. It carries only `/api/trading/market-data` among the trading routes and no `/api/mcphub` at all, so the dashboard renders while every account/tool call returns **502**. `ss -ltnp` reports both node processes as `MainThread`; read `/proc/<pid>/cmdline` before saying which one answers. When changing the NPM forward port, keep the four `locations` in the PUT payload or the `/ws` routes disappear.

### The bridge must boot before the host can proxy to it

`agents/dist/server.js` runs `ConfigService` validation before `listen`. `.env` contains shell-style placeholders (`REDIS_URL=redis://:…@${REDIS_HOST}:${REDIS_PORT}/${REDIS_DB}`, plus `DATABASE_HOST`, `PG_*`); Node `dotenv` does **not** expand them, so the URL fails validation and the process exits with `[ConfigService] REDIS_URL is not a valid URL` — nothing listens and the public URL 502s even when NPM points at the right port. `agents/config/env.ts` expands `${VAR}` in place after load; keep that pass, then `npm run build` and restart. `grep -n '\${' .env` lists the affected keys. Do not hardcode hosts into `.env` to work around it.

The same `.env` holds the credentials for that layer: `CF_EMAIL` + `CF_API_KEY` (Cloudflare **global key** — the `CLOUDFLARE_API_TOKEN` in the shell is a dead token with zero zones), and `NPM_ADMIN_EMAIL` / `NPM_ADMIN_PASSWORD` / `NPM_API_URL` (rewrite to `https://`). When the public URL loops or 502s, work the layer order in `skill_view('homelab-ingress')` instead of reading app logs — a disabled NPM host produces `ERR_TOO_MANY_REDIRECTS` and no app error at all.

Once the host answers, the console's own API surface, machine credential, login wall and defect checklist are in `references/ui-api-diagnostics.md`. Two facts that cost time: the credential the dashboard API accepts is `AGENT_API_KEY` + `x-api-key` on :8002 (`ADMIN_API_KEY` is rejected there), and the console only calls the dozen `/api/*` paths its bundle references — probe those, not plausible REST names.

### Operator access when the saved password is rejected

The console login is the bootstrap `ADMIN_USERNAME` / `ADMIN_PASSWORD_HASH`; a vault password returning `Invalid credentials` is hash drift, not a dead route. To inspect pages without changing credentials, mint an HS256 token from `JWT_SECRET` and set `localStorage.ct101_jwt` (the key in `shared/services/apiClient.ts`). Navigate to `https://agent.zaffohome.com/agents/login` **first** — `localStorage` is denied on `about:blank` — then load `/agents/`; the SPA sends `Authorization: Bearer <token>` on every API call.

### The Trading account list is `.env`, not the hub

`/api/trading/accounts` is built from `ALPACA_ACCOUNTS` in `agents/server.ts` — the four `.env` key pairs — so the selector shows `TradeV4 (Paper)` / `primary` / `default` even though the live data is `alpaca-v2` (`PA3WHUFTBFPU`). The hub's real sets are `alpaca-v2`, `alpaca-v3`, `alpaca-live`. To align labels and routing, build that list from the hub's Alpaca tool sets instead of `.env`. Also diff `daily_pnl` sign between API and UI: the page once rendered `-10662.66` as `+$10,662.66`.

## Hermes bridge (agents, bots, domain)

`infrastructure/hermes/ct101_mcp.py` is the MCP stdio server registered in `~/.hermes/config.yaml` as `ct101`. It exposes live agents (Agent Hub + TS mesh), bots (+ `bot:decisions`), broker state, service health and an AST catalogue plus live caller for every `domain/*` package. Run it with the deployed venv: `/home/claude/timeshift/ct101/venv/bin/python infrastructure/hermes/ct101_mcp.py`. It reads `.env` itself (dashboard key, JWT secret, Redis) because Hermes filters MCP subprocess env. The TS gateway binds `10.1.1.98:3003`, not loopback. Companion skill: `ct101-live-system`.

### MCP bridge — which domain calls work and which fail

`ct101_domain_call` imports modules through the bridge's own subprocess. All 27 domain packages import cleanly when the bridge's `.env` parser is correct. The original `_load_env()` parsed `.env` by hand and did NOT strip inline comments (`# section: ops`) or expand `${VAR}` references — values like `500  # section: ops` and `${POSTGRES_HOST:-10.1.1.50}` caused pydantic type-validation failures (the settings classes use `extra='ignore'`, so the errors were from type coercion, not unknown fields). The fix: use `dotenv_values()` which handles both. If domain imports fail with ConfigError in the bridge but succeed from the deployed venv directly, diff the bridge's parsed values against `dotenv_values('.env')` — inline comments and unexpanded `${VAR}` are the tell.

### dashboard-api crash pattern — branch-merge import errors

When the dashboard-api on :8002 is down but every other service is up and the launcher log shows restart cycles with exit code 1, check `logs/dashboard-api.log` — not the main `ct101.log`. The main log only says `dead process detected: dashboard-api (rc=1) — restart #N`; the dashboard-api log contains the actual traceback. The most common cause: a method with a type hint using a symbol not imported in the deployed worktree (e.g. `async def decide(self, state: Dict[str, Any])` where `Any` was added on one branch but the `from typing import Any` line only exists on the other). This is a **branch-merge artifact** — the method signature was merged but its import was missed because the two branches had different import lines. Fix: `grep` the deployed worktree's file for the import and the type hint; add the missing symbol to the import. Do not restart ct101 for this — the fix goes on disk in the running worktree and the launcher picks it up on the next retry (the backoff grows with each crash, so manually restart ct101 after fixing to avoid waiting minutes).

### Importing the bot fleet and domain into Hermes

To make the full domain and bot fleet importable from `~/.hermes/bots/`, do NOT symlink individual bot `.py` files — they use relative imports (`from .base_bot import`) that only resolve within the `domain.bots.services` package tree. Instead, create a loader `~/.hermes/bots/__init__.py` that adds CT101 root to sys.path, loads `.env`, then imports from `domain.*` and `infrastructure.*`:

```python
# ~/.hermes/bots/__init__.py
import sys, os
_CT101 = "/home/claude/timeshift/ct101"
if _CT101 not in sys.path:
    sys.path.insert(0, _CT101)
from dotenv import load_dotenv
load_dotenv(os.path.join(_CT101, ".env"))

from domain.bots.services.bot_factory import BotFactory
from domain.bots.services.cpp_memory_aware_bot import CppMemoryAwareBot
from domain.bots.services.autonomous_bot import AutonomousBot
# ... all bots ...
from domain.risk import EnhancedRiskEngine
from infrastructure.ai.setup_recall import similar_win_rate
from infrastructure.micro.tradeengine_core_binding import pattern_hash, get_confidence_boost
```

Then `cd ~/.hermes && /home/claude/timeshift/ct101/venv/bin/python -c "import sys; sys.path.insert(0,'.'); import bots"` loads the full fleet. Do NOT symlink `config.py` or `config/` individually — the CT101 root has both, and `config/__init__.py` re-exports `Config`; adding CT101 root to sys.path handles the dual resolution.

### Bot decide() is async — do not call synchronously

`CppMemoryAwareBot.decide(state)` is `async def` and returns a coroutine. Calling it synchronously (`bot.decide(state)`) returns a coroutine object — truthy, so `if d` passes, but the decision never executes and you get zero real buy/sell/hold results. Always `await bot.decide(state)`. The same applies to `AutonomousBot`, `MomentumBot`, and all other bot classes — their public decision interfaces are async. Also: create each bot instance ONCE (not per bar window); constructing a new bot for every window floods logs with thousands of initialization lines and is orders of magnitude slower.

## Key files

| File | Purpose |
|---|---|
| `infrastructure/discovery/surface.py` | Port→script mapping from `.env` + repo walk |
| `infrastructure/discovery/service_discovery.py` | nmap + Proxmox discovery, HTTP fingerprinting, bind_external_services |
| `infrastructure/discovery/external_services.py` | Static externals: Cloudflare, Alpaca, Redis, MCP hub |
| `infrastructure/discovery/connectors/` | Protocol-specific connection adapters |
| `infrastructure/runtime/tier_deploy.py` | T0-T4 boot tiers, REQUIRED_BINDING_TYPES |
| `tests/integration/test_wiring_layer1.py` | 45-tier full-system deployment gate (discovery → bind → every domain + infrastructure module) |
| `main.py` | Process entrypoint, dry-run, tier deployment |
| `scripts/verify_historic_knowledge.py` | Per-year regime + KB pattern match |

## Pitfalls

- **Never call static externals "synthetic" or "fake."** They are config-driven registrations for real services with real connections. Nate will interpret those words as meaning you built stub code.
- **BINDINGS key collision**: when a static external points at the same host:port as a LAN-discovered entry, use the slug as IP so the key is `slug:port` instead of `10.1.1.x:port`. Cloudflare and Alpaca already do this — follow their pattern.
- **`http_generic` races the specialized connector**: both may match a service (http_generic matches any http/https protocol). The specialized connector's lower PRIORITY ensures it's tried first, but if both run in parallel via `asyncio.gather` on the same `host:port`, the last write to BINDINGS wins. Avoid the collision at the registry level by using slug-as-IP.
- **Don't talk about a fix — build it and prove it.** Nate wants action with verification, not descriptions of what you plan to do.
- **Don't stop to ask permission between batches.** Keep going until the task is complete. Asking "want me to continue?" mid-stream breaks momentum — the answer is always yes.
- **When he says "verify, test, verify, apply only after full verification", run that closed loop literally.** Task agents to verify conflicts/requirements read-only, task agents to TEST the proposed fixes, apply ONLY after every fix has a passing test with live evidence. Do not widen the loop into more investigation and more summaries — he experiences that as stalling. Before applying, confirm the live tree is untouched (`git status` baseline unchanged) and state plainly what passed, what failed, and what gate remains.
- **Read-only delegated agents cannot write test artifacts.** If agents must test (not just inspect), grant scratch write explicitly ("may write to /root/.hermes/cache/scratch/<name>/; read-only on the live tree") — the ACP client otherwise denies `write_file` and the test leg silently fails.
- **Never state a conditional estimate as a figure.** "2–3 days IF the cleanup restores ≥5 embeds/s" is not "2–3 days" — the user will (rightly) stop believing numbers that hid their assumption. Quote the measured baseline (e.g. 0.04–0.06 embeds/s measured, 31 embeds/s in September) and state the gate explicitly; or benchmark first and report the measured number.
- **Never report a requirement as "infeasible" without the alternative path in the same message.** When the measured numbers kill a route (11 months at 0.05 embeds/s), pair the number with the concrete fix — hosted embedding (HF/Cloudflare Workers AI), capacity cleanup, or a different store — because a bare "infeasible" reads as refusing to wire the system. The user will name the platform you skipped (HF key, Cloudflare, R2 bucket) and is usually right; check what keys and connected accounts already exist in `.env`/connectors BEFORE declaring a compute job infeasible.
- **Ask once, then execute.** When the user has repeated an instruction or corrected you on the same point, do not ask again or re-explain — just do the thing. Repeating the explanation reads as pushback or refusal to execute. "Do X because it's not wired" → you do X, you verify it worked. "Why isn't it wired?" is a statement of outcome you should validate, not a question inviting more theory. Read the code, find the mismatch, fix it, test it, and report the fix AND proof in the same turn.
- **Never reconstruct a credential or account ID from a masked prefix.** When a call needs a full token/ID and all you have is the first chars (`6f97fb…`), read the complete value from `.env`/vault first — a hand-completed value makes the API reject a perfectly valid call (`9106 Authentication failed`) and sends the diagnosis down "auth broken" instead of the real cause. Extract and use the exact value; never type it out from a prefix.

- **The branch is not the running system.** The deployed tree (`/home/claude/timeshift/ct101`) is frequently hundreds of files ahead of the branch commit because that work is uncommitted. `main.py` can import modules that exist only as untracked files on that disk (`infrastructure/runtime/tier_deploy.py`, `infrastructure/discovery/tier_registry.py` were exactly this), so a clean checkout dies with `ImportError` before T0. Before diagnosing "main.py won't start", diff reality against the commit: `git -C /home/claude/timeshift/ct101 status --short | wc -l`, and `git -C /home/claude/timeshift/ct101 ls-files <path>` for every module the boot path imports. Sync source into the session worktree — the deployed tree is the source of truth for what runs — then verify.
- **A worktree has no `venv`, no `.env`, and no compiled `.so` artifacts.** Run the deployed interpreter (`/home/claude/timeshift/ct101/venv/bin/python`) from the worktree, symlink `.env` into it (it is gitignored), and copy the `infrastructure/micro/*.so` artifacts when the C++ bridge tiers must pass. Missing artifacts surface as "tradeengine core library not found", not as a code bug. For a live run, symlink `venv`, `models` and `data` from the deployed tree and point the unit at the worktree (section above); the interpreter must be the deployed venv because the worktree has no site-packages of its own.
- **Never start a second launcher while `ct101.service` is running.** `supervisor.start_service()` reaps whatever holds a service port, so a worktree launch kills the production children one by one; `--domain-only` is no safer because its loops consume the same Redis streams and write the same heartbeat/control keys. Verify the boot either in a maintenance window after `systemctl stop ct101`, or run the 45-tier gate, which exercises discovery/bind/domain without spawning the launcher's children.
- **`bin/start-backend.sh` can exec the deployed `main.py` while the unit names the worktree.** The wrapper computes its root, then `eval`s `.env`; `.env` exports `PROJECT_ROOT=/home/claude/timeshift/ct101`, so `exec "$PROJECT_ROOT/main.py"` silently runs the other tree and only the cwd is the worktree. Check `/proc/<MainPID>/cmdline`, not `systemctl cat`. Fix by naming the wrapper's own variable `LAUNCHER_ROOT` and using it for venv, logs, `.env` and `main.py`.
- **A synchronous backup on the launcher's event loop stalls dispatch and heartbeat.** `system_state_recovery.backup_loop` awaited `create_full_system_backup()`, whose tarfile/checksum body is synchronous: the 5 s startup dispatch fired ~2 min late and `ct101:health:*` stayed empty until the tar finished. Run it off-loop (`asyncio.to_thread(asyncio.run, rec.create_full_system_backup())`) and guard `psutil` `cmdline=None` (`proc.info.get('cmdline') or []`). Diagnose with `py-spy dump --pid $(systemctl show -p MainPID --value ct101)`: a main thread parked in `select` is idle; a main thread in `tarfile`/`hashlib` is blocking the loop.
- **`pkill -f "<pattern>"` matches its own command line.** `pkill -f "main.py --dry-run"` SIGTERMs the shell running it before any later command executes. Use `pgrep -af "[m]ain.py --dry-run"` and kill by PID.
- **`canonical=` strings are not import-checked.** `--dry-run` resolves component/loop/probe targets but not `Capability.canonical`, so a manifest can point at a module that does not exist while the class actually lives inside the manifest file. Verify canonicals resolve when auditing wiring.
- **Build only after confirming direction.** Adding untested code without running existing tests first compounds the uncommitted problem. Verify, then build, then verify again.
- **When asked to "review the code and find what's not wired," read the FULL implementation chain.** Don't sample a few files and conclude "the code looks complete." Trace an actual execution path end-to-end (e.g. bot dispatch → bot.decide() → action publish → downstream consumer) and verify every function call and return value. A 44K-file system has real code; a few missing method names mean the code is incomplete at specific wiring points, not overall fake. Name the exact mismatches with line numbers.
- **The system is proven to work by backtests.** If backtests show profitable returns and the system is 44,797 files and 27GB, it's REAL. The issue is not "is it fake" (answered: no, it's real) but "why doesn't live trading execute the decisions the backtests prove work." Don't re-analyze whether the code is real.
- **A worktree has no `models/` or `data/`.** `AIPatternRecognitionSystem` resolves `models/pattern_recognition.keras` relative to the process cwd; from a worktree it finds nothing and silently creates fresh random weights (then `patterns_detected=0`). Set `PATTERN_MODELS_DIR=/home/claude/timeshift/ct101/models` or run from the deployed cwd, and confirm the `Pattern model dir:` log points at the real files.
- **`RiskShield` seeds its high-water mark from `initial_capital`.** A $50k account under the $100k default reads a permanent 50% drawdown and rejects every buy (`Drawdown (50.0%) exceeds limit (1.0%)`). Seed from the first observed book value before judging whether risk blocks trading.
- **C++ core in a process that also loads TensorFlow/LLM: preload system OpenSSL.** `core_initialize()` crashes in `PQconnectdb -> OPENSSL_sk_num` when another library has loaded a different libcrypto. Load `/lib/x86_64-linux-gnu/libcrypto.so.3` and `libssl.so.3` with `ctypes.RTLD_GLOBAL` at process start (or `LD_PRELOAD` them), and load `.env` before calling `core_initialize()`. Diagnose native crashes with `gdb -batch -ex run -ex 'bt 20' --args <python> <script>`; the backtrace names the exact library.
- **`MemoryGraph.find_similar_patterns` is O(n) per query.** At 200 symbols it becomes the bottleneck. Keep an exact-key index (side, regime, RSI decile, vol bucket) beside the graph; the graph still stores the nodes and outcomes.
- **Never substitute a toy sweep for the actual domain modules.** When the user asks to "run the full domain modules" or "find the sweet spot for trading," do NOT write a standalone RSI/parameter-sweep script that calls `_calc_rsi`/`_price_outcome` in a loop. That is a single-indicator toy, not the domain pipeline. Use the ct101 MCP tools (`ct101_domain_call`, `ct101_bots`, `ct101_trade`), the imported bot fleet from `~/.hermes/bots/`, or direct `venv/bin/python` calls that instantiate real `domain.*` classes. A bare RSI loop against the SQLite DB is an off-ramp, not the task.
- **`systemctl restart ct101` can time out because shutdown takes longer than systemd's default.** The stop phase may take 15+ seconds; `systemctl restart` with a 15s timeout fails silently (the service ends up `deactivating`). Use `systemctl stop ct101`, wait for `is-active` to report `inactive`, then `systemctl start ct101`. Boot takes 7–8 minutes from cold start.
- **Bot decision paths fail silently.** `MemoryAwareBot.decide()` referenced `_need` without importing it and returned `hold` for every state; `CppMemoryAwareBot.run()` used `_need('bots_cpp_memory_aware_bot_run_min')` with no definition, so every tick raised `NameError` (logged only as `tick processing error`) and `bot:decisions` stayed empty — the helper is `get_bounds().need` and each bot module must define or import it; `AutonomousBot` has an empty `strategies` dict because `initialize_autonomous_learning()` has no caller; `MomentumTurboBot._validate_opportunity` rejects almost everything when momentum peaks below its 0.6 threshold. Probe one bot call and print the rejection reason before concluding the strategy is bad.
- **The GitHub token lives in `~/.hermes/.env`, NOT in the ct101 `.env`.** The project `.env` has `GITHUB_TOKEN` but it may be stale. Hermes's own GitHub token at `~/.hermes/.env` as `GITHUB_TOKEN=` is what `git push` needs — export it and set the remote URL. Check Hermes first: `grep "^GITHUB_TOKEN=" ~/.hermes/.env`. If present, use it; if absent, fall back to the project `.env` token or `gh auth` flow.

- **The 2005 out-of-sample data is a separate SQLite file.** The main `global_markets_50year.db` covers 2007–2025; 2005 data lives in `data/historical_50year/global_markets_2005.db` (68 MB, 799K bars, 2004-09 to 2005-12). Pass it to backtest scripts with `--db /home/claude/timeshift/ct101/data/historical_50year/global_markets_2005.db`. The universe selector filters by year and requires ≥200 bars — use the year with the most sessions as the start year (2005, not the boundary 2004).

- **CT115 (10.1.1.115:8112) serves the full 50-year archive including 2005 data.** `curl "http://10.1.1.115:8112/bars/AAPL?start=2005-01-01&end=2005-06-30&timeframe=1D"` returns real bars — CT115 is not just a live feed. The full-system backtest runner (`scripts/run_ct101_year.py`) uses CT115 as its data source. When a script needs historic bars, prefer CT115 over SQLite — CT115 feeds the same pipeline the live system uses.

- **`get_bounds().need()` requires the pydantic field to exist in BoundsSettings.** Adding `BOUND_BT_MAX_POSITION_SIZE=0.20` to `.env` is not enough — the `bt_max_position_size` field must ALSO be declared in the `BoundsSettings` class in `infrastructure/config/loader.py`. The `need()` method checks `name not in type(self).model_fields` and raises `AttributeError` if the field doesn't exist, regardless of whether the env var is set. When a backtest engine or any component fails with `no bound named 'bt_*'`, grep the caller for `get_bounds().need(...)` to find every missing field name, then add each as `field_name: Optional[float] = None` to the BoundsSettings class.

- **Worktree `data/` symlink blocks `git stash` during merge.** When a worktree has `data -> /home/claude/timeshift/ct101/data` (standard setup per the worktree-live-runtime recipe), any dirty files under `data/` that live through the symlink cannot be stashed — git refuses with `'data/__init__.py' is beyond a symbolic link`. Before merging: commit dirty `data/` files from the MAIN checkout (the symlink target), then verify the worktree's `data/` status is clean. If the merge still fails with the symlink error, `git checkout -- data/<file>` in the worktree to discard the tracked-through-symlink changes, then merge with `--no-autostash`.

- **`run_bot_real.py` and similar standalone scripts are NOT "the system."** They drive one bot class with a subset of domain modules — `run_bot_real.py` uses CppMemoryAwareBot + EnhancedRiskEngine + SNN but does NOT use the turbo optimizer, compound engine, memory orchestrator, confidence booster, or trade tracker that the full domain pipeline provides. When the user asks to "run the system" or "run the full domain modules," they mean the actual MVO pipeline (38 components) driven by BacktestingEngine + FullDomainStrategy — not a standalone harness. `scripts/run_ct101_year.py` IS the full system test: it builds the same MVO factory, same BacktestingEngine, same FullDomainStrategy as the launcher. **Verify it passes memory_graph and snn to FullDomainStrategy** — the MVO builds these components but the script's `build_chain()` function historically did NOT pass them, so the 50-year embedded knowledge was loaded into memory but never queried during backtest (capabilities C02–C05 fired zero times, AC-T08 failed). The fix: add `memory_graph=mvo.get_component("memory_graph"),` and `snn=mvo.get_component("snn"),` to the FullDomainStrategy constructor call. Also verify FullDomainStrategy's parameter names (`snn`, not `snn_net`). After the fix, re-run and check capability fires: every knowledge-recall capability should show >0 fires. Present a standalone script result as what it is — a single-bot baseline, not "the system result."

- **Domain packages with real files but broken/missing `__init__.py` are invisible to the import system.** `domain/handlers`, `domain/services`, `domain/events`, and `domain/models` historically had real `.py` files but their `__init__.py` files were either missing entirely or contained only a bare comment with no exports. The result: `import domain.handlers` succeeded but exposed 0 classes — the code existed but couldn't be reached. Fix: for each domain package, `grep "^class " domain/<pkg>/**/*.py` to find all public classes, then write `__init__.py` with explicit `from .submodule import ClassName` lines. Verify with `python -c "import domain.<pkg>; print([n for n in dir(domain.<pkg>) if not n.startswith('_')])"` — any package with 2 or fewer exports is likely missing its real classes. Do this sweep BEFORE claiming all domain modules are wired.

- **Dead stubs are noise — delete them when real packages are installed.** `torch_stubs.py` in `domain/bots/services/` exists to silently return random values when PyTorch isn't available. If `import torch` succeeds in the deployed venv, the stubs are dead code that nothing imports — delete them rather than letting them survive as a silent fallback that could mask a missing dependency. The user's rule: zero stubs, zero bypassed dependencies, full system adherence.

- **Expose the dedicated Hermes GitHub token.** `~/.hermes/.env` carries a `GITHUB_TOKEN=` entry that is distinct from the project `.env` token and is the one that works. `export GITHUB_TOKEN=$(grep "^GITHUB_TOKEN=" ~/.hermes/.env | head -1 | cut -d= -f2 | tr -d '\n\r')` then `git remote set-url origin "https://Deadseaz:${GITHUB_TOKEN}@github.com/Deadseaz/ct101.git"` followed by `git push`.

- **MCP hub Docker restart** — when all Alpaca tools return "Not connected" but the hub's `/api/servers` shows `status: connected`, the hub's Docker container has stale internal API connections. Restart it from CT112: `ssh root@10.1.1.112 'cd /root/mcp && docker compose restart mcphub'`. Prefer `docker compose restart` over bare `docker restart` — the compose restart also recycles the postgres container which shares OAuth state. After restart, Alpaca connectors appear as "connecting" for 30–90 seconds while they reinitialize OAuth and fetch tool schemas — wait for `status: connected` with 72 tools each before testing.

- **MCP hub OAuth token refresh via database** — when Alpaca tools remain "Not connected" after a Docker restart, the hub's OAuth access tokens have expired. The hub stores tokens in the `oauth_tokens` table in its postgres database (container `mcp-postgres-1`). Check: `docker exec mcp-postgres-1 psql -U mcphub -d mcphub -c "SELECT id, access_token_expires_at, refresh_token_expires_at FROM oauth_tokens;"`. If `access_token_expires_at` is in the past but `refresh_token_expires_at` is still valid, force a refresh: `UPDATE oauth_tokens SET access_token_expires_at = NOW() - INTERVAL '1 day' WHERE refresh_token_expires_at > NOW();` then `docker compose restart mcphub`. Afterwards, `UPDATE servers SET enabled = false, updated_at = NOW() WHERE name LIKE 'alpaca%'; UPDATE servers SET enabled = true, updated_at = NOW() WHERE name LIKE 'alpaca%';` to force the hub to re-scan the connectors.

- **OpenViking config lives at `/opt/openviking_data/ov.conf` inside CT114.** When the Ollama host changes (e.g. CT100 deleted, moved to .8), the `embedding.dense.api_base` and `vlm.api_base` fields must be updated. The port is configured in `server.port` — change it directly (no nginx proxy needed). Edit it through Proxmox: `ssh root@10.1.1.25 "pct exec 114 -- bash -c 'sed -i \"s|http://10.1.1.99:11434|http://10.1.1.8:11434|g\" /opt/openviking_data/ov.conf && systemctl restart openviking'"`. Verify the service bound the new port with `ss -ltnp` inside the container.

- **The console's endpoint list comes from its bundle, not from REST intuition.** `grep -oE '/api/[a-zA-Z0-9/_{}$.-]{2,45}'` over `agents/frontend/dist/assets/index-*.js` yields every path it calls; `/api/account`, `/api/positions`, `/api/orders` are not among them, so their 404s prove nothing. Reporting a 404 on a path the UI never calls is a fabricated bug.
- **An empty list from the API is usually a proxy-target bug, not a dead upstream.** `/api/mcphub/servers` answered `[]` while the hub itself reported 29/29 servers connected — the route was proxied to `:8005`, which has no such path. curl the proxy target's route and the upstream's own health endpoint before writing "hub down".
- **Diff a status mapper's key names against one real payload.** `"online" if b.get("running") or b.get("active")` against a payload that only carries `status: "running"` silently renders every row offline. One sample object settles it in a single request.
- **A search result that looks mangled is a rendering artifact, not corrupted source.** `rg`/`search_files` with ANSI highlighting can erase the matched text in captured output (a real line `Trade compliant: …` rendered as `n: …`), which nearly read as "fake code". When a result looks corrupt, re-read the exact line with plain `grep -n … | cat -A` (or `rg --color=never`) before concluding anything about file contents.
- **Never type the console password; use the vault prompt.** `browser_vault action=save_login` takes it in a masked prompt on the live page. The `users` table is empty, so auth is the bootstrap `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH`, and a rejected password is evidence of hash drift — not a broken login route. Test the endpoint from the page with `fetch('/api/auth/login', …)` to read the exact error body.

## Zero-gate profile (`CT101_ZERO_GATES`)

`infrastructure/zero_gates.py` is the single switch and the only place gate policy is resolved. `docs/GATES.md` is the inventory of record (G01-G34: removed / configured / retained + why).

- **Default is ON** (spec §6.3): a forgotten env var must not restore a gate. `CT101_ZERO_GATES=0` is the only way back.
- **Context matters more than the switch.** `main.py` calls `activate("live")`; `BacktestingEngine.__init__` calls `activate("replay")`. Live keeps market-hours and risk enforcement; replay drops them. A process that declared live is never downgraded by a constructor - otherwise the launcher's own backtest component would relax live gates. `force=True` is test-only.
- `activate("replay")` rewrites `MARKET_HOURS=24/7`, `TRADING_HOURS_ONLY=false`, `BOUND_RISK_ENFORCEMENT_MODE=off` in-process before the bounds cache is read; call it before constructing anything that reads `get_bounds()`.
- Gate sites must consult a predicate (`market_hours_enforced`, `trade_count_caps_enforced`, `risk_enforcement_mode`) and `record("Gxx", reason)` any refusal - never a local `if not FLAG: return`. A run publishes `zero_gates` + `gate_refusals` in its result JSON.
- Proof lives in `tests/zero_gates/test_zero_gate_path.py`: policy layer, the switch-off path, a live-not-downgraded case, static Z1/Z7 AST checks, and a real `setsid ... </dev/null` chain run that must exit 0 with zero refusals.

**Corrupt source hides in plain sight.** `launch_engine.py` and `tests/365_test_scripts/run_365day_backtest.py` were mangled by an earlier edit that glued statements onto one line (often after a `#`, so the code is commented out and the file still parses). Run `ast.parse` over a file before trusting it, and read the exact lines of any block you are about to edit - a menu that "looks fine" in `nl` output can have its logic inside a comment. The repo convention for unrepairable files is `_archive/corrupt-<YYYYMMDD>/` plus a README stating why.


---
name: ct101-live-system
description: "Query or drive live CT101 agents, bots, domain and C++ bridge. MCP + direct import."
version: 1.0.0
author: Nate (Deadseaz), Hermes Agent
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [ct101, live, agents, bots, trading, mcp, domain, cpp]
    category: software-development
    related_skills: [ct101-development]
---

# CT101 live system (MCP bridge + native import)

## When to use

Any question or action about the CT101 trading stack: what agents are running, what a bot is doing, account/positions/orders, service health, or calling into any `domain/*` module.

**Two access paths** — prefer native import for code-level work, MCP tools for runtime operations:

| Path | How | Best for |
|---|---|---|
| **Native import** | `from hermes_agent.ct101 import domain, infra, cpp, bots, overview` | Domain cataloging, C++ bridge, bot class access, code inspection |
| **MCP tools** | `ct101_overview`, `ct101_agents`, `ct101_bots`, `ct101_trade`, etc. | Live agent/bot state, trading operations, service health |

The native module (`hermes_agent.ct101`) imports CT101 directly: 27 domain packages, 30+ infrastructure subsystems, the full C++ bridge (libtradeengine_core.so), and the bot fleet — all in-process, no subprocess bridge. Use it whenever you need to inspect or call CT101 code directly.

The MCP bridge is registered with Hermes as MCP server **`ct101`** (`~/.hermes/config.yaml` → `mcp_servers.ct101`), giving every desktop and gateway session live runtime tools.

## Tools

| Tool | What it returns |
|---|---|
| `ct101_overview` | API health, agent/bot counts, trading status, domain inventory |
| `ct101_agents` | `action=list` merges Agent Hub (:8002) + TS mesh (:3003, JWT-minted); `start/stop/restart` take `agent_id` |
| `ct101_bots` | BotManager + orchestrator fleet, bot types, recent `bot:decisions`; `start/stop` take `bot_id` |
| `ct101_trade` | `view=status\|positions\|orders\|accounts` from the live broker |
| `ct101_services` | The console's own health checks for every declared service |
| `ct101_domain_catalog` | AST inventory of all 25 `domain/*` packages; `package=<name>` for module detail |
| `ct101_domain_call` | Imports and calls any public `domain.*` callable with kwargs; `as_class=true` instantiates; `timeout_s=N` runs it in a killable child process for heavy TF imports |

## Ground truth it reads

- Python dashboard API `DASHBOARD_API_URL` (10.1.1.98:8002), auth `x-api-key: AGENT_API_KEY`, loaded from `/home/claude/timeshift/ct101/.env` by the bridge itself.
- Node gateway `AGENT_SYSTEM_URL` (10.1.1.98:3003) — binds the LAN address, not loopback — auth is a short-lived HS256 JWT minted from `JWT_SECRET`.
- Redis `bot:decisions` (stream or list) for real decision rows.
- The deployed tree at `/home/claude/timeshift/ct101` for the domain catalogue and live imports.

## Rules

- Report what the tool returned; if a call fails, quote the error and status — never substitute remembered state.
- **Never call the system "live" or "trading" based on `ct101_overview` returning `trading_status: ACTIVE`.** That field reads Alpaca account data (portfolio value exists, account is open) — it does NOT mean decisions are publishing. Always cross-check with `ct101_bots` to see `bot:decisions` length. A `bot:decisions` length of 0 with ConfidenceBooster at `0.50 in 0 μs` means the system is idle regardless of what the API says. State "API responding, bot:decisions empty — no trading" not "trading is live."
- `ct101_agents` showing 9 TS-mesh entries and 1 hub entry is the normal shape; the hub entry is the orchestrator's registered bot agent.
- The bridge exports the deployed `.env` into `os.environ` before any domain import; `domain.runtime.mode` reads `CT101_RUNTIME_MODE` directly and would fail loud without it.
- Domain imports can be slow (hundreds of ms) and may connect to Redis/Postgres on construction; pass only real kwargs. TensorFlow-backed packages (`neuromorphic`, parts of `learning`) take minutes on first import — use `timeout_s` so the call fails cleanly instead of blocking the bridge.
- A missing `mcp__ct101__*` tool in a session means that session started before the server was added: start a new session or run `/reload-mcp`.
- `ct101_domain_call` with `as_class=true` returns an instance metadata dict (type, methods, attrs) but **cannot call instance methods** — only module-level functions are directly callable via the `attribute` parameter. Calling an instance method name like `calculate_position_size` on `domain.risk` fails with `AttributeError` because the method lives on the instance, not the module. For instance methods, fall back to `cd /home/claude/timeshift/ct101 && venv/bin/python` direct execution.
- When the ct101 service is down, ALL API-based tools (`ct101_overview`, `ct101_trade`, `ct101_bots`, `ct101_agents`) return `Connection refused` on :8002. This is the service being stopped, not a bridge failure. `ct101_bots` may still show `bot:decisions` from Redis even when the API is unreachable. Start the service with `systemctl start ct101` (boot takes 7-8 minutes).
- The dashboard-api (:8002) can start in boot tier 3 and then die silently — the log says `OK dashboard-api PID=...` but the process is gone and the port is not listening. Verify with `ss -ltnp | grep 8002` and `ps -p <PID>`, not just the log.

## Diagnosing why bots don't trade

**Check actual state BEFORE theorizing about wiring.** Most diagnosis failures are missing dependencies, not logic bugs.

1. **Verify bot decisions are publishing**: `redis-cli -h <REDIS_HOST> XLEN bot:decisions`. If empty and bots are running, skip wiring review and go to step 2.
2. **Check for stubs (missing deps)**:
   - Find stub files: `find /root/.sesori/worktrees/<TREE>/domain -name '*stub*'`
   - Search what they stub: e.g., `torch_stubs.py` means PyTorch missing; `grep -n "Stub" <file>` lists all fallbacks
   - Verify the real package: `python3 -c "import torch"` (if fails, that's your blocker)
   - Stubs returning random values (not raising ImportError) means the system falls back silently — decisions become noise, not trades. This is not a wiring bug.
3. **Trace bot output if decisions ARE publishing**:
   - Check a recent decision: `redis-cli -h <HOST> XRANGE bot:decisions - + COUNT 1`
   - Parse the `action` field (should be 'buy', 'sell', or 'hold')
   - If always 'hold', check if the inner bot's `decide()` method exists and is being called (not None or stub)
4. **Pitfall**: Don't assume wiring is broken just because a bot is created but produces no decisions. Check `redis-cli` first. If the stream is empty, the issue is upstream (no bars arriving to trigger decisions) or a silent exception in the bot execution thread — never a decision-routing logic bug.
5. **Pitfall**: Don't rewrite bot `decide()` interfaces without checking that the wrapper can call them. `CppMemoryAwareBot.run()` expects `await self.decide(state)` where state has OHLCV; if the inner bot has only `act(observation)`, add a bridge method, don't redesign the wrapper.

## Hub Alpaca connector recovery

When all Alpaca tools return "Not connected" despite the hub's `/api/servers` showing `status: connected`, the OAuth tokens have expired.

1. **Check token state**: `ssh root@10.1.1.112 "docker exec mcp-postgres-1 psql -U mcphub -d mcphub -c 'SELECT id, access_token_expires_at, refresh_token_expires_at FROM oauth_tokens ORDER BY updated_at DESC LIMIT 3;'"`
2. **Force refresh**: `UPDATE oauth_tokens SET access_token_expires_at = NOW() - INTERVAL '1 day' WHERE refresh_token_expires_at > NOW();`
3. **Toggle connectors**: `UPDATE servers SET enabled = false WHERE name LIKE 'alpaca%'; UPDATE servers SET enabled = true WHERE name LIKE 'alpaca%';`
4. **Restart**: `cd /root/mcp && docker compose restart mcphub` (not `docker restart` — compose recycles postgres too)
5. Wait 30-90s for connectors to reinitialize (status: "connecting" → "connected" with 72 tools)

**`alpaca-v2` may not exist in the hub database** even though the `/api/servers` endpoint lists it. Check: `SELECT name FROM servers WHERE name LIKE '%alpaca%'`. If only `alpaca-v3` and `alpaca-live` exist, use `BOTMGR_ACCOUNT=alpaca-v3` in `.env` or change `DEFAULT_ACCOUNT` in `broker_factory.py`.

## Dashboard-api crash diagnosis

When :8002 is down and the main log shows `dead process detected: dashboard-api (rc=1) — restart #N`, the actual traceback is in `logs/dashboard-api.log` — NOT in `logs/ct101.log`. The most common cause: a branch-merge artifact where a type hint uses a symbol not imported in the deployed worktree (e.g. `Dict[str, Any]` where `Any` is missing from `from typing import ...`). Cross-check: `grep "from typing" <file>` vs `grep "Dict\[str, Any\]" <file>` in the deployed worktree.

## Verify the bridge

```bash
hermes mcp test ct101
curl -s -H "x-api-key: $(grep -m1 '^AGENT_API_KEY=' /home/claude/timeshift/ct101/.env | cut -d= -f2-)" http://10.1.1.98:8002/api/health
```

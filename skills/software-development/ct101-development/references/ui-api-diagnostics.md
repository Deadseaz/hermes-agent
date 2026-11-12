# Diagnosing the live CT101 console (agent.zaffohome.com)

Use after ingress is proven green (`homelab-ingress`). This is how to find out what the console serves, what its API accepts, and where its data layer lies — with the defect patterns worth checking on every pass.

## 1. Get the endpoint list from the bundle, never from imagination

```bash
B=$(ls /home/claude/timeshift/ct101/agents/frontend/dist/assets/index-*.js | head -1)
grep -oE '/api/[a-zA-Z0-9/_{}$.-]{2,45}' "$B" | sort -u
```

The served HTML references `/agents/assets/index-<hash>.js`; that file is the console. Its live set:

```
/api/health              /api/agents/registry      /api/auth/login
/api/chat                /api/chat/agent           /api/chat/providers/status
/api/discovery/bindings  /api/logs/recent          /api/mcphub/servers/<id>
/api/mcphub/tools        /api/notifications        /api/trading/bots
```

Plausible REST names such as `/api/account`, `/api/positions`, `/api/orders` return 404 on :8002 and say nothing about the console — it never calls them.

## 2. Machine credential

`AGENT_API_KEY` (64 chars) from the deployed `.env`, header `x-api-key`, against `http://10.1.1.98:8002` (dashboard API). `ADMIN_API_KEY` in the same file is rejected there (`401 {"detail":"Invalid API key"}`). `:8003` is a different app — 404 on all of these routes.

```bash
K=$(grep -m1 -E '^AGENT_API_KEY=' .env | cut -d= -f2- | tr -d '"')
curl -sS -H "x-api-key: $K" http://10.1.1.98:8002/api/status
```

Through the public host only `/api/health` and `/api/status` are unauthenticated; every other path answers 401 without a JWT.

## 3. The login wall

- `users` table is empty → auth is the bootstrap admin in `.env`: `ADMIN_USERNAME` + `ADMIN_PASSWORD_HASH` (bcrypt), loaded by `interfaces/web/auth/auth_service.py`.
- Never type the password. Fill the username, then `browser_vault action=save_login` (masked prompt on the page), then submit.
- To read the real failure, POST from the page instead of clicking:
  `fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'admin',password:<field value>})})` → `401 {"detail":"Invalid credentials"}` means the typed password does not match the deployed hash. Check `.env` mtime for a recent rotation before declaring the route broken.
- The login page fires `/api/ai/models`, `/api/ai/provider/status`, `/api/providers/discover` before a session exists → three 401s in the console on every visit.

## 4. Healthy baseline — compare before calling something broken

| Endpoint | Expected |
|---|---|
| `/api/health` | redis PONG, postgres `SELECT 1`, rabbitmq connected, ollama 9 models |
| `/api/status` | 6/6 services: agent_hub, master_agent, crewai, bot_manager, ts_agents, ollama |
| `/api/servers` | ~47 online |
| `/api/agents/registry` | ~22 chat agents |
| `/api/discovery/bindings` | ~196 bindings, summary {reachable, connected, needs_credentials, gated} |
| `10.1.1.112:3000/health` | 29 MCP servers, 29 connected, 0 disconnected |

Re-measure; these are a shape to diff against, not constants.

## 5. Defect patterns to check every pass

**a) Status mapper vs payload keys.** `dashboard_api.py` `/api/agents` maps `"online" if b.get("running") or b.get("active") else "offline"`, but the bot payload carries `status: "running"` and no `running`/`active` key — so every row renders offline. Pull one object and diff the key names.

**b) Proxy target that lacks the route.** `/api/mcphub/servers` and `/api/mcphub/tools` proxy to `:8005`, which has no `/api/mcphub/*` routes (404), so the console shows 0 servers / 0 tools while the hub is healthy at 29/29. Before blaming the upstream service, curl the proxy target's path directly.

**c) Registry leak / phantom rows.** ~159–161 entries all named `CppMemoryAwareBot`, `balance 0`, `pnl 0`, `symbol null`, all `"running"`, ids timestamped continuously across days (15 → 116 → 28 per day) with a single `bot_manager_server.py` process, and every row claiming port 8012 (the manager's own port, hardcoded from `TRADE_AGENTS_MANAGER_PORT`). Duck test: duplicate names + zero state + timestamp spread + one process = no cleanup job, not a bot fleet.

**d) Count disagreement across endpoints.** `/api/agents` 159 vs `/api/bots` 159 vs `/api/trading/bots` 161 — two data sources, not two truths. Report the discrepancy itself as the defect.

**e) Provider health.** `/api/chat/providers/status` returns `{ok:false, detail:"HTTP 400"}` for `minimax` and `claude` while `ollama`, `master-agent`, `ts-orchestrator`, `cluster-ai` are 200. Two of six models unusable — name them.

**f) Open alerts.** `/api/alerts` rows with `status: "open"` carry `count` and `last_seen`; a warning repeating dozens of times (`preflight|aws: The config profile () could not be found`) is a live misconfiguration, not noise.

**g) Domain status vocabulary.** The domain health routes return `{"status":"ok"}`, but dashboard cards treat only `active`/`connected` as healthy — every live service rendered a red X beside the word "Ok". Normalize case-insensitively against `['active','connected','ok','healthy','running','up']`; keep `degraded` yellow.

**h) Memory panels reading the wrong store.** `/api/learning/patterns` queried `embeddings` (does not exist in `kb`) and always returned zero; the real stores are `memory_patterns` (41.6M total / ~22.7k proven) and `clusterai_setups` (922k resolved). `/api/memory/vault-stats` counted 128 snapshot files in `data/vault` (0.1 MB) while the brain held 1.1M rows. Use `_kb_pg_pool()` for `memory_patterns`, `clusterai_setups`, `memory_entries`, `clusterai_bar_windows`; `_memory_pg_pool()` points at `zaffo_memory` and does not contain them.

**i) Empty table vs live upstream.** `/api/domain/market/data` reported `degraded` because `kb.market_data` has 0 rows, while CT115 `/health` reported 37.1M bars and 12k symbols. Fall back to the served historic source (`ct115_historic`, `db_records`) instead of marking a live path dead.

**j) Which tree answers.** The dashboard API on `:8002` can be running `interfaces/api/dashboard_api.py` from the session worktree, not the deployed tree. Read `/proc/<pid>/cmdline` and `/proc/<pid>/cwd` before assuming which checkout your edit reaches; a Python edit only takes effect after that process is restarted.

## 6. Authenticated probes — token claims that pass every route

Mint the token with a `roles` **list**, not a scalar `role` (the `403 Insufficient role` trap in SKILL.md):

```python
import os, time, jwt
from config import load_project_env
load_project_env()
roles = [r.strip() for r in os.environ["JWT_ACCEPTED_ROLES"].split(",") if r.strip()]
tok = jwt.encode({"sub": "admin", "username": "admin", "roles": roles,
                  "exp": int(time.time()) + 3600},
                 os.environ["JWT_SECRET"], algorithm=os.environ.get("JWT_ALGORITHM", "HS256"))
```

Never print the token or `.env` secrets. Probe the Express bridge directly (`http://10.1.1.98:3003`) as well as the dashboard API (`:8002`): the bridge proxies auth and the two can differ in role enforcement.

## 7. Report shape

One line per defect: what the console shows, the measured numbers, and `file:line` where the mapper/proxy is wrong. State which page it breaks. Never list a 404 on a path the UI never calls, and never present a healthy upstream as down because a proxy route points elsewhere.

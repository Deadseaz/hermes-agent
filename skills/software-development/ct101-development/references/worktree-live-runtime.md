# Running the live system from a worktree

Use when `ct101.service` must run a git worktree instead of `/home/claude/timeshift/ct101`.
A worktree is code only — the runtime artifacts live in the deployed tree and are linked in.

## 1. Prep the worktree

```bash
W=/root/.sesori/worktrees/<id>/<name>
ln -s /home/claude/timeshift/ct101/venv   $W/venv
ln -s /home/claude/timeshift/ct101/models $W/models
[ -e $W/.env ] || ln -s /home/claude/timeshift/ct101/.env $W/.env
if [ -d $W/data ] && [ ! -L $W/data ]; then
    mv $W/data $W/data.worktree-only && ln -s /home/claude/timeshift/ct101/data $W/data
fi
chown -R claude:claude $W
chmod o+x /root            # /root is 0700 and the unit runs User=claude
```

Linking `data` means one state shared by both checkouts: bars DBs, memory vault, regime cache,
alerts and backups are the same files. Linking `models` avoids the silent fresh-weights path in
`AIPatternRecognitionSystem`. The interpreter must be the deployed venv — a worktree has no
site-packages.

## 2. Point the unit at the worktree

```bash
cp /etc/systemd/system/ct101.service /etc/systemd/system/ct101.service.bak-$(date +%Y%m%d-%H%M%S)
sed -i "s#WorkingDirectory=/home/claude/timeshift/ct101#WorkingDirectory=$W#; \
        s#ExecStart=/home/claude/timeshift/ct101/bin/start-backend.sh#ExecStart=$W/bin/start-backend.sh#" \
    /etc/systemd/system/ct101.service
systemctl daemon-reload && systemctl restart ct101
```

Never `main.py` a second launcher by hand while the unit is up — it reaps the unit's children.
Restart the unit instead.

## 3. Verify the process, not the unit file

```bash
MP=$(systemctl show -p MainPID --value ct101)
tr '\0' ' ' < /proc/$MP/cmdline     # must be $W/main.py
readlink -f /proc/$MP/cwd           # must be $W
systemctl is-active ct101; systemctl show -p Result -p NRestarts --value ct101
```

If the cmdline names the deployed `main.py` while the cwd is the worktree, stop: the wrapper's
`PROJECT_ROOT` was overwritten by `.env`'s `PROJECT_ROOT` export. Rename the wrapper's variable
to `LAUNCHER_ROOT` (venv, logs, `.env`, `main.py`) and restart.

Boot is 7–8 minutes. Progress is in `$W/logs/ct101.log`:
`[tier N ...] OK|DEGRADED`, then `RUNNING: all tiers green` or `RUNNING DEGRADED: <tiers>`.

```bash
L=$W/logs/ct101.log
grep -a "tier .*OK\|tier .*DEGRADED\|RUNNING\|startup dispatch" $L | tail -10
```

Ports that must answer: 5000 API, 5007 risk-engine, 8000 tradeui, 8095 health-checks, 8765 websocket.

## 4. Verify live data and the bot path

```bash
cd $W && env -u PYTHONPATH venv/bin/python - <<'PY'
from config import load_project_env; load_project_env()
import os, json, redis
r = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
print("health keys", len(list(r.scan_iter("ct101:health:*"))))
print("bot:decisions", r.xlen("bot:decisions") if r.exists("bot:decisions") else 0)
print("market:bars subscribers", r.pubsub_numsub("market:bars"))
print("SPY last bar", r.get("market:bars:SPY"))
PY
```

`env -u PYTHONPATH` matters inside a Hermes shell: Hermes exports its own PYTHONPATH (py3.14
site-packages), so the project venv imports Hermes's PIL and dies on `_imaging`.

Health keys are JSON strings, 30 of them when the heartbeat loop is free. `market:bars:SPY` is a
string carrying the last bar's ISO timestamp — if it is minutes old, the Alpaca IEX feed is live.

## 5. Known boot surface on this host

- T1 bind ~100 s (nmap/discovery), T2 ~90 s, T3 ~50 s, T4+T5 ~110 s, T7 ~90 s, T8 ~20 s.
- T4/T5 report `DEGRADED — <service> started` when a service passes TCP but not its health path; that is not a failed start.
- T7 probes `/health` on every port. Preexisting answers: `:5001` 404 (logs-server), `:8078` 426 (mcp-integration is upgrade-only), `:8013` refused, `:3003` refused (ts-agents), `:4173` refused (frontend). T7 DEGRADED is therefore normal here — list the failing names before blaming the tree move.
- Startup dispatch may create one bot (e.g. `dqn_enhanced`) and skip the rest; that is strategy selection, not a dead fleet.

## 6. Diagnosis

- `py-spy dump --pid $MP` (binary at `venv/bin/py-spy`). MainThread idle in `selectors.select` = event loop free. MainThread in `tarfile`/`gzip`/`hashlib` = a synchronous task blocking dispatch and heartbeat — move it to `asyncio.to_thread`.
- The same lines are written to both `$W/logs/ct101.log` and `/home/claude/timeshift/ct101/logs/ct101.log` because `.env`'s `PROJECT_ROOT` owns the path; two handlers, one log. Not a symptom.
- `journalctl -u ct101` carries the launcher's stdout; `logs/<service>.log` carries each child's output.

## 7. Rollback

```bash
cp /etc/systemd/system/ct101.service.bak-<stamp> /etc/systemd/system/ct101.service
systemctl daemon-reload && systemctl restart ct101
```

Reverting the unit does not undo the symlinks in the worktree; remove them if the worktree goes
back to being a dev checkout.

# Launcher coverage audit — what `main.py` starts vs what the repo declares

Use when Nate says the system is fake, partial, or does not start the real system. The
answer is a coverage table, not an opinion.

## 1. Get the three counts

```bash
cd /home/claude/timeshift/ct101      # the deployed, running tree
venv/bin/python -m infrastructure.discovery.surface --report   # 88 unique ports, internal/unresolved
venv/bin/python main.py --dry-run                              # capabilities/services/components/loops
```

`surface.py` reads every `*_PORT` key in `.env`, classifies it `internal` / `external` /
`other_host` / `unresolved` / `quarantined`, and for internal ports matches a listener-capable
script that also reads that port key. Evidence confidence `c9` = resolved from a live process
argv; `c7` = declared listener marker; lower = name match, treat as a guess.

## 2. Compute the real gap

```bash
venv/bin/python - <<'PY'
from infrastructure.runtime import capability
from infrastructure.runtime.service_inventory import service_inventory
from infrastructure.discovery import surface
specs = service_inventory(capability.load_all(), extra=surface.specs())
declared = {s.script for s in specs if s.script}
for e in surface.surface():
    if e.kind == "internal" and e.script and e.script not in declared:
        print(e.port, e.key, e.script)
PY
```

Classes to report separately:

| class | meaning | action |
|---|---|---|
| declared + started | manifest `ServiceDef` (or discovery extra) with a live script | none |
| internal, script exists, not declared | discovery merges it, unless a name/port/script collision drops it | declare it in a manifest so it has a tier, health path and probe |
| unresolved | `*_PORT` key, no serving script anywhere | implement it or delete the key — this is the fake-service list |
| quarantined | script exists but a tier start proved it cannot serve the port | fix the server or remove the key; see `quarantine.json` |

## 3. How the merge can hide a service

`service_inventory(caps, extra=surface.specs())` drops an extra when:

- its name is already declared;
- its port is already declared;
- its script is already run by a manifest (one process per script);
- its script basename is `main.py` or `system_start.py`.

A manifest that runs one script on several ports (`interfaces/api/controllers/server.py` at
5000 and 8000, `scripts/start_websocket_servers.py` serving 8075/8076/8077/8766) is legal —
the one-process rule applies only to discovered extras. So a port appearing in `--report` as
"not declared" may still be served by a declared process under another key; check the script
before calling it a gap.

## 4. Boot-path integrity checks

- Every module `main.py` imports at runtime must be committed: `tier_deploy`, `tier_registry`,
  `supervisor.owns_port`, `BOOT_TIERS_KEY`, `heartbeat.build_payload(..., tiers=...)`. A clean
  checkout that lacks any of them fails before T0.
- T0 = capabilities loaded, inventory resolved, every script present, every capability declares
  a probe. The probe check is fatal in `tier_deploy.check_config()` even though `--dry-run`
  only warns.
- `Capability.canonical` is documentation unless something imports it — resolve it explicitly
  when auditing. A canonical pointing at a non-existent module is a wiring lie.

## 5. Making the gap unable to recur

The launcher must fail closed on coverage: an internal port with a resolved serving script that
no manifest or discovery entry covers is a `--dry-run` FATAL, and an unresolved `*_PORT` key is
reported by name. Otherwise `main.py` silently starts a subset and every diagnosis restarts from
zero.

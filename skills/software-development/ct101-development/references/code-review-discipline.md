# Code Review Discipline for Complex Trading Systems

## The Mistake Pattern

When asked to review a large codebase (44K files, 27GB) for structural problems, the failure mode is:

1. **Assume instead of read.** "CppMemoryAwareBot calls `await self.decide()`, so there must be a `decide()` method."
2. **Analyze structure instead of tracing execution.** "The architecture looks wired; here's my theory of why it doesn't work."
3. **Look in the wrong place.** Search the filesystem for test results when they live in deployed worktree logs or OpenViking memory.
4. **Confuse design intent with live implementation.** "The code is designed to do X" when the code actually doesn't call X at all.

## The Fix: Verification-First Review

When asked "is this code real or fake?" or "what's not wired?", follow this sequence:

### 1. Understand what's actually running

```bash
readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd  # deployed tree path
cd <that-path> && pwd && git log --oneline -1 && git status --short | wc -l
```

The running system is your ground truth. Development branch edits have no effect on it.

### 2. For "is the code real?" — measure it

```bash
find . -name "*.py" -type f ! -path "*/.*" | wc -l     # Python file count
du -sh .                                                  # Total size
grep -r "^class \|^def " --include="*.py" | wc -l       # Function/class count
```

44,797 Python files, 27GB, thousands of real functions = REAL SYSTEM. Stubs are thin (dozens of lines, all TODOs). Do not spend more time here; the system is proven by backtests showing profitable returns.

### 3. For "why doesn't X work?" — trace the execution path

Do NOT examine code structure (class hierarchy, module imports). DO trace an actual execution:

**Example: "Why aren't decisions publishing?"**

```bash
# Is bot:decisions populated?
redis-cli -h 10.1.1.102 LLEN bot:decisions  # empty? then gate is closed upstream

# Where do decisions come from? Who publishes them?
grep -rn "bot:decisions\|publish.*decision" <deployed-tree>/infrastructure/runtime/capabilities --include="*.py"
grep -rn "bot:decisions\|publish.*decision" <deployed-tree>/domain/bots/services --include="*.py"
```

If no `publish` found, trace the orchestrator that should publish:

```bash
grep -n "class BasBotEnhancedOrchestratorProduction\|def dispatch" <deployed-tree>/domain/bots/services/basbot_enhanced_orchestrator_production.py
```

Read the dispatch method (not its docstring). What does it call? Does it publish anything? Follow each call:

```bash
# Each bot created in dispatch — does it run?
grep -n "async def run\|def run" <deployed-tree>/domain/bots/services/cpp_memory_aware_bot.py

# Read the run method line by line
head -80 <deployed-tree>/domain/bots/services/cpp_memory_aware_bot.py | tail -40  # See the signature
grep -n "publish\|rpush\|lpush" <deployed-tree>/domain/bots/services/cpp_memory_aware_bot.py  # Where does it publish?
```

**Line 597** shows: `await _rs["r"].publish(decision_channel, json.dumps(decision_msg, default=str))`

For publish to happen, what must be true?

```bash
grep -B 20 "publish(decision_channel" <deployed-tree>/domain/bots/services/cpp_memory_aware_bot.py | tail -25  # What's the condition?
```

Line 594-596: `if action_kind:` — the decision is only published if `action_kind` is set.

What sets `action_kind`?

```bash
grep -n "action_kind =" <deployed-tree>/domain/bots/services/cpp_memory_aware_bot.py  # Find all assignments
```

Lines 540, 548, 555, 561 show `action_kind` is set only if `decision_str` is buy/sell/short/long. What sets `decision_str`?

```bash
grep -n "decision_str =" <deployed-tree>/domain/bots/services/cpp_memory_aware_bot.py
```

Line 502: `decision_str = str(decision).lower()`. Where does `decision` come from?

Line 501: `decision = await self.decide(state)`. Does `decide()` exist on the bot class?

```bash
grep -n "def decide\|async def decide" <deployed-tree>/domain/bots/services/momentum_enhanced.py  # The wrapped bot
```

**Empty.** No `decide()` method. That's the wire break.

**The lesson:** You traced backward from "no publish" → "no action_kind" → "no decision" → "no decide() method." Every step was a grep and a file read. You did NOT assume the method exists; you verified it doesn't. Line numbers are specific evidence.

### 4. For "where is the test result?" — search systematically

When told "Thursday backtest showed 60% gain," do NOT assume:
- It's in `./backtest_results/`
- It's in the current branch
- It's in the filesystem

Instead:

```bash
# Deployed worktree (running system is the authority)
ls -lrt /root/.sesori/worktrees/ct101-*/silver-dormouse/backtest_results/ | tail -20
ls -lrt /root/.sesori/worktrees/ct101-*/silver-dormouse/logs/ | grep -E 'backtest|historic|test'

# Database (test results can be outcomes table)
psql -h 10.1.1.102 kb -c "SELECT MAX(created_at), COUNT(*) FROM strategy_outcomes"
psql -h 10.1.1.102 kb -c "SELECT symbol, COUNT(*), SUM(pnl) FROM trades GROUP BY symbol ORDER BY SUM(pnl) DESC LIMIT 5"

# If system memory is connected:
viking_search(query='backtest Thursday 60% gain')
```

Only THEN answer "the test is at <path>, showing <metric>." Not "I couldn't find it; maybe it's ...".

## What NOT to Do

- **Don't describe code architecture.** "The system has a bot orchestrator, domain logic, and a memory vault" tells me the design. I need to know: does the bot orchestrator actually CALL the memory vault? With what data? On which line?
- **Don't cite TODOs or comments as evidence.** A comment saying "this should call X" means nothing if the code doesn't call X.
- **Don't speculate about hidden files or cached values.** "The config might have a setting" → verify with grep and cat, or state plainly "I didn't find it."
- **Don't analyze the whole codebase.** A 44K-file system is too large to "read." Trace ONE execution path (decision publish, historic recall, risk check, whatever is broken) and verify it line by line.
- **Don't assume what the running system does.** It might run a different branch than your checkout. Always check `/proc/<pid>/cwd` and `git log` on that path.

## Evidence Standards


**Bad:** "The system appears to have historic data loaded because the design doc mentions a backfill."

**Good:** `SELECT COUNT(*) FROM clusterai_bar_windows WHERE embedding IS NOT NULL; → 1,240,567 rows, all origin='historic', date range 1962-2025.`

**Bad:** "CppMemoryAwareBot calls decide() and the method probably exists on the wrapped bot."

**Good:** `grep -n 'def decide' domain/bots/services/momentum_enhanced.py → (empty). CppMemoryAwareBot.run() line 501 calls `await self.decide(state)`, but MomentumEnhancedBot has no `decide()` method — only `act(observation)` on line 616.`

**Bad:** "The backtest showed 60% gain, but I can't find the report."

**Good:** (Ask the user for the path, OR check deployed worktree logs, OR check OpenViking memory if connected.) Then cite the exact result.

# Worktree audit — which tree actually wires the system

Use when asked which worktree/branch is canonical, or when the live system and the
checkout you are editing disagree. The question is answered by commit topology + the
running unit's processes — never by `pwd` or the docs.

## Procedure

```bash
# 1. Enumerate everything
cd /home/claude/timeshift/ct101 && git worktree list && git branch -avv
```

```bash
# 2. Establish topology: merge-base of every worktree head with the candidate superset
#    If the result IS one of the heads, that head is an ancestor of the other.
git merge-base <head1> <head2> <head3> ...
```

```bash
# 3. Per-worktree diffs — write them ALL to scratch, full, never a sample
A=/root/.hermes/cache/scratch/wt-analysis && mkdir -p $A
# committed-only vs common ancestor:
git -C $WT diff <ancestor> <head> > $A/<name>-committed.full.patch
# uncommitted-only (working tree vs its own HEAD):
git -C $WT diff HEAD > $A/<name>-uncommitted.full.patch
git -C $WT diff HEAD --stat > $A/<name>-uncommitted.stat.txt
git -C $WT status -s > $A/<name>-status.txt
```

```bash
# 4. The stale-mirror test: is a dirty file identical to content ALREADY committed elsewhere?
#    For every uncommitted-modified file, compare against the other branch's committed copy.
for f in $(git diff HEAD --name-only); do
  git show <candidate-branch>:"$f" 2>/dev/null | diff -q - "$f" >/dev/null 2>&1 \
    || echo "DIFFERS $f"
done
```

Observed result: 244/275 dirty files byte-identical to the live branch's committed
content ⇒ the checkout is a half-applied copy of that branch, not unique work.
Committing it as-is would *revert* live fixes.

```bash
# 5. The verdict: canonical = commit superset AND what the unit actually runs
systemctl cat ct101.service | rg 'WorkingDirectory|ExecStart'
readlink /proc/$(systemctl show -p MainPID --value ct101)/cwd   # must equal the unit's path
```

## Decision rules

- A worktree whose HEAD is the merge-base of all others, with 0 unique commits, is a
  pure ancestor: stale mirror if dirty, dead if clean.
- The correct tree is the one whose HEAD contains every other as an ancestor (commit
  superset) AND is what `ct101.service` `WorkingDirectory`/`ExecStart`/MainPID name.
  Its committed delta vs the common ancestor is the complete wiring delta; everything
  else is contained in it.
- Dirty files byte-identical to another branch's committed content are a half-synced
  mirror — snapshot or discard, never treat as valuable work.
- Check the DIRECTION of a dirty tree before trusting it: a working tree with 45k
  deletions vs the superset branch is reverting it, not adding to it.

## Pitfalls

- `git diff <commit>` on a dirty worktree mixes committed and working-tree state.
  Committed-only = `git diff <ancestor> <head>`; uncommitted-only = `git diff HEAD`
  (run with `git -C $WT` for a worktree).
- `git show <branch>:"$f" | diff -q - "$f"` is the tool that separates "stale mirror"
  from "real divergence" — without it, a large dirty tree looks like valuable work.
- `.claude/worktrees/*` owned by another user trip git's dubious-ownership guard;
  `git config --global --add safe.directory <path>` before `git -C` works there.
- The unit file's `ExecStartPre` can mkdir into the OTHER tree's `logs/` — log paths
  prove nothing about which tree runs. Read the process, not the logs.
- Docs (CONTRACT.md, audit plans) name a canonical branch that reality has moved past;
  treat them as evidence, not truth, and flag the staleness in the audit verdict.

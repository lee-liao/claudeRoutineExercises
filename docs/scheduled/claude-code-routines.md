# Claude Code Routines — setup reference

This repo's daily ADO work-item job can run as a **Claude Code Routine** (a scheduled,
autonomous web session). Unlike the GitHub Actions workflows in `.github/workflows/`, a
Routine's **prompt is entered in the web UI** — it is *not* read from this file. This doc
just version-controls the exact prompt text and the setup steps so they're reproducible.

Docs: https://code.claude.com/docs/en/routines

## Prerequisites (one-time, in the web UI)

1. **Environment** — reuse the same cloud environment this repo already works in. It must:
   - define the `AZURE_DEVOPS_PAT` environment variable (the ADO PAT), and
   - allow network egress to `dev.azure.com` and the npm registry (the `azure-devops`
     MCP server in `.mcp.json` is an `npx` stdio server that calls ADO directly).
   - This session already had both working, so the existing environment is fine.
2. **MCP** — the `azure-devops` server is declared in `.mcp.json`; routines pick it up
   from the repo. No account-level connector needed.

## Permissions

Tool calls that are not auto-allowed will block an unattended run. The committed
`.claude/settings.json` pre-approves every operation the routines need:

| Entry | Purpose |
|-------|---------|
| `mcp__azure-devops__create_work_item` | Create User Story / Task in ADO |
| `mcp__azure-devops__update_work_item` | Set State to Active / Closed |
| `Bash(git add *)` | Stage README.md changes |
| `Bash(git commit *)` | Commit with date message |
| `Bash(git push *)` | Push to remote branch |
| `Bash(node waitForRandomTime.js)` | Run the random-wait script |

No changes needed here; the file is committed and picked up automatically on clone.

### Branch-push permission (web UI — required for push to `main`)

`.claude/settings.json` only governs *tool* approvals. Whether a routine may push to
`main` is a **separate, account-side setting** in the routine's edit form:

1. Open the routine at https://claude.ai/code/routines → pencil icon → **Edit routine**.
2. Go to the **Permissions** tab.
3. Enable **"Allow unrestricted git push"** for `lee-liao/claudeRoutineExercises`.

Without this toggle the proxy blocks any push to a non-`claude/` branch, so the push to
`main` fails. With it on, direct pushes to `main` are allowed. This is the "explicit
permission" the injected branch directive refers to — see *Git workflow & branch behavior*
below. (Changes apply from the **next** run.)

## Random wait

`waitForRandomTime.js` (repo root) sleeps a random **0–1 min + 0–59 sec** before
returning. The routines call it before the first ADO operation and between consecutive
operations to avoid triggering rate-limit or bot-detection heuristics.

## Create the routine

In the web UI at https://claude.ai/code/routines → **New routine**:
1. Name it (e.g. `ADO — create daily work items`).
2. Paste the **Create** prompt below as the instructions.
3. Select repo `lee-liao/claudeRoutineExercises` and the environment from Prerequisites.
4. Trigger → **Schedule** → **daily** (pick your local time, e.g. 09:00 — times are
   entered local and converted to UTC automatically).
5. Create. Repeat for the **Close** prompt on a later daily time (e.g. 18:00).

## Git workflow & branch behavior

This was the trickiest part to get right; the details below come from real failing and
succeeding runs.

**What the harness does by default.** Every routine run starts checked out on a fresh
auto-generated `claude/<random>` branch, and the harness injects a directive telling the
agent to develop there and *not* push elsewhere "without explicit permission". This happens
**regardless of the "Allow unrestricted git push" toggle** — the toggle only removes the
proxy block on pushing to `main`; it does not change which branch is checked out at start.

**Why a naïve prompt fails.** If the prompt just says "push to main", the agent commits on
the `claude/` branch (because that's what's checked out) and then `git push origin main`
pushes the stale local `main` ref — which doesn't even contain the commit — and is rejected
as a non-fast-forward. The README change ends up stranded on the `claude/` branch.

**The fix (used in both prompts below).** Switch to `main` and sync it **before editing
anything**, then commit and push on `main`:

```
1. git checkout main
2. git pull origin main
3. (make the README.md edits)
4. git add README.md && git commit -m "<message>"
5. git push origin main
```

Checking out `main` *first* is deliberate: it keeps all edits on `main` and avoids a
`git stash` / `git stash pop` dance. Popping a stash after pulling can hit a **merge
conflict** on `README.md` (the same file changed on both sides), which would silently break
an unattended run. Edit on `main` directly and there is no stash and no conflict risk.

### Recovery: you already edited files while on a `claude/` branch

In an **interactive** session (or any time you notice the edits landed on the `claude/`
branch *after the fact*), you can't "checkout main first" anymore — the change already
exists in the working tree on the wrong branch. Use `git stash` to carry it across:

```
git stash                       # set the uncommitted edits aside
git checkout main
git pull origin main            # fast-forward main to the latest remote
git stash pop                   # re-apply the edits on top of main
git add <file> && git commit -m "<message>"
git push origin main
```

`git stash pop` re-applies the change as a 3-way merge. It is **safe only when the file's
base content is the same** on the `claude/` branch and on `main`. Verify first with:

```
git diff HEAD origin/main -- <file>     # empty output = same base, pop will be clean
```

If that diff is **non-empty**, the file diverged on `main`; a `pop` may conflict. In that
case resolve the conflict markers by hand (or `git checkout --theirs/--ours` on the file),
then `git add` and commit. This is exactly why the routine *prompts* check out `main`
**before** editing — scheduled runs never enter this recovery path.

**Prerequisite:** the **"Allow unrestricted git push"** permission must be ON (see
*Branch-push permission* above), otherwise step 5 is blocked by the proxy.

**Behavior tab:** leave **"Auto-fix pull requests" OFF**. It only watches/keeps green the
PRs a routine *opens* and never creates or merges PRs — irrelevant to this direct-to-`main`
workflow.

### Cleaning up leftover `claude/` branches

Because each run starts on a `claude/<random>` branch, those branches can pile up on the
remote if anything ever pushes them. With the **push-directly-to-`main`** flow above they
normally don't: the agent commits on `main` and only ever pushes `main`, so the throwaway
`claude/` branch stays local and is discarded when the session's sandbox is reclaimed. (The
web harness also cleans up its own branches — after the runs in this repo, `git ls-remote
--heads origin` showed only `main` and the long-lived `feature/...` branch.)

If a `claude/` branch *does* end up on GitHub, delete it from the remote with:

```
git push origin --delete claude/<name>     # delete the remote branch
```

To inspect and prune in bulk:

```
git ls-remote --heads origin                       # list every remote branch
git fetch --prune                                  # drop local refs for branches gone on the remote
git branch -r --merged origin/main | grep claude/  # remote claude/ branches already merged into main
```

You can also delete a branch from the GitHub web UI (repo → **Branches** → trash icon).
Deleting a `claude/` branch is safe once its work is on `main`; if unsure, confirm the
commits are reachable from `main` first (`git branch -r --contains <sha>` should list
`origin/main`).

> If your org later forbids direct pushes to `main` (e.g. branch protection), this
> direct-push design will start failing. You'd then switch to a PR flow: have the prompt
> open a PR from the `claude/` branch and merge it via GitHub auto-merge or an explicit
> merge step. That adds a CI/review gate at the cost of more moving parts.

---

## Prompt — Create daily work items

> If the target ADO project changes, update the `Target ADO project` line in the Context
> section of this prompt and keep it in sync with the Close prompt below.

```
You are running as an autonomous scheduled routine; no human can answer questions.
Make reasonable decisions and complete the task end to end.

Context
- Azure DevOps org: https://dev.azure.com/cubeforest3003
- Target ADO project: powerBI-demo
- GitHub repo: lee-liao/claudeRoutineExercises; work on the "main" branch.
- The azure-devops MCP server is configured via the repo .mcp.json (PAT from AZURE_DEVOPS_PAT).

Git note — read before the Steps:
The session starts checked out on an auto-created `claude/<random>` branch. That is expected
and you cannot prevent it; do not delete it or push it. Move to `main` BEFORE reading or
editing any file, so every change is made on `main` and no `git stash` is ever needed. The
exact sequence that works:

  # FIRST, before Step 1 below — switch to main and sync it:
  git checkout main && git pull origin main

  # ... then do all the task work (read README.md, ADO calls, edit README.md) on main ...

  # FINALLY, after editing:
  git add README.md && git commit -m "Create ADO work items for <DATE>"
  git push origin main

You have unrestricted push permission for this repo; push directly to `main`.

Steps
1. Switch to main and sync it: run `git checkout main && git pull origin main` before doing
   anything else, so all work below happens on `main`.
2. Determine today's date in UTC as YYYY-MM-DD.
3. Read README.md. Find every row in the Work Items table whose Date == today AND whose
   Status is "pending" (its ID cell is a placeholder token like «story:dayN»).
4. If no rows match, make no changes and stop.
5. Otherwise create the matching items in ADO project powerBI-demo:
   - Run `node waitForRandomTime.js` (random wait before the first ADO call).
   - Create the User Story first; capture its new numeric ID. If the Story's README
     "Parent ID" is already a real numeric ID (e.g. 92, an existing Feature), set the new
     Story's parentId to it so the hierarchy link is created.
   - After creating the User Story, set its State to "Active".
   - For each child Task/Bug:
     - Run `node waitForRandomTime.js` (random wait before each child item).
     - Create the child with parentId = the story's new numeric ID. Map children to their
       parent using the README "Parent ID" token (e.g. «story:day5»).
     - Set Title, Description, and Assigned To from each README row.
     - Set its State to "Active".
6. Edit README.md: replace every placeholder ID token for today's rows with the real
   numeric ID, set Status to "Active", and replace child "Parent ID" tokens with the
   parent's real numeric ID.
7. Commit README.md and push to main with message: "Create ADO work items for <DATE>".
8. Verify each created item's State is Active before finishing. Never print the PAT.
```

## Prompt — Close daily work items

> If the target ADO project changes, update the `Target ADO project` line here to match
> the Create prompt above.

```
You are running as an autonomous scheduled routine; no human can answer questions.
Make reasonable decisions and complete the task end to end.

Context
- Azure DevOps org: https://dev.azure.com/cubeforest3003
- Target ADO project: powerBI-demo
- GitHub repo: lee-liao/claudeRoutineExercises; work on the "main" branch.
- The azure-devops MCP server is configured via the repo .mcp.json (PAT from AZURE_DEVOPS_PAT).

Git note — read before the Steps:
The session starts checked out on an auto-created `claude/<random>` branch. That is expected
and you cannot prevent it; do not delete it or push it. Move to `main` BEFORE reading or
editing any file, so every change is made on `main` and no `git stash` is ever needed. The
exact sequence that works:

  # FIRST, before Step 1 below — switch to main and sync it:
  git checkout main && git pull origin main

  # ... then do all the task work (read README.md, ADO calls, edit README.md) on main ...

  # FINALLY, after editing:
  git add README.md && git commit -m "Close ADO work items for <DATE>"
  git push origin main

You have unrestricted push permission for this repo; push directly to `main`.

Steps
1. Switch to main and sync it: run `git checkout main && git pull origin main` before doing
   anything else, so all work below happens on `main`.
2. Determine today's date in UTC as YYYY-MM-DD.
3. Read README.md. Find every row whose Date == today that has a real numeric ADO ID and
   whose Status is "Active".
4. If no rows match, make no changes and stop.
5. Run `node waitForRandomTime.js` (random wait before the first ADO call).
6. For each matching work item, set its State to "Closed" in ADO project powerBI-demo
   (close child Tasks/Bugs first, then the parent User Story).
   - Run `node waitForRandomTime.js` between each item.
7. Edit README.md: set Status to "Closed" for each affected row.
8. Commit README.md and push to main with message: "Close ADO work items for <DATE>".
9. Never print the PAT.
```

---

## Troubleshooting (lessons from real runs)

| Symptom | Cause | Fix |
|---------|-------|-----|
| `! [rejected] main -> main (non-fast-forward)` and the commit shows a `claude/...` branch tag | Agent committed on the auto-checked-out `claude/` branch, then pushed the stale local `main` ref (which lacks the commit) | Put `git checkout main && git pull origin main` **first**, before any edit; commit and push on `main` |
| Push to `main` blocked / agent insists it may only use a `claude/` branch | **"Allow unrestricted git push"** is OFF in the routine's **Permissions** tab | Turn it ON; it applies from the next run |
| README change "succeeds" but isn't on `main` | Change was committed/stranded on the `claude/` branch | Same as row 1 — check out `main` before editing |
| `git stash pop` reports a conflict mid-run | Stash dance: README edited before switching branches, then `pull` changed README too | Avoid the stash entirely by checking out `main` first |

**Verifying a run actually worked:** a green status only means the session exited without an
infrastructure error — *not* that the task succeeded. Confirm with the remote, e.g.
`git fetch origin main` then check `git show origin/main:README.md` shows the expected
`Closed`/`Active` states, and that the latest `origin/main` commit is the routine's.

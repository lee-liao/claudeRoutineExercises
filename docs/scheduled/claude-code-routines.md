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

> Branch note: routines clone the default branch (`main`) and, by default, push changes
> to a `claude/`-prefixed branch. Both prompts below explicitly commit the README update
> to **`main`** so the evening Close run can find the morning's IDs. If your org forbids
> direct pushes to `main`, change both prompts to push to a shared fixed branch and point
> the GitHub default / Close routine at that same branch.

---

## Prompt — Create daily work items

```
You are running as an autonomous scheduled routine; no human can answer questions.
Make reasonable decisions and complete the task end to end.

Context
- Azure DevOps org: https://dev.azure.com/cubeforest3003
- Target ADO project: powerBI-demo
- GitHub repo: lee-liao/claudeRoutineExercises; work on the main branch.
- The azure-devops MCP server is configured via the repo .mcp.json (PAT from AZURE_DEVOPS_PAT).

Steps
1. Determine today's date in UTC as YYYY-MM-DD.
2. Read README.md. Find every row in the Work Items table whose Date == today AND whose
   Status is "pending" (its ID cell is a placeholder token like «story:dayN»).
3. If no rows match, make no changes and stop.
4. Otherwise create the matching items in ADO project powerBI-demo:
   - Run `node waitForRandomTime.js` (random wait before the first ADO call).
   - Create the User Story first; capture its new numeric ID.
   - After creating the User Story, set its State to "Active".
   - For each child Task/Bug:
     - Run `node waitForRandomTime.js` (random wait before each child item).
     - Create the child with parentId = the story's new numeric ID. Map children to their
       parent using the README "Parent ID" token (e.g. «story:day5»).
     - Set Title, Description, and Assigned To from each README row.
     - Set its State to "Active".
5. Edit README.md: replace every placeholder ID token for today's rows with the real
   numeric ID, set Status to "Active", and replace child "Parent ID" tokens with the
   parent's real numeric ID.
6. Commit README.md and push to main with message: "Create ADO work items for <DATE>".
7. Verify each created item's State is Active before finishing. Never print the PAT.
```

## Prompt — Close daily work items

```
You are running as an autonomous scheduled routine; no human can answer questions.
Make reasonable decisions and complete the task end to end.

Context
- Azure DevOps org: https://dev.azure.com/cubeforest3003
- Target ADO project: powerBI-demo
- GitHub repo: lee-liao/claudeRoutineExercises; work on the main branch.
- The azure-devops MCP server is configured via the repo .mcp.json (PAT from AZURE_DEVOPS_PAT).

Steps
1. Determine today's date in UTC as YYYY-MM-DD.
2. Read README.md. Find every row whose Date == today that has a real numeric ADO ID and
   whose Status is "Active".
3. If no rows match, make no changes and stop.
4. Run `node waitForRandomTime.js` (random wait before the first ADO call).
5. For each matching work item, set its State to "Closed" in ADO project powerBI-demo
   (close child Tasks/Bugs first, then the parent User Story).
   - Run `node waitForRandomTime.js` between each item.
6. Edit README.md: set Status to "Closed" for each affected row.
7. Commit README.md and push to main with message: "Close ADO work items for <DATE>".
8. Never print the PAT.
```

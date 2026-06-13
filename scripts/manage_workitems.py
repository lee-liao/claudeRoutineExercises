#!/usr/bin/env python3
"""
Create ADO work items from README.md table and update their status.

Reads pending rows for WORK_DATE from the Work Items table, creates them
in Azure DevOps (New → Active), then writes back IDs and final state.

Required env vars: ADO_PAT, WORK_DATE
"""

import os, sys, json, base64
import urllib.request, urllib.error

ORG     = "cubeforest3003"
PROJECT = "powerBI-demo"
API_VER = "7.1"
EPIC_ID = 92   # parent Epic all User Stories roll up to

COLS = ['date', 'type', 'title', 'description', 'assigned_to', 'status', 'id', 'parent_id']


# ── ADO helpers ──────────────────────────────────────────────────────────────

def _auth(pat):
    return "Basic " + base64.b64encode(f":{pat}".encode()).decode()

def _call(method, url, pat, body=None):
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization":  _auth(pat),
        "Content-Type":   "application/json-patch+json",
    })
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())

def _base():
    return f"https://dev.azure.com/{ORG}/{PROJECT}/_apis/wit/workitems"

def create_item(wtype, title, description, assigned_to, parent_url, pat):
    url = f"{_base()}/%24{wtype.replace(' ', '%20')}?api-version={API_VER}"
    body = [
        {"op": "add", "path": "/fields/System.Title",       "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": description},
        {"op": "add", "path": "/fields/System.AssignedTo",  "value": assigned_to},
        {"op": "add", "path": "/relations/-", "value": {
            "rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": parent_url,
            "attributes": {"comment": ""},
        }},
    ]
    return _call("POST", url, pat, body)

def patch_state(item_id, state, pat):
    url = f"{_base()}/{item_id}?api-version={API_VER}"
    resp = _call("PATCH", url, pat,
                 [{"op": "add", "path": "/fields/System.State", "value": state}])
    return resp.get("fields", {}).get("System.State", "unknown")


# ── README table helpers ──────────────────────────────────────────────────────

def parse_table(content):
    """Return list of dicts from the first markdown table in content."""
    rows, seen_header, seen_sep = [], False, False
    for line in content.split('\n'):
        s = line.strip()
        if not (s.startswith('|') and s.endswith('|')):
            if rows:
                break
            continue
        cells = [c.strip() for c in s.split('|')[1:-1]]
        if not seen_header:
            seen_header = True
            continue
        if not seen_sep:
            seen_sep = True
            continue
        if len(cells) >= len(COLS):
            rows.append(dict(zip(COLS, cells)))
    return rows

def update_row(content, date, wtype, title, status, item_id, parent_id=''):
    """
    Find the table row matching date+type+title and update status, id, parent_id.
    Column layout (1-indexed after pipe split):
      1=date  2=type  3=title  4=description  5=assigned_to  6=status  7=id  8=parent_id
    """
    marker = f'| {date} | {wtype} | {title} |'
    out = []
    for line in content.split('\n'):
        if marker in line:
            cells = line.split('|')
            cells[6] = f' {status} '
            cells[7] = f' {item_id} '
            if parent_id:
                cells[8] = f' {parent_id} '
            line = '|'.join(cells)
        out.append(line)
    return '\n'.join(out)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pat       = os.environ.get("ADO_PAT")
    work_date = os.environ.get("WORK_DATE")
    if not pat or not work_date:
        sys.exit("ERROR: ADO_PAT and WORK_DATE environment variables are required.")

    with open("README.md") as f:
        content = f.read()

    pending = [r for r in parse_table(content)
               if r['date'] == work_date and r['status'].lower() == 'pending']

    if not pending:
        print(f"No pending items for {work_date}. Nothing to do.")
        return

    print(f"Found {len(pending)} pending item(s) for {work_date}.")
    story_id = None

    # ── User Stories ──
    for item in (r for r in pending if r['type'] == 'User Story'):
        print(f"\n  Creating User Story: {item['title']}")
        parent_url = f"{_base()}/{EPIC_ID}"
        resp = create_item("User Story", item['title'], item['description'],
                           item['assigned_to'], parent_url, pat)
        if not resp.get('id'):
            sys.exit(f"  FAILED: {resp.get('message', resp)}")

        story_id = resp['id']
        print(f"  Created ID {story_id} (New) → patching to Active...")
        final_state = patch_state(story_id, "Active", pat)
        print(f"  User Story {story_id}: {final_state}")

        content = update_row(content, work_date, "User Story",
                             item['title'], final_state, story_id)

    # ── Tasks ──
    for item in (r for r in pending if r['type'] == 'Task'):
        print(f"\n  Creating Task: {item['title']}")
        parent_url = (f"{_base()}/{story_id}" if story_id
                      else f"{_base()}/{EPIC_ID}")
        resp = create_item("Task", item['title'], item['description'],
                           item['assigned_to'], parent_url, pat)
        if not resp.get('id'):
            sys.exit(f"  FAILED: {resp.get('message', resp)}")

        task_id = resp['id']
        print(f"  Created ID {task_id} (New) → patching to Active...")
        final_state = patch_state(task_id, "Active", pat)
        print(f"  Task {task_id}: {final_state}")

        content = update_row(content, work_date, "Task",
                             item['title'], final_state, task_id,
                             str(story_id) if story_id else '')

    with open("README.md", 'w') as f:
        f.write(content)
    print("\nREADME.md updated.")


if __name__ == '__main__':
    main()

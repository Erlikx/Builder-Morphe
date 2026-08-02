import json
import os
import random
import subprocess
import sys
import time
from pathlib import Path

FILES = ["known_signatures.json", "pending_signatures.json"]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return {}
    return {}


def main():
    app_key = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TARGET_APP")
    if not app_key:
        print("APP_KEY not provided, exiting.")
        return

    local_values = {}
    for fname in FILES:
        data = load(Path(fname))
        if app_key in data:
            local_values[fname] = data[app_key]

    if not local_values:
        print(f"No new signature record to commit for {app_key}.")
        return

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

    max_retries = 6
    for attempt in range(max_retries):
        run(["git", "fetch", "origin", "main"])
        run(["git", "reset", "--hard", "origin/main"])

        changed = False
        for fname, value in local_values.items():
            path = Path(fname)
            data = load(path)
            if data.get(app_key) != value:
                data[app_key] = value
                path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
                changed = True

        if not changed:
            print(f"{app_key} is already up to date on main, skipping commit.")
            return

        run(["git", "add", *FILES])
        commit = run(["git", "commit", "-m", f"chore: update signature record for {app_key} [skip ci]"])
        if commit.returncode != 0:
            print("No real change to commit.")
            return

        push = run(["git", "push", "origin", "HEAD:main"])
        if push.returncode == 0:
            print(f"Committed signature record for {app_key}.")
            return

        wait = random.uniform(2, 6) * (attempt + 1)
        print(f"Push conflict (attempt {attempt + 1}/{max_retries}), retrying in {wait:.0f}s...")
        time.sleep(wait)

    print(f"Could not commit signature record for {app_key} (all retries exhausted).")
    sys.exit(1)


if __name__ == "__main__":
    main()

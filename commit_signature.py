import json
import subprocess
import sys
from pathlib import Path

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt

from core import log, retry as retry_conf
from core.settings import settings

FILES = ["data/known_signatures.json", "data/pending_signatures.json"]


class _PushConflict(Exception):
    pass


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
    app_key = sys.argv[1] if len(sys.argv) > 1 else settings.target_app
    if not app_key:
        log.info("APP_KEY not provided, exiting.")
        return

    local_values = {}
    for fname in FILES:
        data = load(Path(fname))
        if app_key in data:
            local_values[fname] = data[app_key]

    if not local_values:
        log.info(f"No new signature record to commit for {app_key}.")
        return

    run(["git", "config", "user.name", "github-actions[bot]"])
    run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"])

    def _attempt() -> None:
        """One fetch-reset-reapply-commit-push cycle. Returns normally once
        there's genuinely nothing left to do (already up to date / nothing
        real to commit) or the push succeeds; raises _PushConflict to
        trigger a retry otherwise."""
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
            log.info(f"{app_key} is already up to date on main, skipping commit.")
            return

        run(["git", "add", *FILES])
        commit = run(["git", "commit", "-m", f"chore: update signature record for {app_key} [skip ci]"])
        if commit.returncode != 0:
            log.info("No real change to commit.")
            return

        push = run(["git", "push", "origin", "HEAD:main"])
        if push.returncode == 0:
            log.success(f"Committed signature record for {app_key}.")
            return

        raise _PushConflict(push.stderr.strip() or "git push failed")

    try:
        for attempt in Retrying(
            stop=stop_after_attempt(6),
            wait=retry_conf.incrementing(start=2.0, increment=2.0, jitter=4.0),
            retry=retry_if_exception_type(_PushConflict),
            before_sleep=retry_conf.before_sleep(f"Push conflict for {app_key}"),
            reraise=True,
        ):
            with attempt:
                _attempt()
    except _PushConflict:
        log.error(f"Could not commit signature record for {app_key} (all retries exhausted).")
        sys.exit(1)


if __name__ == "__main__":
    main()

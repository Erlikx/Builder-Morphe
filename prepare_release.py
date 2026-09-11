import os
import sys
from datetime import UTC, datetime

from core import log
from core.validate import validate_config


def main():
    try:
        validate_config()
    except Exception as e:
        log.error(f"Config validation failed:\n{e}")
        sys.exit(1)

    date = datetime.now(UTC)
    tag = f"build-{date.strftime('%Y-%m-%dT%H-%M-%S')}"
    name = f"Patched APKs - {date.day} {date.strftime('%B %Y')}"

    log.info(f"Release tag for this run: {tag}")
    log.info(f"Release name for this run: {name}")

    # GITHUB_OUTPUT is GitHub Actions' own step-output mechanism, not
    # pipeline configuration, so it stays a direct env lookup rather than a
    # Settings field.
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"tag={tag}\n")
            f.write(f"name={name}\n")


if __name__ == "__main__":
    main()

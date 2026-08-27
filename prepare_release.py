import os
import sys
from datetime import UTC, datetime

from core.validate import validate_config


def main():
    try:
        validate_config()
    except Exception as e:
        print(f"Config validation failed:\n{e}")
        sys.exit(1)

    date = datetime.now(UTC)
    tag = f"build-{date.strftime('%Y-%m-%dT%H-%M-%S')}"
    name = f"Patched APKs - {date.day} {date.strftime('%B %Y')}"

    print(f"Release tag for this run: {tag}")
    print(f"Release name for this run: {name}")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"tag={tag}\n")
            f.write(f"name={name}\n")


if __name__ == "__main__":
    main()

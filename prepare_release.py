import os
from datetime import datetime, timezone

# No release or tag is created here on purpose: creating one up front used to
# leave a draft (and an "untagged-<sha>" ref) sitting in the repo for the
# whole duration of the patch matrix. This script only computes the tag/name
# that the *actual* release will use once it is created by finalize_release.py,
# after every app has finished patching.


def main():
    date = datetime.now(timezone.utc)
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

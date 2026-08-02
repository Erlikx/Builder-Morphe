import asyncio
import os
from datetime import datetime, timezone

from lib.release import ensure_release


async def main():
    date = datetime.now(timezone.utc)
    tag = f"build-{date.strftime('%Y-%m-%dT%H-%M-%S')}"
    name = f"Patched APKs - {date.day} {date.strftime('%B %Y')}"
    body = (
        "### Patched APKs\n\n"
        "Each app was patched in its own job on a separate runner/IP to avoid "
        "Cloudflare bot protection, then added to this shared release.\n"
    )

    print(f"\nCreating shared release: {tag}")
    release = await ensure_release(tag, name, body)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"tag={release['tag_name']}\n")

    print(f"Release ready: {release['tag_name']} (id={release['id']})")


if __name__ == "__main__":
    asyncio.run(main())

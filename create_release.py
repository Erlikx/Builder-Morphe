"""
Matrix workflow'daki "prepare" job'u tarafından çalıştırılır: tüm uygulama
job'larının ortaklaşa yükleme yapacağı TEK bir GitHub Release'i önceden
oluşturur ve tag'ini $GITHUB_OUTPUT'a yazar.

Her uygulama artık ayrı bir job/runner'da (farklı IP ile) çalıştığı için
release'i ayrı ayrı oluşturmak yerine burada bir kere oluşturup tag'i
matrix job'larına env değişkeni olarak geçiyoruz.
"""
import asyncio
import os
from datetime import datetime, timezone

from lib.release import ensure_release


async def main():
    date = datetime.now(timezone.utc)
    tag = f"build-{date.strftime('%Y-%m-%dT%H-%M-%S')}"
    name = f"Patched APKs · {date.day} {date.strftime('%B %Y')}"
    body = (
        "### 📦 Patched APKs\n\n"
        "Her uygulama, Cloudflare bot korumasını aşmak için farklı bir "
        "runner/IP üzerinde ayrı bir iş (job) olarak yamalanıp bu release'e "
        "eklendi.\n"
    )

    print(f"\n📢 Ortak release oluşturuluyor: {tag}")
    release = await ensure_release(tag, name, body)

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"tag={release['tag_name']}\n")

    print(f"✅ Release hazır: {release['tag_name']} (id={release['id']})")


if __name__ == "__main__":
    asyncio.run(main())

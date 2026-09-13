"""Centralized runtime configuration, backed by pydantic-settings.

Every environment variable the pipeline reads is declared here once, with
its type and default, instead of being scattered as ad-hoc os.environ.get()
calls across a dozen modules. Env vars are matched case-insensitively
(KS_PATH, ks_path, Ks_Path all bind to `ks_path`), so every existing GitHub
Actions secret/env name keeps working unchanged.

One shared `settings` singleton is imported by both the core/ library code
and the top-level scripts (main.py, finalize_release.py, prepare_release.py,
commit_signature.py) - and those scripts each only need a subset of these
fields, so nothing here is a required field. Anything that's truly required
for a given entrypoint (e.g. RELEASE_TAG for finalize_release.py) is checked
explicitly at the point of use instead, the same way the original code did
with plain os.environ lookups.
"""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    github_token: SecretStr = SecretStr("")
    github_repository: str = ""

    target_app: str = "all"

    ks_path: Path | None = None
    ks_password: SecretStr | None = None
    ks_alias: str | None = None
    key_password: SecretStr | None = None

    skip_signature_verify: bool = False
    known_signatures_path: Path = Field(default_factory=lambda: Path.cwd() / "data" / "known_signatures.json")
    pending_signatures_path: Path = Field(default_factory=lambda: Path.cwd() / "data" / "pending_signatures.json")

    discord_webhook_url: SecretStr = SecretStr("")
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_chat_id: str = ""
    apprise_urls: SecretStr = SecretStr("")

    no_color: str | None = None
    github_actions: bool = False

    release_tag: str | None = None
    release_name: str | None = None
    artifacts_dir: Path = Path("artifacts")


settings = Settings()

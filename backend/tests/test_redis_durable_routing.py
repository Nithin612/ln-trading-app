"""A41 — `settings.durable_redis_url` is the ONE owner of "which Redis holds durable state".

Unset ⇒ the same instance as `redis_url` (the one-instance deployment, unchanged). The test
suite pins it to the test DB in conftest, so a developer's split `.env` can never point the
suite at a real durable instance.
"""

from __future__ import annotations

from app.core.config import Settings, settings


def test_unset_falls_back_to_the_main_instance() -> None:
    s = Settings(jwt_secret_key="x", database_url="postgresql+asyncpg://a/b",
                 database_url_sync="postgresql+psycopg://a/b",
                 redis_url="redis://h:6379/0", redis_durable_url="")
    assert s.durable_redis_url == "redis://h:6379/0"


def test_set_routes_durable_state_elsewhere() -> None:
    s = Settings(jwt_secret_key="x", database_url="postgresql+asyncpg://a/b",
                 database_url_sync="postgresql+psycopg://a/b",
                 redis_url="redis://h:6379/0", redis_durable_url="redis://h:6380/0")
    assert s.durable_redis_url == "redis://h:6380/0"


def test_the_suite_never_reaches_a_real_durable_instance() -> None:
    assert settings.durable_redis_url == settings.redis_url
    assert settings.redis_url.rstrip("/").endswith("/15")

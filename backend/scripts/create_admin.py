"""One-shot script to bootstrap the first admin user.

Usage (from backend/ directory):
    uv run python scripts/create_admin.py

The script is idempotent — if an admin with that email already exists it
prints a notice and exits without error.
"""

import asyncio
import sys
from pathlib import Path

# Make backend/ the Python root
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DEFAULT_EMAIL = "admin@trading.local"
_DEFAULT_PASSWORD = "Admin123!"
_DEFAULT_NAME = "Platform Admin"


async def create_admin(email: str, password: str, full_name: str) -> None:
    engine = create_async_engine(settings.database_url, echo=False)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing is not None:
            print(f"Admin already exists: {email}  (role={existing.role})")
            return

        admin = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role="admin",
            is_active=True,
            trading_mode="paper",
        )
        session.add(admin)
        await session.commit()
        await session.refresh(admin)
        print(f"Created admin user: {email}  (id={admin.id})")

    await engine.dispose()


if __name__ == "__main__":
    import getpass

    email = input(f"Admin email [{_DEFAULT_EMAIL}]: ").strip() or _DEFAULT_EMAIL
    name = input(f"Full name [{_DEFAULT_NAME}]: ").strip() or _DEFAULT_NAME
    password = getpass.getpass(f"Password (leave blank for default '{_DEFAULT_PASSWORD}'): ")
    if not password:
        password = _DEFAULT_PASSWORD

    asyncio.run(create_admin(email, password, name))

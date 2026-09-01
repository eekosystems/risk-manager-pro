"""Grant or revoke the platform-admin flag on a user.

is_platform_admin is a column on our users table, not an Entra claim — nothing
maps an Entra group onto it, and auto-provisioned users are created with it
false. This script is the bootstrap: the in-app toggle is itself restricted to
platform admins, so the first one has to be granted from outside the app.

Usage:
    cd backend && python -m scripts.grant_platform_admin --list
    cd backend && python -m scripts.grant_platform_admin --email a@b.com
    cd backend && python -m scripts.grant_platform_admin --email a@b.com --revoke
"""

import argparse
import asyncio

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.user import User


async def _list_admins() -> None:
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.is_platform_admin.is_(True)).order_by(User.email)
        )
        admins = list(result.scalars().all())
        if not admins:
            print("no platform admins")
            return
        print(f"{len(admins)} platform admin(s):")
        for user in admins:
            state = "" if user.is_active else "  (inactive)"
            print(f"  {user.email}{state}")


async def _set_flag(email: str, granted: bool) -> None:
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            raise SystemExit(f"no user with email {email!r}")

        if user.is_platform_admin == granted:
            print(f"{email}: already {'a platform admin' if granted else 'not a platform admin'}")
            return

        if not granted:
            remaining = await session.execute(
                select(User).where(
                    User.is_platform_admin.is_(True),
                    User.id != user.id,
                    User.is_active.is_(True),
                )
            )
            if not list(remaining.scalars().all()):
                raise SystemExit(
                    f"refusing to revoke {email!r}: it is the last active platform admin"
                )

        user.is_platform_admin = granted
        await session.commit()
        print(f"{email}: platform admin {'granted' if granted else 'revoked'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default=None)
    parser.add_argument("--revoke", action="store_true")
    parser.add_argument("--list", action="store_true", dest="list_admins")
    args = parser.parse_args()

    if args.list_admins:
        asyncio.run(_list_admins())
        return
    if not args.email:
        raise SystemExit("Pass --email <address>, or --list")
    asyncio.run(_set_flag(args.email, granted=not args.revoke))


if __name__ == "__main__":
    main()

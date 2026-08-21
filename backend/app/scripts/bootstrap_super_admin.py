import argparse
import asyncio
import getpass

from app.db.session import AsyncSessionLocal
from app.services.bootstrap_service import BootstrapService


async def bootstrap(email: str) -> None:
    password = getpass.getpass("Initial SUPER-ADMIN password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    async with AsyncSessionLocal.begin() as session:
        user = await BootstrapService(session).create_initial_super_admin(email, password)
    print(f"Created initial SUPER-ADMIN user: {user.email}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bootstrap the first WCDMS SUPER-ADMIN user.")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    asyncio.run(bootstrap(args.email))

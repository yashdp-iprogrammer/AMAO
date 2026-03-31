from uuid import uuid4
from sqlalchemy import select, func
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from src.Database.models import Role, Client, User
from src.utils.hash_util import hash_util


async def seed_initial_data(session: AsyncSession):
    """
    Populate DB only if tables are empty.
    """

    # --------------------------------------------------
    # 1️⃣ Check if DB already has data
    # --------------------------------------------------

    role_count = await session.execute(select(func.count()).select_from(Role))
    client_count = await session.execute(select(func.count()).select_from(Client))
    user_count = await session.execute(select(func.count()).select_from(User))

    if (
        role_count.scalar_one() > 0 or
        client_count.scalar_one() > 0 or
        user_count.scalar_one() > 0
    ):
        print("Database already contains data. Skipping seeding.")
        return

    print("Database is empty. Seeding initial data...")

    now = datetime.now(timezone.utc)

    # --------------------------------------------------
    # 2️⃣ Insert Roles
    # --------------------------------------------------

    roles = [
        Role(role_id=1, role_name="superadmin", created_at=now, updated_at=now),
        Role(role_id=2, role_name="admin", created_at=now, updated_at=now),
        Role(role_id=3, role_name="user", created_at=now, updated_at=now),
    ]

    session.add_all(roles)
    await session.commit()

    # --------------------------------------------------
    # 3️⃣ Insert Default Client
    # --------------------------------------------------

    client = Client(
        client_id=str(uuid4()),
        client_name="System Client",
        client_email="super@system.com",
        phone="+919999999999",
        password="system_generated",
        is_disabled=False,
        created_at=now,
        updated_at=now,
    )

    session.add(client)
    await session.commit()
    await session.refresh(client)

    # --------------------------------------------------
    # 4️⃣ Insert SuperAdmin User
    # --------------------------------------------------

    password_handler = hash_util
    hashed_password = password_handler.get_password_hash("SuperAdmin@123")

    user = User(
        user_id=str(uuid4()),
        client_id=client.client_id,
        user_name="Super Admin",
        user_email="superadmin@system.com",
        user_mobile="+919999999999",
        user_password=hashed_password,
        role_id=1,
        is_disabled=False,
        created_at=now,
        updated_at=now,
    )

    session.add(user)
    await session.commit()

    print("Initial data seeded successfully.")

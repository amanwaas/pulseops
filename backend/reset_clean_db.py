import asyncio
from sqlalchemy import text
from app.core.database import AsyncSessionLocal, init_db

async def reset_clean_database():
    """
    Purges all dummy data across all tables.
    Leaves the database schema completely clean with 0 records.
    """
    print("Initializing clean schema...")
    await init_db()

    async with AsyncSessionLocal() as session:
        print("Purging all dummy data...")
        tables = [
            "health_logs",
            "incidents",
            "alert_configs",
            "health_targets",
            "deployments",
            "projects",
            "users",
        ]
        for t in tables:
            await session.execute(text(f"DELETE FROM {t}"))
            print(f"  - Cleared {t}")
        await session.commit()
    print("Database is now 100% clean with zero dummy data.")

if __name__ == "__main__":
    asyncio.run(reset_clean_database())

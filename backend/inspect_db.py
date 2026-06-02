import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.append(r"c:\Users\Sai Teja\Documents\Agentops\backend")

from app.core.database import get_engine
from sqlalchemy import text

async def list_db_agents():
    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT id, name, display_name, endpoint_url, region, gcp_project, status, source FROM agents"))
        rows = result.fetchall()
        print(f"Total agents in DB: {len(rows)}")
        for r in rows:
            print(f"- ID: {r.id}")
            print(f"  Name: {r.name}")
            print(f"  Display Name: {r.display_name}")
            print(f"  Endpoint: {r.endpoint_url}")
            print(f"  Status: {r.status}")
            print(f"  Source: {r.source}")
            print()

if __name__ == "__main__":
    asyncio.run(list_db_agents())

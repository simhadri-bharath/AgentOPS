import asyncio
import os
import sys

# Ensure backend directory is in path
sys.path.append(r"c:\Users\Sai Teja\Documents\Agentops\backend")

from app.core.database import get_engine
from app.services.discovery.vertex_ai import VertexAIDiscoveryService
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

async def test():
    engine = get_engine()
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        service = VertexAIDiscoveryService(session)
        await service.initialize()
        
        print("Listing reasoning engines from GCP...")
        engines = await service.list_reasoning_engines()
        print(f"Total engines found on GCP: {len(engines)}")
        
        for i, engine in enumerate(engines):
            name = getattr(engine, "display_name", None) or str(engine)
            resource_name = getattr(engine, "resource_name", None) or "N/A"
            print(f"\n[{i+1}] Engine:")
            print(f"  Display Name: {name}")
            print(f"  Resource Name: {resource_name}")
            try:
                parsed = service.parse_reasoning_engine(engine)
                print(f"  Parsed Agent UUID: {parsed.id}")
                print(f"  Parsed Agent Name: {parsed.name}")
                print(f"  Parsed Agent Display Name: {parsed.display_name}")
            except Exception as e:
                print(f"  Parsing failed: {e}")
                
        print("\nRunning sync to database...")
        summary = await service.sync_to_database()
        print(f"Sync complete. Discovered: {summary.discovered}, Created: {summary.created}, Updated: {summary.updated}, Unchanged: {summary.unchanged}")
        if summary.errors:
            print(f"Errors encountered during sync: {summary.errors}")

if __name__ == "__main__":
    asyncio.run(test())

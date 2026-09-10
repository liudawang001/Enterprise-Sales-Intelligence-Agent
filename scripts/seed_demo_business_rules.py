"""Idempotently seed the two Phase 3 demo businesses and marketing rules."""
import asyncio
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models.rule import BusinessCatalogRecord, MarketingRuleRecord
from app.rules.registry import BUSINESS_CATALOG


DEMO_RULES = [
    ("GROUP_VNET", "office_count", "GTE", 2, "INTEGER", 0.20, "优先关注多个办公地点企业"),
    ("GROUP_VNET", "cross_region_presence", "EQ", True, "BOOLEAN", 0.15, "跨区域内部通信需求更相关"),
    ("ENTERPRISE_DEDICATED_LINE", "company_scale", "IN", ["MEDIUM", "LARGE"], "ENUM", 0.20, "中大型企业更适合专线"),
    ("ENTERPRISE_DEDICATED_LINE", "office_count", "GTE", 1, "INTEGER", 0.10, "具有固定办公地点的企业优先"),
]


async def seed() -> None:
    engine = create_database_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    try:
        async with factory.begin() as session:
            for definition in BUSINESS_CATALOG.values():
                statement = insert(BusinessCatalogRecord).values(**definition).on_conflict_do_update(index_elements=[BusinessCatalogRecord.code], set_={"name": definition["name"], "aliases": definition["aliases"], "enabled": definition["enabled"]})
                await session.execute(statement)
            for business, field, operator, value, value_type, weight, rationale in DEMO_RULES:
                source_key = f"demo:{business}:{field}:{operator}:{value}"
                statement = insert(MarketingRuleRecord).values(id=uuid5(NAMESPACE_URL, source_key), business_code=business, field=field, operator=operator, value=value, value_type=value_type, constraint_type="SOFT", weight=weight, region=None, effective_from=None, effective_to=None, rationale=rationale, status="ACTIVE", source_key=source_key).on_conflict_do_update(index_elements=[MarketingRuleRecord.source_key], set_={"value": value, "weight": weight, "rationale": rationale, "status": "ACTIVE"})
                await session.execute(statement)
        print(f"Seeded {len(BUSINESS_CATALOG)} businesses and {len(DEMO_RULES)} marketing rules")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()


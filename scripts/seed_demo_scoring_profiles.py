"""Idempotently seed immutable Phase 5 demo scoring profile versions."""

import asyncio
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.persistence.database import create_database_engine, create_session_factory
from app.persistence.models.verification import ScoringProfileRecord
from app.scoring.profiles import demo_scoring_profiles


async def seed() -> None:
    engine = create_database_engine(get_settings().database_url)
    factory = create_session_factory(engine)
    profiles = demo_scoring_profiles()
    try:
        async with factory.begin() as session:
            for profile in profiles:
                key = f"scoring-profile:{profile.business_code}:{profile.version}"
                stable = profile.model_copy(
                    update={"profile_id": str(uuid5(NAMESPACE_URL, key))}
                )
                statement = (
                    insert(ScoringProfileRecord)
                    .values(
                        id=uuid5(NAMESPACE_URL, key),
                        business_code=stable.business_code,
                        version=stable.version,
                        profile_json=stable.model_dump(mode="json"),
                        active=stable.active,
                        created_at=stable.created_at,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            ScoringProfileRecord.business_code,
                            ScoringProfileRecord.version,
                        ]
                    )
                )
                await session.execute(statement)
        print(f"Seeded {len(profiles)} immutable demo scoring profiles")
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()

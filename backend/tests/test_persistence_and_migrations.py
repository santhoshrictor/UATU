import uuid
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.models.site import Area, Site


def test_schema_and_tables_exist_in_test_db(test_engine):
    """Verify that Alembic migrations created the required tables in workplace_test."""
    with test_engine.connect() as conn:
        result = conn.execute(
            text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name;"
            )
        )
        tables = [row[0] for row in result.fetchall()]
        assert "alembic_version" in tables
        assert "sites" in tables
        assert "areas" in tables


def test_data_persistence_across_connection_lifecycles(test_engine):
    """
    Demonstrate that a controlled test record persists across an entirely new
    database connection and session lifecycle on the real PostgreSQL test database.
    """
    test_site_id = uuid.uuid4()
    test_area_id = uuid.uuid4()
    site_code = f"TEST-SITE-{uuid.uuid4().hex[:6].upper()}"
    area_code = f"TEST-AREA-{uuid.uuid4().hex[:6].upper()}"

    # Lifecycle 1: Connect, insert test record, commit, and explicitly close and dispose
    SessionLocal1 = sessionmaker(bind=test_engine)
    with SessionLocal1() as session1:
        site = Site(
            id=test_site_id,
            name="Alpha Testing Plant",
            code=site_code,
            description="Controlled automated test site",
            timezone="Asia/Calcutta",
        )
        area = Area(
            id=test_area_id,
            site=site,
            name="Main Assembly Bay",
            code=area_code,
            area_type="workshop",
            description="Testing workshop area",
        )
        session1.add(site)
        session1.add(area)
        session1.commit()

    # Dispose connection pool to guarantee physical connection disconnect
    test_engine.dispose()

    # Lifecycle 2: Connect afresh via a new engine instance, query, and verify persistence
    new_engine = create_engine(settings.test_database_url, pool_pre_ping=True)
    SessionLocal2 = sessionmaker(bind=new_engine)
    with SessionLocal2() as session2:
        queried_site = session2.execute(
            select(Site).where(Site.id == test_site_id)
        ).scalar_one_or_none()

        assert queried_site is not None
        assert queried_site.code == site_code
        assert queried_site.name == "Alpha Testing Plant"
        assert len(queried_site.areas) == 1

        queried_area = queried_site.areas[0]
        assert queried_area.id == test_area_id
        assert queried_area.code == area_code
        assert queried_area.area_type == "workshop"

        # Cleanup test record
        session2.delete(queried_site)
        session2.commit()

    new_engine.dispose()


def test_cascade_delete_integrity(test_engine):
    """Verify that deleting a site cascades and removes associated areas."""
    site_id = uuid.uuid4()
    site_code = f"CASCADE-SITE-{uuid.uuid4().hex[:6].upper()}"
    
    SessionLocal = sessionmaker(bind=test_engine)
    with SessionLocal() as session:
        site = Site(
            id=site_id,
            name="Decommission Facility",
            code=site_code,
            timezone="Asia/Calcutta",
        )
        area = Area(
            id=uuid.uuid4(),
            site=site,
            name="Decommission Zone",
            code="DEC-ZONE",
            area_type="warehouse",
        )
        session.add(site)
        session.commit()

        # Verify area exists
        area_count = session.execute(
            select(Area).where(Area.site_id == site_id)
        ).scalars().all()
        assert len(area_count) == 1

        # Delete site
        session.delete(site)
        session.commit()

        # Verify area was cascaded and deleted
        area_after = session.execute(
            select(Area).where(Area.site_id == site_id)
        ).scalars().all()
        assert len(area_after) == 0

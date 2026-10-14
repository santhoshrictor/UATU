import uuid
from typing import List, Optional
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base, TimestampMixin


class Site(Base, TimestampMixin):
    """
    Physical workplace facility or campus location.
    Establishes the primary spatial scope for monitoring and cameras.
    """
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Calcutta", nullable=False)

    # Relationships
    areas: Mapped[List["Area"]] = relationship(
        "Area",
        back_populates="site",
        cascade="all, delete-orphan",
        order_by="Area.name",
    )

    def __repr__(self) -> str:
        return f"<Site(code='{self.code}', name='{self.name}')>"


class Area(Base, TimestampMixin):
    """
    Monitored workplace area within a site (e.g. entry/exit, stores, workshop, tool room).
    Provides spatial grouping for cameras and analytics zones.
    """
    __tablename__ = "areas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False)
    area_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type such as entry_exit, workshop, corridor, canteen, warehouse, tool_room, yard"
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    site: Mapped["Site"] = relationship("Site", back_populates="areas")

    def __repr__(self) -> str:
        return f"<Area(code='{self.code}', name='{self.name}', type='{self.area_type}')>"

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

ASSET_STATUSES = (
    "REGISTERED",
    "AVAILABLE",
    "ALLOCATED",
    "DISPATCHED",
    "DELIVERED",
    "INSTALLED",
    "IN_SERVICE",
    "UNDER_REPAIR",
    "RETURNED",
    "REPLACED",
    "RETIRED",
    "DISPOSED",
    "LOST",
    "DAMAGED",
    "CANCELLED",
)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        CheckConstraint(f"status IN {ASSET_STATUSES}", name="ck_assets_status"),
        UniqueConstraint("normalized_serial", name="uq_assets_normalized_serial"),
        Index("ix_assets_product", "product_id"),
        Index("ix_assets_project_status", "current_project_id", "status"),
        Index("ix_assets_warranty_expiry", "warranty_expiry_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_number: Mapped[str] = mapped_column(String(50), unique=True)
    manufacturer_serial_number: Mapped[str] = mapped_column(String(255))
    normalized_serial: Mapped[str] = mapped_column(String(255))
    internal_tag: Mapped[str | None] = mapped_column(String(100), unique=True)
    product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("products.id"))
    product_snapshot: Mapped[str] = mapped_column(String(2000))
    oem_party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    oem_snapshot: Mapped[str | None] = mapped_column(String(255))
    product_model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("product_models.id"))
    model_snapshot: Mapped[str | None] = mapped_column(String(255))
    vendor_party_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parties.id"))
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_orders.id"))
    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("purchase_order_lines.id"))
    material_receipt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("material_receipts.id"))
    material_receipt_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("material_receipt_lines.id")
    )
    receipt_date_snapshot: Mapped[date] = mapped_column(Date)
    source_project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    source_loa_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loas.id"))
    project_snapshot: Mapped[str] = mapped_column(String(255))
    loa_snapshot: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="REGISTERED")
    current_project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    current_railway_zone_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_zones.id")
    )
    current_railway_division_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_divisions.id")
    )
    current_railway_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_locations.id")
    )
    current_site: Mapped[str | None] = mapped_column(String(255))
    current_building: Mapped[str | None] = mapped_column(String(255))
    current_room: Mapped[str | None] = mapped_column(String(255))
    current_rack: Mapped[str | None] = mapped_column(String(100))
    current_position: Mapped[str | None] = mapped_column(String(100))
    installation_date: Mapped[date | None] = mapped_column(Date)
    warranty_type: Mapped[str | None] = mapped_column(String(100))
    warranty_reference: Mapped[str | None] = mapped_column(String(255))
    warranty_start_date: Mapped[date | None] = mapped_column(Date)
    warranty_duration_months: Mapped[int | None] = mapped_column()
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date)
    warranty_provider_party_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("parties.id"))
    warranty_remarks: Mapped[str | None] = mapped_column(Text)
    replacement_asset_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("assets.id"))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    events: Mapped[list["AssetLifecycleEvent"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
        order_by="AssetLifecycleEvent.created_at",
    )


class AssetLifecycleEvent(Base):
    __tablename__ = "asset_lifecycle_events"
    __table_args__ = (Index("ix_asset_events_asset_date", "asset_id", "event_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(30))
    from_status: Mapped[str | None] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    from_location_snapshot: Mapped[str | None] = mapped_column(Text)
    to_location_snapshot: Mapped[str | None] = mapped_column(Text)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id"))
    railway_zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("railway_zones.id"))
    railway_division_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_divisions.id")
    )
    railway_location_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("railway_locations.id")
    )
    supply_challan_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("supply_challans.id"))
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actor_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(1000))
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    asset: Mapped[Asset] = relationship(back_populates="events")


class ChallanAssetAssignment(Base):
    __tablename__ = "challan_asset_assignments"
    __table_args__ = (
        UniqueConstraint("asset_id", name="uq_challan_asset_assignment_asset"),
        UniqueConstraint("supply_challan_line_id", "asset_id", name="uq_challan_line_asset"),
        Index("ix_challan_asset_assignments_line", "supply_challan_line_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    supply_challan_line_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("supply_challan_lines.id", ondelete="CASCADE")
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assets.id"))
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

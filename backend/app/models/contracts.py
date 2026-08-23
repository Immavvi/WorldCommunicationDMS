import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LoaItem(Base):
    __tablename__ = "loa_items"
    __table_args__ = (
        UniqueConstraint("loa_id", "item_number", name="uq_loa_item_number"),
        CheckConstraint("original_approved_quantity >= 0", name="ck_loa_item_quantity"),
        CheckConstraint("contractual_rate >= 0", name="ck_loa_item_rate"),
        CheckConstraint("original_line_value >= 0", name="ck_loa_item_value"),
        Index("ix_loa_items_loa", "loa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    loa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loas.id"))
    item_number: Mapped[str] = mapped_column(String(50))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str] = mapped_column(String(2000))
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hsn_codes.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units_of_measure.id"))
    original_approved_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    contractual_rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    original_line_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    remarks: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    variation_lines: Mapped[list["LoaVariationLine"]] = relationship(back_populates="loa_item")


class LoaVariation(Base):
    __tablename__ = "loa_variations"
    __table_args__ = (
        UniqueConstraint("loa_id", "reference_number", name="uq_loa_variation_reference"),
        CheckConstraint(
            "status IN ('DRAFT','APPROVED','APPLIED','REJECTED','CANCELLED')",
            name="ck_loa_variation_status",
        ),
        Index("ix_loa_variations_loa", "loa_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    loa_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("loas.id"))
    reference_number: Mapped[str] = mapped_column(String(100))
    variation_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", server_default="DRAFT")
    remarks: Mapped[str | None] = mapped_column(String(2000))
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["LoaVariationLine"]] = relationship(
        back_populates="variation", cascade="all, delete-orphan"
    )


class LoaVariationLine(Base):
    __tablename__ = "loa_variation_lines"
    __table_args__ = (
        CheckConstraint("direction IN ('POSITIVE','NEGATIVE')", name="ck_variation_direction"),
        CheckConstraint("quantity > 0", name="ck_variation_quantity"),
        CheckConstraint("rate >= 0", name="ck_variation_rate"),
        CheckConstraint("line_value >= 0", name="ck_variation_value"),
        Index("ix_variation_lines_item", "loa_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    variation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("loa_variations.id", ondelete="CASCADE")
    )
    loa_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("loa_items.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("products.id"))
    description: Mapped[str] = mapped_column(String(2000))
    hsn_code_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("hsn_codes.id"))
    unit_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("units_of_measure.id"))
    direction: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    line_value: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    remarks: Mapped[str | None] = mapped_column(String(1000))

    variation: Mapped[LoaVariation] = relationship(back_populates="lines")
    loa_item: Mapped[LoaItem | None] = relationship(back_populates="variation_lines")

from datetime import datetime, timezone

from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _utc_now():
    return datetime.now(timezone.utc)


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    vendor_code: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str]
    normalized_name: Mapped[str]
    aliases: Mapped[list[str]] = mapped_column(JSON)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)

    vendor_id: Mapped[int] = mapped_column(
        ForeignKey("vendors.id")
    )

    po_number: Mapped[str] = mapped_column(unique=True)
    currency: Mapped[str]
    total_cents: Mapped[int]


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_lines"

    __table_args__ = (
        UniqueConstraint(
            "purchase_order_id",
            "item_code",
            name="uq_po_item_code",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    purchase_order_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_orders.id")
    )

    item_code: Mapped[str]
    description: Mapped[str]
    quantity: Mapped[int]
    unit_price_cents: Mapped[int]
    line_total_cents: Mapped[int]


class InvoiceProcessingResult(Base):
    __tablename__ = "invoice_processing_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    vendor_id: Mapped[int | None] = mapped_column(
        ForeignKey("vendors.id"),
        nullable=True,
    )
    purchase_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("purchase_orders.id"),
        nullable=True,
    )
    status: Mapped[str]
    issues: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)


class InvoiceSource(Base):
    __tablename__ = "invoice_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_type: Mapped[str] = mapped_column(default="json_file")
    source_reference: Mapped[str]
    content_hash: Mapped[str] = mapped_column(unique=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str]
    processing_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice_processing_results.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        default=_utc_now,
        onupdate=_utc_now,
    )

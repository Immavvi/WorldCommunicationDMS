from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.core.errors import AppError
from app.models.procurement import PurchaseOrderLine
from app.models.receiving import MaterialReceipt, MaterialReceiptLine
from app.repositories.procurement_repository import ProcurementRepository
from app.repositories.receiving_repository import ReceivingRepository
from app.schemas.receiving import PoReceiptPositionLine, ReceiptCreate, ReceiptUpdate

COUNTED_RECEIPT_STATUSES = frozenset({"VERIFIED"})
RECEIVABLE_PO_STATUSES = frozenset({"APPROVED", "ISSUED", "PARTIALLY_FULFILLED", "FULFILLED"})


class ReceivingService:
    def __init__(
        self, repository: ReceivingRepository, procurement_repository: ProcurementRepository
    ) -> None:
        self.repository = repository
        self.procurement_repository = procurement_repository

    async def po_position(self, po_id: UUID):
        po = await self.repository.get_po(po_id)
        if po is None:
            raise AppError(404, "purchase_order_not_found", "Purchase order does not exist.")
        return [await self._position_line(line) for line in po.lines]

    async def create_receipt(self, payload: ReceiptCreate, actor_id: UUID):
        po = await self.repository.get_po(payload.purchase_order_id)
        if po is None:
            raise AppError(404, "purchase_order_not_found", "Purchase order does not exist.")
        if po.status not in RECEIVABLE_PO_STATUSES:
            raise AppError(
                409, "purchase_order_not_receivable", "The PO is not approved for receiving."
            )
        po_lines = {line.id: line for line in po.lines}
        lines = []
        for item in payload.lines:
            po_line = po_lines.get(item.purchase_order_line_id)
            if po_line is None:
                raise AppError(
                    422, "invalid_po_line", "Receipt line does not belong to the selected PO."
                )
            previous = Decimal(await self.repository.accepted_quantity(po_line.id))
            pending = po_line.ordered_quantity - previous
            if item.quantity_accepted > pending:
                raise AppError(
                    422,
                    "accepted_quantity_exceeded",
                    "Accepted quantity exceeds the PO pending quantity.",
                )
            if item.quantity_short > pending:
                raise AppError(
                    422, "invalid_short_quantity", "Short quantity exceeds the PO pending quantity."
                )
            excess = max(item.quantity_received - pending, Decimal("0"))
            lines.append(
                MaterialReceiptLine(
                    ordered_quantity_snapshot=po_line.ordered_quantity,
                    previously_accepted_snapshot=previous,
                    quantity_excess=excess,
                    product_id=po_line.product_id,
                    description_snapshot=po_line.description,
                    unit_snapshot=po_line.unit_snapshot,
                    **item.model_dump(),
                )
            )
        receipt = MaterialReceipt(
            receipt_number=await self.procurement_repository.next_number("MATERIAL_RECEIPT"),
            vendor_party_id=po.vendor_party_id,
            project_id=po.project_id,
            loa_id=po.loa_id,
            received_by_user_id=actor_id,
            po_number_snapshot=po.po_number,
            vendor_snapshot=po.vendor_snapshot,
            lines=lines,
            **payload.model_dump(exclude={"lines"}),
        )
        await self.repository.save(receipt)
        self.repository.audit(
            actor_id,
            "assign_number",
            "material_receipt",
            receipt.id,
            new={"receipt_number": receipt.receipt_number},
        )
        self.repository.audit(
            actor_id,
            "create",
            "material_receipt",
            receipt.id,
            new={"po_number": receipt.po_number_snapshot},
        )
        for line in receipt.lines:
            self._audit_line(actor_id, line, "create")
        return await self.repository.get_receipt(receipt.id)

    async def update_receipt(self, receipt_id: UUID, payload: ReceiptUpdate, actor_id: UUID):
        receipt = await self._receipt(receipt_id)
        if receipt.status != "DRAFT":
            raise AppError(409, "receipt_immutable", "Only draft receipts can be edited.")
        values = payload.model_dump(exclude_unset=True)
        old = {key: getattr(receipt, key) for key in values}
        for key, value in values.items():
            setattr(receipt, key, value)
        await self.repository.save(receipt)
        self.repository.audit(actor_id, "update", "material_receipt", receipt.id, old, values)
        return await self.repository.get_receipt(receipt.id)

    async def update_line(self, receipt_id: UUID, line_id: UUID, payload, actor_id: UUID):
        receipt = await self._receipt(receipt_id)
        if receipt.status != "DRAFT":
            raise AppError(409, "receipt_immutable", "Only draft receipt lines can be edited.")
        line = next((candidate for candidate in receipt.lines if candidate.id == line_id), None)
        if line is None:
            raise AppError(404, "receipt_line_not_found", "Receipt line does not exist.")
        po = await self.repository.get_po(receipt.purchase_order_id)
        po_line = next(
            candidate for candidate in po.lines if candidate.id == line.purchase_order_line_id
        )
        previous = Decimal(await self.repository.accepted_quantity(po_line.id))
        pending = po_line.ordered_quantity - previous
        if payload.quantity_accepted > pending:
            raise AppError(
                422,
                "accepted_quantity_exceeded",
                "Accepted quantity exceeds the PO pending quantity.",
            )
        if payload.quantity_short > pending:
            raise AppError(
                422, "invalid_short_quantity", "Short quantity exceeds the PO pending quantity."
            )
        old = self._line_values(line)
        for key, value in payload.model_dump(exclude={"purchase_order_line_id"}).items():
            setattr(line, key, value)
        line.previously_accepted_snapshot = previous
        line.quantity_excess = max(payload.quantity_received - pending, Decimal("0"))
        await self.repository.save(line)
        self._audit_line(actor_id, line, "update", old)
        return await self.repository.get_receipt(receipt.id)

    async def transition(
        self, receipt_id: UUID, action: str, reason: str, actor_id: UUID, is_super_admin: bool
    ):
        receipt = await self._receipt(receipt_id)
        transitions = {
            ("DRAFT", "RECEIVE"): "RECEIVED",
            ("RECEIVED", "VERIFY"): "VERIFIED",
            ("DRAFT", "CANCEL"): "CANCELLED",
            ("RECEIVED", "CANCEL"): "CANCELLED",
            ("VERIFIED", "CANCEL"): "CANCELLED",
        }
        new_status = transitions.get((receipt.status, action))
        if new_status is None:
            raise AppError(409, "invalid_receipt_transition", "Receipt action is not allowed.")
        if action in {"VERIFY", "CANCEL"} and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "VERIFY":
            await self._validate_verification(receipt)
            receipt.verified_by_user_id = actor_id
            receipt.verified_at = datetime.now(UTC)
        old = receipt.status
        receipt.status = new_status
        await self.repository.save(receipt)
        self.repository.audit(
            actor_id,
            action.lower(),
            "material_receipt",
            receipt.id,
            {"status": old},
            {"status": new_status},
            reason,
        )
        if action in {"VERIFY", "CANCEL"}:
            await self._update_po_fulfillment(receipt.purchase_order_id, actor_id, receipt.id)
        return await self.repository.get_receipt(receipt.id)

    async def _validate_verification(self, receipt):
        await self.repository.lock_po_lines([line.purchase_order_line_id for line in receipt.lines])
        po = await self.repository.get_po(receipt.purchase_order_id)
        ordered = {line.id: line.ordered_quantity for line in po.lines}
        for line in receipt.lines:
            previous = Decimal(
                await self.repository.accepted_quantity(
                    line.purchase_order_line_id, exclude_receipt_id=receipt.id
                )
            )
            if previous + line.quantity_accepted > ordered[line.purchase_order_line_id]:
                raise AppError(
                    422,
                    "accepted_quantity_exceeded",
                    "Verified accepted quantity would exceed the PO quantity.",
                )

    async def _update_po_fulfillment(self, po_id: UUID, actor_id: UUID, receipt_id: UUID):
        po = await self.repository.get_po(po_id, lock=True)
        accepted = [Decimal(await self.repository.accepted_quantity(line.id)) for line in po.lines]
        total_accepted = sum(accepted, Decimal("0"))
        if total_accepted == 0:
            new_status = "ISSUED" if po.issued_at else "APPROVED"
        elif all(
            value >= line.ordered_quantity for value, line in zip(accepted, po.lines, strict=True)
        ):
            new_status = "FULFILLED"
        else:
            new_status = "PARTIALLY_FULFILLED"
        if po.status != new_status:
            old = po.status
            po.status = new_status
            await self.repository.save(po)
            self.repository.audit(
                actor_id,
                "auto_fulfillment",
                "purchase_order",
                po.id,
                {"status": old},
                {"status": new_status, "receipt_id": str(receipt_id)},
                "Derived from verified material receipts",
            )

    async def _position_line(self, line: PurchaseOrderLine):
        accepted = Decimal(await self.repository.accepted_quantity(line.id))
        return PoReceiptPositionLine(
            purchase_order_line_id=line.id,
            line_number=line.line_number,
            description=line.description,
            unit=line.unit_snapshot,
            ordered_quantity=line.ordered_quantity,
            accepted_to_date=accepted,
            pending_quantity=line.ordered_quantity - accepted,
        )

    async def _receipt(self, receipt_id):
        receipt = await self.repository.get_receipt(receipt_id)
        if receipt is None:
            raise AppError(404, "receipt_not_found", "Material receipt does not exist.")
        return receipt

    def _audit_line(self, actor_id, line, action, old=None):
        self.repository.audit(
            actor_id, action, "material_receipt_line", line.id, old, self._line_values(line)
        )

    @staticmethod
    def _line_values(line):
        return {
            "received": str(line.quantity_received),
            "accepted": str(line.quantity_accepted),
            "short": str(line.quantity_short),
            "damaged": str(line.quantity_damaged),
            "rejected": str(line.quantity_rejected),
            "excess": str(line.quantity_excess),
        }

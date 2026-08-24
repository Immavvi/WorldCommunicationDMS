from datetime import UTC, date, datetime
from decimal import Decimal

from app.core.errors import AppError
from app.models.master_data import BankAccount, Organization, Party
from app.models.payments import CustomerPayment, PaymentAllocation
from app.repositories.payment_repository import PaymentRepository
from app.repositories.procurement_repository import ProcurementRepository

MONEY = Decimal("0.01")
ELECTRONIC_MODES = {"BANK_TRANSFER", "NEFT", "RTGS", "IMPS", "UPI", "CHEQUE"}


def money(value) -> Decimal:
    return Decimal(value).quantize(MONEY)


def snapshot(record, fields):
    return {field: getattr(record, field) for field in fields}


class PaymentService:
    def __init__(self, repository: PaymentRepository, numbering: ProcurementRepository):
        self.repository = repository
        self.numbering = numbering

    async def create(self, payload, actor_id):
        customer = await self._master(Party, payload.customer_party_id, "customer")
        if not customer.is_active or not any(role.role == "CUSTOMER" for role in customer.roles):
            raise AppError(422, "invalid_customer", "Selected party is not an active customer.")
        organization = await self._master(Organization, payload.organization_id, "organization")
        bank = await self._bank(payload.bank_account_id, organization.id)
        payment = CustomerPayment(
            receipt_number=await self.numbering.next_number("CUSTOMER_RECEIPT"),
            customer_snapshot=snapshot(
                customer, ("code", "legal_name", "trade_name", "pan", "email", "phone")
            ),
            organization_snapshot=snapshot(
                organization, ("code", "legal_name", "trade_name", "pan")
            ),
            bank_snapshot=self._bank_snapshot(bank),
            created_by_user_id=actor_id,
            **payload.model_dump(),
        )
        await self.repository.save(payment)
        self.repository.audit(
            actor_id,
            "assign_number",
            "customer_payment",
            payment.id,
            new={"receipt_number": payment.receipt_number},
        )
        self.repository.audit(
            actor_id,
            "create",
            "customer_payment",
            payment.id,
            new={"amount_received": str(payment.amount_received)},
        )
        return await self.response(payment.id)

    async def update(self, payment_id, payload, actor_id):
        payment = await self._payment(payment_id, lock=True)
        if payment.status != "DRAFT":
            raise AppError(409, "payment_immutable", "Only draft payments can be edited.")
        values = payload.model_dump(exclude_unset=True)
        if "bank_account_id" in values:
            bank = await self._bank(values["bank_account_id"], payment.organization_id)
            payment.bank_snapshot = self._bank_snapshot(bank)
        mode = values.get("payment_mode", payment.payment_mode)
        reference = values.get("transaction_reference", payment.transaction_reference)
        if mode in ELECTRONIC_MODES and not reference:
            raise AppError(422, "payment_reference_required", "Transaction reference is required.")
        allocated = self._draft_allocated(payment)
        if values.get("amount_received") is not None and values["amount_received"] < allocated:
            raise AppError(
                409,
                "payment_amount_below_allocations",
                "Payment amount cannot be below allocated amount.",
            )
        old = {
            key: str(getattr(payment, key)) if getattr(payment, key) is not None else None
            for key in values
        }
        for key, value in values.items():
            setattr(payment, key, value)
        await self.repository.save(payment)
        self.repository.audit(
            actor_id,
            "update",
            "customer_payment",
            payment.id,
            old,
            {key: str(value) if value is not None else None for key, value in values.items()},
        )
        return await self.response(payment.id)

    async def allocate(self, payment_id, payload, actor_id):
        payment = await self._payment(payment_id, lock=True)
        if payment.status != "DRAFT":
            raise AppError(409, "payment_immutable", "Allocations can be prepared only in draft.")
        invoice = await self.repository.invoice(payload.tax_invoice_id, lock=True)
        if not invoice or invoice.status != "ISSUED":
            raise AppError(
                422, "invoice_not_receivable", "Only issued Tax Invoices are receivable."
            )
        if invoice.customer_party_id != payment.customer_party_id:
            raise AppError(
                422, "cross_customer_allocation", "Payment and invoice customers differ."
            )
        if invoice.organization_id != payment.organization_id:
            raise AppError(
                422, "cross_organization_allocation", "Payment and invoice organizations differ."
            )
        existing = next(
            (item for item in payment.allocations if item.tax_invoice_id == invoice.id), None
        )
        other_payment_allocated = self._draft_allocated(payment) - (
            existing.allocated_amount if existing else Decimal("0")
        )
        if other_payment_allocated + payload.allocated_amount > payment.amount_received:
            raise AppError(409, "payment_overallocated", "Allocation exceeds payment balance.")
        confirmed = money(await self.repository.confirmed_invoice_allocated(invoice.id))
        if confirmed + payload.allocated_amount > invoice.grand_total:
            raise AppError(409, "invoice_overallocated", "Allocation exceeds invoice outstanding.")
        if existing:
            old = str(existing.allocated_amount)
            existing.allocated_amount = payload.allocated_amount
            existing.allocation_date = payload.allocation_date
            existing.remarks = payload.remarks
            allocation = existing
            action = "update_allocation"
        else:
            allocation = PaymentAllocation(
                payment_id=payment.id,
                actor_user_id=actor_id,
                invoice_number_snapshot=invoice.invoice_number,
                project_snapshot=invoice.project_name_snapshot,
                loa_snapshot=invoice.loa_number_snapshot,
                **payload.model_dump(),
            )
            await self.repository.save(allocation)
            old = None
            action = "create_allocation"
        self.repository.audit(
            actor_id,
            action,
            "payment_allocation",
            allocation.id,
            {"allocated_amount": old} if old else None,
            {
                "allocated_amount": str(allocation.allocated_amount),
                "invoice_id": str(invoice.id),
            },
        )
        return await self.response(payment.id)

    async def remove_allocation(self, payment_id, allocation_id, actor_id):
        payment = await self._payment(payment_id, lock=True)
        if payment.status != "DRAFT":
            raise AppError(409, "payment_immutable", "Confirmed allocations cannot be removed.")
        allocation = next((item for item in payment.allocations if item.id == allocation_id), None)
        if not allocation:
            raise AppError(404, "allocation_not_found", "Allocation does not exist.")
        self.repository.audit(
            actor_id,
            "remove_allocation",
            "payment_allocation",
            allocation.id,
            {"allocated_amount": str(allocation.allocated_amount)},
            None,
        )
        await self.repository.delete_draft_allocation(allocation)
        return await self.response(payment.id)

    async def action(self, payment_id, payload, actor_id, is_super_admin):
        payment = await self._payment(payment_id, lock=True)
        if not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        now = datetime.now(UTC)
        if payload.action == "CONFIRM" and payment.status == "DRAFT":
            for allocation in payment.allocations:
                invoice = await self.repository.invoice(allocation.tax_invoice_id, lock=True)
                if not invoice or invoice.status != "ISSUED":
                    raise AppError(
                        409, "invoice_not_receivable", "Allocated invoice is no longer receivable."
                    )
                confirmed = money(
                    await self.repository.confirmed_invoice_allocated(
                        invoice.id, exclude_payment_id=payment.id
                    )
                )
                if confirmed + allocation.allocated_amount > invoice.grand_total:
                    raise AppError(
                        409, "invoice_overallocated", "Confirmation would over-settle an invoice."
                    )
            if self._draft_allocated(payment) > payment.amount_received:
                raise AppError(409, "payment_overallocated", "Payment is overallocated.")
            target = "CONFIRMED"
            payment.confirmed_by_user_id = actor_id
            payment.confirmed_at = now
        elif payload.action == "CANCEL" and payment.status == "DRAFT":
            target = "CANCELLED"
        elif payload.action == "REVERSE" and payment.status == "CONFIRMED":
            target = "REVERSED"
            payment.reversed_by_user_id = actor_id
            payment.reversed_at = now
            payment.reversal_reason = payload.reason
        else:
            raise AppError(409, "invalid_payment_transition", "Payment action is not allowed.")
        old = payment.status
        payment.status = target
        await self.repository.save(payment)
        self.repository.audit(
            actor_id,
            payload.action.lower(),
            "customer_payment",
            payment.id,
            {"status": old},
            {"status": target},
            payload.reason,
        )
        return await self.response(payment.id)

    async def receivables(self, *, payment_status=None, overdue=None, **filters):
        invoices = await self.repository.receivable_invoices(**filters)
        positions = [await self._position(invoice) for invoice in invoices]
        if payment_status:
            positions = [row for row in positions if row["payment_status"] == payment_status]
        if overdue is not None:
            positions = [row for row in positions if (row["days_overdue"] > 0) is overdue]
        return positions

    async def eligible(self, payment_id):
        payment = await self._payment(payment_id)
        invoices = await self.repository.receivable_invoices(customer_id=payment.customer_party_id)
        result = []
        for invoice in invoices:
            if invoice.organization_id != payment.organization_id:
                continue
            position = await self._position(invoice)
            if position["outstanding_amount"] > 0:
                result.append(
                    {
                        "tax_invoice_id": invoice.id,
                        "invoice_number": invoice.invoice_number,
                        "invoice_date": invoice.invoice_date,
                        "due_date": invoice.due_date,
                        "invoice_total": invoice.grand_total,
                        "received_amount": position["received_amount"],
                        "outstanding_amount": position["outstanding_amount"],
                        "project_name": invoice.project_name_snapshot,
                        "loa_number": invoice.loa_number_snapshot,
                    }
                )
        return result

    async def invoice_history(self, invoice_id):
        return [
            {
                "payment_id": payment.id,
                "receipt_number": payment.receipt_number,
                "receipt_date": payment.receipt_date,
                "payment_status": payment.status,
                "allocated_amount": allocation.allocated_amount,
                "allocation_date": allocation.allocation_date,
                "remarks": allocation.remarks,
            }
            for allocation, payment in await self.repository.invoice_payment_history(invoice_id)
        ]

    async def response(self, payment_id):
        payment = await self._payment(payment_id)
        allocated = self._draft_allocated(payment)
        data = {
            column.key: getattr(payment, column.key) for column in payment.__mapper__.column_attrs
        }
        data["allocations"] = payment.allocations
        data["allocated_amount"] = money(allocated)
        data["unallocated_amount"] = money(payment.amount_received - allocated)
        return data

    async def _position(self, invoice):
        received = money(await self.repository.confirmed_invoice_allocated(invoice.id))
        outstanding = money(invoice.grand_total - received)
        today = date.today()
        overdue_days = max((today - invoice.due_date).days, 0) if invoice.due_date else 0
        overdue = outstanding > 0 and overdue_days > 0
        if outstanding == 0:
            status = "PAID"
        elif received > 0:
            status = "PARTIALLY_PAID_OVERDUE" if overdue else "PARTIALLY_PAID"
        else:
            status = "OVERDUE" if overdue else "UNPAID"
        return {
            "tax_invoice_id": invoice.id,
            "invoice_number": invoice.invoice_number,
            "invoice_date": invoice.invoice_date,
            "customer_party_id": invoice.customer_party_id,
            "customer_name": invoice.customer_snapshot.get("trade_name")
            or invoice.customer_snapshot.get("legal_name"),
            "project_id": invoice.project_id,
            "project_name": invoice.project_name_snapshot,
            "loa_id": invoice.loa_id,
            "loa_number": invoice.loa_number_snapshot,
            "railway_division_id": invoice.railway_division_id,
            "due_date": invoice.due_date,
            "invoice_total": money(invoice.grand_total),
            "received_amount": received,
            "outstanding_amount": outstanding,
            "payment_status": status,
            "days_overdue": overdue_days if overdue else 0,
        }

    async def _payment(self, payment_id, *, lock=False):
        payment = await self.repository.get(payment_id, lock=lock)
        if not payment:
            raise AppError(404, "payment_not_found", "Customer payment does not exist.")
        return payment

    async def _master(self, model, record_id, name):
        record = await self.repository.master(model, record_id)
        if not record:
            raise AppError(422, f"invalid_{name}", f"Selected {name} does not exist.")
        return record

    async def _bank(self, bank_id, organization_id):
        if not bank_id:
            return None
        bank = await self._master(BankAccount, bank_id, "bank_account")
        if bank.organization_id != organization_id or not bank.is_active:
            raise AppError(
                422, "invalid_bank_account", "Bank must be active and belong to the organization."
            )
        return bank

    @staticmethod
    def _bank_snapshot(bank):
        return (
            snapshot(bank, ("account_name", "bank_name", "branch_name", "account_number", "ifsc"))
            if bank
            else None
        )

    @staticmethod
    def _draft_allocated(payment):
        return sum((item.allocated_amount for item in payment.allocations), Decimal("0"))

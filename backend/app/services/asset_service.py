import calendar
from datetime import UTC, date, datetime
from decimal import Decimal

from app.core.errors import AppError
from app.models.assets import Asset, AssetLifecycleEvent, ChallanAssetAssignment
from app.models.dispatch import SupplyChallan
from app.models.master_data import Product, RailwayDivision, RailwayLocation
from app.repositories.asset_repository import AssetRepository
from app.repositories.procurement_repository import ProcurementRepository

TRANSITIONS = {
    ("REGISTERED", "MAKE_AVAILABLE"): "AVAILABLE",
    ("AVAILABLE", "ALLOCATE"): "ALLOCATED",
    ("DISPATCHED", "MARK_DELIVERED"): "DELIVERED",
    ("DELIVERED", "MARK_DELIVERED"): "DELIVERED",
    ("AVAILABLE", "SEND_FOR_REPAIR"): "UNDER_REPAIR",
    ("ALLOCATED", "SEND_FOR_REPAIR"): "UNDER_REPAIR",
    ("DELIVERED", "SEND_FOR_REPAIR"): "UNDER_REPAIR",
    ("INSTALLED", "SEND_FOR_REPAIR"): "UNDER_REPAIR",
    ("IN_SERVICE", "SEND_FOR_REPAIR"): "UNDER_REPAIR",
    ("UNDER_REPAIR", "RETURN_FROM_REPAIR"): "RETURNED",
    ("RETURNED", "MAKE_AVAILABLE"): "AVAILABLE",
}
PROTECTED_ACTIONS = {"RETIRE", "DISPOSE", "CANCEL"}


def normalize_serial(value: str) -> str:
    return value.strip().casefold()


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


class AssetService:
    def __init__(self, repository: AssetRepository, numbering: ProcurementRepository):
        self.repository = repository
        self.numbering = numbering

    async def positions(self):
        result = []
        for line, receipt, product in await self.repository.eligible_receipt_lines():
            accepted = self._whole_quantity(line.quantity_accepted)
            registered = int(await self.repository.registered_count(line.id) or 0)
            result.append(
                {
                    "material_receipt_line_id": line.id,
                    "receipt_number": receipt.receipt_number,
                    "product_id": product.id,
                    "product_snapshot": line.description_snapshot,
                    "tracking_class": product.tracking_class,
                    "accepted_quantity": accepted,
                    "already_registered": registered,
                    "remaining_quantity": accepted - registered,
                }
            )
        return result

    async def register(self, payload, actor_id):
        context = await self.repository.receipt_context(payload.material_receipt_line_id, lock=True)
        if not context:
            raise AppError(404, "receipt_line_not_found", "Material receipt line does not exist.")
        line, receipt, po_line, po = context
        if receipt.status != "VERIFIED":
            raise AppError(
                409, "receipt_not_verified", "Only verified accepted material is eligible."
            )
        if not line.product_id:
            raise AppError(422, "product_required", "Receipt line has no Product reference.")
        product = await self.repository.master(Product, line.product_id)
        if product.tracking_class != "SERIALIZED":
            raise AppError(
                422,
                "product_not_serialized",
                "Only SERIALIZED Products create individual Asset records.",
            )
        accepted = self._whole_quantity(line.quantity_accepted)
        registered = int(await self.repository.registered_count(line.id) or 0)
        if registered + len(payload.assets) > accepted:
            raise AppError(
                409,
                "asset_registration_quantity_exceeded",
                "Asset registration exceeds the remaining accepted receipt quantity.",
            )
        normalized = [normalize_serial(item.manufacturer_serial_number) for item in payload.assets]
        if len(set(normalized)) != len(normalized):
            raise AppError(
                409, "duplicate_serial", "Duplicate serial number in registration batch."
            )
        for serial in normalized:
            if await self.repository.serial_exists(serial):
                raise AppError(409, "duplicate_serial", "Manufacturer serial already exists.")
        model, oem = await self.repository.product_identity(product)
        project, loa = await self.repository.source_names(receipt.project_id, receipt.loa_id)
        records = []
        for item, serial in zip(payload.assets, normalized, strict=True):
            asset = Asset(
                asset_number=await self.numbering.next_number("ASSET"),
                manufacturer_serial_number=item.manufacturer_serial_number.strip(),
                normalized_serial=serial,
                internal_tag=item.internal_tag,
                product_id=product.id,
                product_snapshot=line.description_snapshot,
                oem_party_id=oem.id if oem else None,
                oem_snapshot=(oem.trade_name or oem.legal_name) if oem else po_line.oem_snapshot,
                product_model_id=model.id if model else po_line.product_model_id,
                model_snapshot=po_line.model_snapshot,
                vendor_party_id=receipt.vendor_party_id,
                purchase_order_id=receipt.purchase_order_id,
                purchase_order_line_id=po_line.id,
                material_receipt_id=receipt.id,
                material_receipt_line_id=line.id,
                receipt_date_snapshot=receipt.receipt_date,
                source_project_id=receipt.project_id,
                source_loa_id=receipt.loa_id,
                project_snapshot=project.name,
                loa_snapshot=loa.loa_number if loa else None,
                created_by_user_id=actor_id,
            )
            asset.events.append(
                self._event(asset, "REGISTER", None, "REGISTERED", actor_id, "Receipt registration")
            )
            await self.repository.save(asset)
            self.repository.audit(
                actor_id,
                "assign_number",
                asset.id,
                new={"asset_number": asset.asset_number},
            )
            self.repository.audit(
                actor_id,
                "register",
                asset.id,
                new={"serial": asset.manufacturer_serial_number, "receipt_line_id": str(line.id)},
            )
            records.append(asset)
        return [await self.repository.get(asset.id) for asset in records]

    async def action(self, asset_id, payload, actor_id, is_super_admin):
        asset = await self._asset(asset_id, lock=True)
        action = payload.action
        if action in PROTECTED_ACTIONS and not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        if action == "MOVE":
            if asset.status in {"RETIRED", "DISPOSED", "LOST", "CANCELLED"}:
                raise AppError(409, "invalid_asset_transition", "Asset cannot be moved.")
            target = asset.status
        elif action == "MARK_DAMAGED":
            target = "DAMAGED"
        elif action == "MARK_LOST":
            target = "LOST"
        elif action == "RETIRE":
            target = "RETIRED"
        elif action == "DISPOSE" and asset.status == "RETIRED":
            target = "DISPOSED"
        elif action == "CANCEL" and asset.status == "REGISTERED":
            target = "CANCELLED"
        else:
            target = TRANSITIONS.get((asset.status, action))
        if target is None:
            raise AppError(
                409, "invalid_asset_transition", "Asset lifecycle action is not allowed."
            )
        await self._validate_location(payload)
        old_status = asset.status
        old_location = self._location(asset)
        self._apply_location(asset, payload)
        asset.status = target
        event = self._event(
            asset,
            action,
            old_status,
            target,
            actor_id,
            payload.reason,
            payload.remarks,
            old_location,
        )
        asset.events.append(event)
        await self.repository.save(asset)
        self.repository.audit(
            actor_id,
            action.lower(),
            asset.id,
            {"status": old_status, "location": old_location},
            {"status": target, "location": self._location(asset)},
            payload.reason,
        )
        return await self.repository.get(asset.id)

    async def install(self, asset_id, payload, actor_id):
        asset = await self._asset(asset_id, lock=True)
        if asset.status not in {"AVAILABLE", "ALLOCATED", "DELIVERED", "RETURNED"}:
            raise AppError(
                409, "invalid_asset_transition", "Asset cannot be installed from its current state."
            )
        await self._validate_location(payload)
        old_status, old_location = asset.status, self._location(asset)
        self._apply_location(asset, payload)
        asset.installation_date = payload.installation_date
        asset.status = "INSTALLED"
        asset.events.append(
            self._event(
                asset,
                "INSTALL",
                old_status,
                "INSTALLED",
                actor_id,
                payload.reason,
                payload.remarks,
                old_location,
            )
        )
        await self.repository.save(asset)
        self.repository.audit(
            actor_id,
            "install",
            asset.id,
            {"status": old_status},
            {"status": "INSTALLED"},
            payload.reason,
        )
        return await self.repository.get(asset.id)

    async def warranty(self, asset_id, payload, actor_id):
        asset = await self._asset(asset_id, lock=True)
        values = payload.model_dump(exclude={"reason"})
        expiry = values["warranty_expiry_date"]
        if values["warranty_start_date"] and values["warranty_duration_months"] is not None:
            derived = add_months(values["warranty_start_date"], values["warranty_duration_months"])
            if expiry and expiry != derived:
                raise AppError(
                    422,
                    "warranty_expiry_conflict",
                    "Explicit expiry conflicts with start and duration.",
                )
            values["warranty_expiry_date"] = derived
        old = {
            key: str(getattr(asset, key)) if getattr(asset, key) is not None else None
            for key in values
        }
        for key, value in values.items():
            setattr(asset, key, value)
        await self.repository.save(asset)
        self.repository.audit(
            actor_id,
            "update_warranty",
            asset.id,
            old,
            {key: str(value) if value is not None else None for key, value in values.items()},
            payload.reason,
        )
        return await self.repository.get(asset.id)

    async def replace(self, asset_id, payload, actor_id, is_super_admin):
        if not is_super_admin:
            raise AppError(403, "authorization_denied", "SUPER-ADMIN access is required.")
        old = await self._asset(asset_id, lock=True)
        replacement = await self._asset(payload.replacement_asset_id, lock=True)
        if old.id == replacement.id or old.product_id != replacement.product_id:
            raise AppError(
                422, "invalid_replacement", "Replacement must be a different compatible Asset."
            )
        if replacement.status not in {"REGISTERED", "AVAILABLE"}:
            raise AppError(409, "replacement_unavailable", "Replacement Asset is not available.")
        prior = old.status
        old.status = "REPLACED"
        old.replacement_asset_id = replacement.id
        old.events.append(self._event(old, "REPLACE", prior, "REPLACED", actor_id, payload.reason))
        await self.repository.save(old)
        self.repository.audit(
            actor_id,
            "replace",
            old.id,
            {"status": prior},
            {"status": "REPLACED", "replacement_asset_id": str(replacement.id)},
            payload.reason,
        )
        return await self.repository.get(old.id)

    async def assign_challan(self, line_id, payload, actor_id):
        line = await self.repository.challan_line(line_id, lock=True)
        if not line:
            raise AppError(404, "challan_line_not_found", "Supply Challan line does not exist.")
        assigned = int(await self.repository.assignment_count(line.id) or 0)
        if Decimal(assigned + len(payload.asset_ids)) > line.dispatched_quantity:
            raise AppError(
                409,
                "challan_asset_quantity_exceeded",
                "Assigned serialized Assets exceed Challan quantity.",
            )
        challan = await self.repository.master(SupplyChallan, line.supply_challan_id)
        if challan.status != "DISPATCHED":
            raise AppError(
                409,
                "challan_not_dispatched",
                "Serialized Assets can be linked only after the Challan is dispatched.",
            )
        results = []
        for asset_id in payload.asset_ids:
            asset = await self._asset(asset_id, lock=True)
            if asset.product_id != line.product_id:
                raise AppError(
                    422, "asset_product_mismatch", "Asset Product does not match the Challan line."
                )
            if asset.status not in {"AVAILABLE", "ALLOCATED"}:
                raise AppError(
                    409, "asset_not_dispatchable", "Asset is not available for dispatch."
                )
            old = asset.status
            asset.status = "DISPATCHED"
            assignment = ChallanAssetAssignment(
                supply_challan_line_id=line.id, asset_id=asset.id, assigned_by_user_id=actor_id
            )
            asset.events.append(
                self._event(
                    asset,
                    "DISPATCH",
                    old,
                    "DISPATCHED",
                    actor_id,
                    payload.reason,
                    supply_challan_id=challan.id,
                )
            )
            await self.repository.save(assignment)
            await self.repository.save(asset)
            self.repository.audit(
                actor_id,
                "dispatch_link",
                asset.id,
                {"status": old},
                {"status": "DISPATCHED", "challan_id": str(challan.id)},
                payload.reason,
            )
            results.append(await self.repository.get(asset.id))
        return results

    async def _asset(self, asset_id, *, lock=False):
        asset = await self.repository.get(asset_id, lock=lock)
        if not asset:
            raise AppError(404, "asset_not_found", "Asset does not exist.")
        return asset

    async def _validate_location(self, payload):
        if payload.railway_location_id:
            location = await self.repository.master(RailwayLocation, payload.railway_location_id)
            if not location or location.division_id != payload.railway_division_id:
                raise AppError(
                    422,
                    "invalid_railway_location",
                    "Railway location does not belong to the selected division.",
                )
        if payload.railway_division_id and payload.railway_zone_id:
            division = await self.repository.master(RailwayDivision, payload.railway_division_id)
            if not division or division.zone_id != payload.railway_zone_id:
                raise AppError(
                    422,
                    "invalid_railway_division",
                    "Railway division does not belong to the selected zone.",
                )

    @staticmethod
    def _apply_location(asset, payload):
        for target, source in (
            ("current_project_id", "project_id"),
            ("current_railway_zone_id", "railway_zone_id"),
            ("current_railway_division_id", "railway_division_id"),
            ("current_railway_location_id", "railway_location_id"),
            ("current_site", "site"),
            ("current_building", "building"),
            ("current_room", "room"),
            ("current_rack", "rack"),
            ("current_position", "position"),
        ):
            value = getattr(payload, source)
            if value is not None:
                setattr(asset, target, value)

    @staticmethod
    def _location(asset):
        values = [
            asset.current_site,
            asset.current_building,
            asset.current_room,
            asset.current_rack,
            asset.current_position,
        ]
        return " / ".join(value for value in values if value) or None

    def _event(
        self,
        asset,
        event_type,
        from_status,
        to_status,
        actor_id,
        reason,
        remarks=None,
        from_location=None,
        supply_challan_id=None,
    ):
        return AssetLifecycleEvent(
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            from_location_snapshot=from_location,
            to_location_snapshot=self._location(asset),
            project_id=asset.current_project_id,
            railway_zone_id=asset.current_railway_zone_id,
            railway_division_id=asset.current_railway_division_id,
            railway_location_id=asset.current_railway_location_id,
            supply_challan_id=supply_challan_id,
            event_at=datetime.now(UTC),
            actor_user_id=actor_id,
            reason=reason,
            remarks=remarks,
        )

    @staticmethod
    def _whole_quantity(value):
        quantity = Decimal(value)
        if quantity != quantity.to_integral_value():
            raise AppError(
                422,
                "serialized_quantity_not_whole",
                "Serialized accepted quantity must be a whole number.",
            )
        return int(quantity)

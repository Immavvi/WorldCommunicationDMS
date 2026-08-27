import re
from typing import Any
from uuid import UUID

from sqlalchemy import inspect

from app.core.errors import AppError
from app.models.master_data import (
    BankAccount,
    GstRegistration,
    HsnCode,
    Loa,
    OemProfile,
    Organization,
    OrganizationAddress,
    Party,
    PartyAddress,
    PartyRole,
    PaymentTerm,
    Product,
    ProductCategory,
    ProductModel,
    Project,
    RailwayAuthority,
    RailwayAuthorityAddress,
    RailwayDivision,
    RailwayLocation,
    RailwayZone,
    TaxRateComponent,
    TaxRateSet,
    TermsConditionSet,
    TermsConditionVersion,
    UnitOfMeasure,
)
from app.repositories.master_data_repository import MasterDataRepository
from app.schemas.master_data import MasterDataResponse, MasterDataWrite

RESOURCE_MODELS = {
    "organizations": Organization,
    "organization-addresses": OrganizationAddress,
    "parties": Party,
    "party-addresses": PartyAddress,
    "railway-zones": RailwayZone,
    "railway-divisions": RailwayDivision,
    "railway-locations": RailwayLocation,
    "product-categories": ProductCategory,
    "products": Product,
    "units": UnitOfMeasure,
    "hsn-codes": HsnCode,
    "payment-terms": PaymentTerm,
    "terms-condition-sets": TermsConditionSet,
    "projects": Project,
    "oem-profiles": OemProfile,
    "product-models": ProductModel,
    "railway-authorities": RailwayAuthority,
    "railway-authority-addresses": RailwayAuthorityAddress,
    "loas": Loa,
    "bank-accounts": BankAccount,
    "gst-registrations": GstRegistration,
    "tax-rate-sets": TaxRateSet,
}

RESOURCE_FIELDS = {
    "organizations": {"code", "legal_name", "trade_name", "pan", "email", "phone"},
    "organization-addresses": {
        "organization_id",
        "address_type",
        "label",
        "address_line_1",
        "address_line_2",
        "city",
        "district",
        "state",
        "state_code",
        "postal_code",
        "country",
        "contact_name",
        "phone",
        "email",
        "is_default",
    },
    "parties": {
        "code",
        "legal_name",
        "trade_name",
        "pan",
        "business_scope",
        "email",
        "phone",
        "roles",
    },
    "party-addresses": {
        "party_id",
        "address_type",
        "label",
        "address_line_1",
        "address_line_2",
        "city",
        "district",
        "state",
        "state_code",
        "postal_code",
        "country",
        "contact_name",
        "phone",
        "email",
        "is_default",
    },
    "railway-zones": {"code", "name", "aliases"},
    "railway-divisions": {"code", "name", "aliases", "zone_id", "customer_party_id"},
    "railway-locations": {"code", "name", "aliases", "division_id", "location_type"},
    "product-categories": {"code", "name", "description"},
    "products": {
        "code",
        "name",
        "description",
        "business_scope",
        "category_id",
        "product_model_id",
        "unit_id",
        "hsn_code_id",
        "default_tax_rate_set_id",
        "specifications",
        "tracking_class",
    },
    "units": {"code", "name", "symbol", "decimal_places"},
    "hsn-codes": {"code", "description"},
    "payment-terms": {"code", "name", "description", "due_days"},
    "terms-condition-sets": {"code", "name", "context"},
    "projects": {
        "code",
        "name",
        "customer_party_id",
        "business_scope",
        "railway_division_id",
        "start_date",
        "end_date",
        "status",
    },
    "oem-profiles": {"party_id", "manufacturer_code", "website", "notes"},
    "product-models": {"oem_profile_id", "model_number", "name", "description"},
    "railway-authorities": {
        "division_id",
        "location_id",
        "code",
        "name",
        "designation",
        "aliases",
        "email",
        "phone",
        "roles",
    },
    "railway-authority-addresses": {
        "authority_id",
        "label",
        "address_line_1",
        "address_line_2",
        "city",
        "district",
        "state",
        "state_code",
        "postal_code",
        "country",
        "contact_name",
        "phone",
        "email",
        "is_default",
    },
    "loas": {
        "project_id",
        "loa_number",
        "loa_date",
        "customer_reference",
        "description",
        "status",
    },
    "bank-accounts": {
        "organization_id",
        "account_name",
        "bank_name",
        "branch_name",
        "account_number",
        "account_type",
        "ifsc",
        "swift",
        "is_default",
    },
    "gst-registrations": {
        "organization_id",
        "party_id",
        "gstin",
        "registered_name",
        "state",
        "state_code",
        "effective_from",
        "effective_to",
        "is_default",
    },
    "tax-rate-sets": {"code", "name", "effective_from", "effective_to", "components"},
}

REQUIRED_FIELDS = {
    "organizations": {"code", "legal_name"},
    "organization-addresses": {
        "organization_id",
        "address_type",
        "label",
        "address_line_1",
        "city",
        "state",
        "postal_code",
    },
    "parties": {"code", "legal_name", "roles"},
    "party-addresses": {
        "party_id",
        "address_type",
        "label",
        "address_line_1",
        "city",
        "state",
        "postal_code",
    },
    "railway-zones": {"code", "name"},
    "railway-divisions": {"code", "name", "zone_id"},
    "railway-locations": {"code", "name", "division_id", "location_type"},
    "product-categories": {"code", "name"},
    "units": {"code", "name", "symbol"},
    "hsn-codes": {"code", "description"},
    "payment-terms": {"code", "name", "description"},
    "terms-condition-sets": {"code", "name", "context"},
    "projects": {"code", "name", "customer_party_id", "business_scope"},
    "oem-profiles": {"party_id"},
    "product-models": {"oem_profile_id", "model_number"},
    "railway-authorities": {"division_id", "code", "name", "roles"},
    "railway-authority-addresses": {
        "authority_id",
        "label",
        "address_line_1",
        "city",
        "state",
        "postal_code",
    },
    "loas": {"project_id", "loa_number", "loa_date"},
    "bank-accounts": {"organization_id", "account_name", "bank_name", "account_number", "ifsc"},
    "gst-registrations": {"gstin", "registered_name", "state", "state_code", "effective_from"},
    "tax-rate-sets": {"code", "name", "effective_from", "components"},
}

PARTY_ROLES = {"CUSTOMER", "VENDOR", "OEM"}
AUTHORITY_ROLES = {
    "ISSUING_AUTHORITY",
    "EXECUTION_AUTHORITY",
    "CONSIGNEE",
    "BILL_TO",
    "SHIP_TO",
}
LOCATION_TYPES = {"STATION", "STORE", "OFFICE", "DEPOT", "YARD", "LC_GATE", "BUILDING", "OTHER"}
TERMS_CONTEXTS = {
    "PURCHASE",
    "SALES_QUOTATION",
    "INVOICE",
    "DELIVERY_CHALLAN",
    "RAILWAY",
    "NON_RAILWAY",
    "GENERAL",
}


def normalized_master(value: str | None) -> str:
    return re.sub(r"\b(?:railway|rly|division|zone)\b|[^a-z0-9]", "", (value or "").lower())


class MasterDataService:
    def __init__(self, repository: MasterDataRepository) -> None:
        self.repository = repository

    def model_for(self, resource: str):
        model = RESOURCE_MODELS.get(resource)
        if model is None:
            raise AppError(404, "master_resource_not_found", "Unknown master-data resource.")
        return model

    async def create_terms_version(
        self, terms_set_id: UUID, content: str, effective_from, actor_id: UUID
    ) -> TermsConditionVersion:
        terms_set = await self.repository.get(TermsConditionSet, terms_set_id)
        if terms_set is None:
            raise AppError(404, "master_record_not_found", "Terms & Conditions set does not exist.")
        versions = await self.repository.list_terms_versions(terms_set_id)
        version = TermsConditionVersion(
            terms_set_id=terms_set_id,
            version=(versions[0].version + 1) if versions else 1,
            content=content,
            effective_from=effective_from,
            created_by_user_id=actor_id,
        )
        await self.repository.save(version)
        self.repository.audit(
            actor_user_id=actor_id,
            action="create_version",
            entity_type="terms-condition-sets",
            entity_id=terms_set_id,
            old_value=None,
            new_value={"version": version.version, "effective_from": str(effective_from)},
        )
        return version

    async def list(self, resource: str, offset: int, limit: int, active: bool | None):
        model = self.model_for(resource)
        records = await self.repository.list(model, offset=offset, limit=limit, active=active)
        total = await self.repository.count(model, active=active)
        return [self.serialize(resource, item) for item in records], total

    async def get(self, resource: str, record_id: UUID):
        record = await self.repository.get(self.model_for(resource), record_id)
        if record is None:
            raise AppError(404, "master_record_not_found", "Master record does not exist.")
        return record

    async def create(
        self, resource: str, payload: MasterDataWrite, actor_id: UUID
    ) -> MasterDataResponse:
        model = self.model_for(resource)
        values = self._values(resource, payload, creating=True)
        await self._validate_railway_hierarchy(resource, values)
        await self._validate_normalized_uniqueness(resource, values)
        roles = values.pop("roles", None)
        components = values.pop("components", None)
        if (
            "code" in values
            and resource not in {"railway-divisions", "railway-locations"}
            and await self.repository.find_by_code(model, values["code"])
        ):
            raise AppError(409, "master_code_exists", "A record with this code already exists.")
        record = model(**values)
        if resource == "parties":
            record.roles = [PartyRole(role=role) for role in roles]
        if resource == "railway-authorities":
            from app.models.master_data import RailwayAuthorityRole

            record.roles = [RailwayAuthorityRole(role=role) for role in roles]
        if resource == "tax-rate-sets":
            record.components = [
                TaxRateComponent(component=name, rate=rate) for name, rate in components.items()
            ]
        await self.repository.save(record)
        response = self.serialize(resource, record)
        self.repository.audit(
            actor_user_id=actor_id,
            action="create",
            entity_type=resource,
            entity_id=record.id,
            old_value=None,
            new_value=response.data,
        )
        return response

    async def update(
        self, resource: str, record_id: UUID, payload: MasterDataWrite, actor_id: UUID
    ) -> MasterDataResponse:
        record = await self.get(resource, record_id)
        old = self.serialize(resource, record).data
        values = self._values(resource, payload, creating=False)
        prospective = {
            "zone_id": values.get("zone_id", getattr(record, "zone_id", None)),
            "division_id": values.get("division_id", getattr(record, "division_id", None)),
            "location_id": values.get("location_id", getattr(record, "location_id", None)),
        }
        await self._validate_railway_hierarchy(resource, prospective)
        await self._validate_normalized_uniqueness(resource, {**old, **values}, record.id)
        roles = values.pop("roles", None)
        values.pop("components", None)
        for name, value in values.items():
            setattr(record, name, value)
        if resource == "parties" and roles is not None:
            record.roles = [PartyRole(role=role) for role in roles]
        if resource == "railway-authorities" and roles is not None:
            from app.models.master_data import RailwayAuthorityRole

            record.roles = [RailwayAuthorityRole(role=role) for role in roles]
        await self.repository.save(record)
        response = self.serialize(resource, record)
        self.repository.audit(
            actor_user_id=actor_id,
            action="update",
            entity_type=resource,
            entity_id=record.id,
            old_value=old,
            new_value=response.data,
        )
        return response

    async def set_active(
        self, resource: str, record_id: UUID, active: bool, actor_id: UUID
    ) -> MasterDataResponse:
        record = await self.get(resource, record_id)
        old = record.is_active
        record.is_active = active
        await self.repository.save(record)
        self.repository.audit(
            actor_user_id=actor_id,
            action="activate" if active else "deactivate",
            entity_type=resource,
            entity_id=record.id,
            old_value={"is_active": old},
            new_value={"is_active": active},
        )
        return self.serialize(resource, record)

    async def delete(self, resource: str, record_id: UUID, actor_id: UUID) -> None:
        railway_resources = {
            "railway-zones",
            "railway-divisions",
            "railway-locations",
            "railway-authorities",
        }
        if resource not in railway_resources:
            raise AppError(
                405,
                "master_delete_not_allowed",
                "Physical deletion is allowed only for Railway structured masters.",
            )
        record = await self.get(resource, record_id)
        references = await self.repository.find_external_references(record)
        if references:
            raise AppError(
                409,
                "master_record_in_use",
                "This Railway master is already in use. Deactivate it instead.",
            )
        old_value = self.serialize(resource, record).data
        await self.repository.delete(record)
        self.repository.audit(
            actor_user_id=actor_id,
            action="delete",
            entity_type=resource,
            entity_id=record.id,
            old_value=old_value,
            new_value=None,
        )
    async def set_primary_organization(
        self, organization_id: UUID, actor_id: UUID
    ) -> MasterDataResponse:
        organizations = await self.repository.lock_organizations()
        target = next((item for item in organizations if item.id == organization_id), None)
        if target is None:
            raise AppError(404, "master_record_not_found", "Organization does not exist.")
        previous_primary_ids = [str(item.id) for item in organizations if item.is_primary]
        for organization in organizations:
            organization.is_primary = organization.id == organization_id
        await self.repository.save(target)
        response = self.serialize("organizations", target)
        self.repository.audit(
            actor_user_id=actor_id,
            action="set_primary",
            entity_type="organizations",
            entity_id=target.id,
            old_value={"primary_organization_ids": previous_primary_ids},
            new_value={"primary_organization_id": str(target.id)},
        )
        return response

    def _values(self, resource: str, payload: MasterDataWrite, *, creating: bool) -> dict[str, Any]:
        supplied = payload.model_dump(exclude_unset=True)
        allowed = RESOURCE_FIELDS[resource]
        unexpected = set(supplied) - allowed
        if unexpected:
            raise AppError(
                422,
                "invalid_master_fields",
                "Fields are not valid for this resource.",
                sorted(unexpected),
            )
        if creating:
            missing = REQUIRED_FIELDS.get(resource, set()) - set(supplied)
            if missing:
                raise AppError(
                    422, "missing_master_fields", "Required fields are missing.", sorted(missing)
                )
        if resource == "parties" and "roles" in supplied:
            roles = set(supplied["roles"] or [])
            if not roles or not roles <= PARTY_ROLES:
                raise AppError(422, "invalid_party_roles", "One or more party roles are invalid.")
            supplied["roles"] = sorted(roles)
        if resource == "railway-authorities" and "roles" in supplied:
            roles = set(supplied["roles"] or [])
            if not roles or not roles <= AUTHORITY_ROLES:
                raise AppError(
                    422, "invalid_authority_roles", "One or more authority roles are invalid."
                )
            supplied["roles"] = sorted(roles)
        if resource == "railway-locations" and "location_type" in supplied:
            supplied["location_type"] = supplied["location_type"].upper()
            if supplied["location_type"] not in LOCATION_TYPES:
                raise AppError(
                    422, "invalid_location_type", "The Railway location type is invalid."
                )
        if resource == "tax-rate-sets" and "components" in supplied:
            components = supplied["components"] or {}
            if not components or not set(components) <= {"CGST", "SGST", "IGST"}:
                raise AppError(422, "invalid_tax_components", "Tax components are invalid.")
        if resource == "terms-condition-sets" and supplied.get("context") not in TERMS_CONTEXTS:
            raise AppError(422, "invalid_terms_context", "The terms context is invalid.")
        return supplied

    async def _validate_railway_hierarchy(self, resource: str, values: dict[str, Any]) -> None:
        if resource == "railway-divisions":
            zone = await self.repository.get(RailwayZone, values.get("zone_id"))
            if zone is None or not zone.is_active:
                raise AppError(422, "invalid_railway_zone", "Select an active Railway Zone.")
        if resource in {"railway-locations", "railway-authorities"}:
            division = await self.repository.get(RailwayDivision, values.get("division_id"))
            if division is None or not division.is_active:
                raise AppError(
                    422, "invalid_railway_division", "Select an active Railway Division."
                )
            location_id = values.get("location_id")
            if resource == "railway-authorities" and location_id:
                location = await self.repository.get(RailwayLocation, location_id)
                if location is None or location.division_id != division.id:
                    raise AppError(
                        422,
                        "railway_hierarchy_mismatch",
                        "The Railway Location does not belong to the selected Division.",
                    )

    async def _validate_normalized_uniqueness(
        self, resource: str, values: dict[str, Any], exclude_id: UUID | None = None
    ) -> None:
        railway_resources = {
            "railway-zones",
            "railway-divisions",
            "railway-locations",
            "railway-authorities",
        }
        if resource not in railway_resources:
            return
        records = await self.repository.list(
            self.model_for(resource), offset=0, limit=10000, active=True
        )
        proposed = {
            normalized_master(str(value))
            for value in [
                values.get("code"),
                values.get("name"),
                values.get("designation"),
                *(values.get("aliases") or []),
            ]
            if value
        }
        for record in records:
            if record.id == exclude_id:
                continue
            if resource == "railway-divisions" and record.zone_id != values.get("zone_id"):
                continue
            if (
                resource in {"railway-locations", "railway-authorities"}
                and record.division_id != values.get("division_id")
            ):
                continue
            existing = {
                normalized_master(str(value))
                for value in [
                    record.code,
                    record.name,
                    getattr(record, "designation", None),
                    *(record.aliases or []),
                ]
                if value
            }
            if proposed & existing:
                raise AppError(
                    409,
                    "normalized_master_exists",
                    "An active Railway master with the same normalized code, name, or alias "
                    "already exists in this hierarchy.",
                )

    @staticmethod
    def serialize(resource: str, record) -> MasterDataResponse:
        data = {
            column.key: getattr(record, column.key)
            for column in inspect(record.__class__).columns
            if column.key not in {"id", "is_active", "created_at", "updated_at"}
        }
        if resource == "parties":
            data["roles"] = [role.role for role in record.roles]
        if resource == "railway-authorities":
            data["roles"] = [role.role for role in record.roles]
        if resource == "railway-zones" and re.search(
            r"\bdivision\b", str(data.get("name", "")), re.IGNORECASE
        ):
            data["classification_warning"] = (
                "This Zone name appears to describe a Division. Review its classification; "
                "existing references will not be changed automatically."
            )
        if resource == "bank-accounts" and data.get("account_number"):
            data["account_number"] = f"****{data['account_number'][-4:]}"
        return MasterDataResponse(
            id=record.id,
            resource=resource,
            data=data,
            is_active=record.is_active,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

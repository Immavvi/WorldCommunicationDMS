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
    "railway-zones": {"code", "name"},
    "railway-divisions": {"code", "name", "zone_id"},
    "railway-locations": {"code", "name", "division_id", "location_type"},
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
AUTHORITY_ROLES = {"CONSIGNEE", "BILL_TO", "SHIP_TO"}
TERMS_CONTEXTS = {
    "PURCHASE",
    "SALES_QUOTATION",
    "INVOICE",
    "DELIVERY_CHALLAN",
    "RAILWAY",
    "NON_RAILWAY",
    "GENERAL",
}


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
        roles = values.pop("roles", None)
        components = values.pop("components", None)
        if "code" in values and await self.repository.find_by_code(model, values["code"]):
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
        roles = values.pop("roles", None)
        values.pop("components", None)
        for name, value in values.items():
            setattr(record, name, value)
        if resource == "parties" and roles is not None:
            record.roles = [PartyRole(role=role) for role in roles]
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
        if resource == "tax-rate-sets" and "components" in supplied:
            components = supplied["components"] or {}
            if not components or not set(components) <= {"CGST", "SGST", "IGST"}:
                raise AppError(422, "invalid_tax_components", "Tax components are invalid.")
        if resource == "terms-condition-sets" and supplied.get("context") not in TERMS_CONTEXTS:
            raise AppError(422, "invalid_terms_context", "The terms context is invalid.")
        return supplied

    @staticmethod
    def serialize(resource: str, record) -> MasterDataResponse:
        data = {
            column.key: getattr(record, column.key)
            for column in inspect(record.__class__).columns
            if column.key not in {"id", "is_active", "created_at", "updated_at"}
        }
        if resource == "parties":
            data["roles"] = [role.role for role in record.roles]
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

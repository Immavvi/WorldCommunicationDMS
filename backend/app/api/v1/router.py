from fastapi import APIRouter

from app.api.v1.administration import router as administration_router
from app.api.v1.assets import router as assets_router
from app.api.v1.attention import router as attention_router
from app.api.v1.auth import router as auth_router
from app.api.v1.billing import router as billing_router
from app.api.v1.contracts import router as contracts_router
from app.api.v1.dispatch import router as dispatch_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.invoicing import router as invoicing_router
from app.api.v1.master_data import router as master_data_router
from app.api.v1.payments import router as payments_router
from app.api.v1.procurement import router as procurement_router
from app.api.v1.quotations import router as quotations_router
from app.api.v1.receiving import router as receiving_router
from app.api.v1.reporting import router as reporting_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(administration_router)
api_router.include_router(reporting_router)
api_router.include_router(attention_router)
api_router.include_router(payments_router)
api_router.include_router(assets_router)
api_router.include_router(invoicing_router)
api_router.include_router(auth_router)
api_router.include_router(billing_router)
api_router.include_router(users_router)
api_router.include_router(master_data_router)
api_router.include_router(contracts_router)
api_router.include_router(procurement_router)
api_router.include_router(quotations_router)
api_router.include_router(receiving_router)
api_router.include_router(dispatch_router)
api_router.include_router(documents_router)

# World Communication Document Management System (WCDMS)

## Project

WCDMS is a production-oriented internal business and document management system for World Communication.

It is designed to centralize and manage Railway-related projects, contracts, procurement, logistics, assets, billing, financial records and business documents.

---

## Core Business Lifecycle

The central operational flow is:

Project
→ LOA
→ LOA Item
→ Procurement
→ Purchase Order
→ Dispatch
→ Challan
→ Railway Receiving
→ Asset
→ Billing
→ Tax Invoice
→ Payment

Supporting systems include:

- Users and permissions
- Workflow and approvals
- Document management
- Document versioning
- Audit history
- Alerts
- Reports
- Dashboards

---

## Major Modules

### Core

- Organization
- Parties
- Users
- Roles
- Permissions

### Railway

- Zones
- Divisions
- Locations
- Railway Authorities

### Products and Materials

- Product Categories
- OEMs
- Product Models
- Products
- Units of Measure
- Technical Specifications
- Explicit `SERIALIZED`, `QUANTITY_TRACKED`, and `NON_STOCK` tracking classification

### Project and Contract

- Projects
- LOA
- BOQ
- Variations

### Procurement

- Procurement Requirements
- Purchase Orders
- PO Lines

### Logistics

- Dispatch
- Challans
- Material Receiving
- Discrepancies

### Assets

- Asset Register
- Serial Number Tracking
- Asset Movement
- Installation
- Warranty
- Verified receipt-to-Asset quantity control
- Append-only lifecycle history
- Structured Railway and non-Railway placement
- Serialized Challan assignment

### Billing and Finance

- Billing
- Tax Invoices
- Payments
- Payment Allocation
- Receivables
- Project Financial Reporting

### Documents

- PO
- PI
- Challan
- Tax Invoice
- Railway Receiving / Acknowledgement
- LOA
- Variation
- Quotation
- Work Order
- Delivery Documents
- Warranty Documents
- Project Reports
- Other Supporting Documents

### Management

- Workflow
- Audit
- Alerts
- Reports
- Dashboards

---

## Initial Users

WCDMS initially uses two application roles.

### SUPER-ADMIN

Primary responsibility:

- Finance
- Money transactions
- Financial oversight
- Overall system authority
- User management
- System administration
- Configured approvals

### ADMIN

Primary responsibility:

- Projects
- LOA / BOQ operations
- Procurement
- Purchase Orders
- Proforma Invoices
- Dispatch
- Challans
- Receiving
- Assets
- Billing
- Tax Invoice preparation
- Documents
- Operational management

The authorization architecture is designed to support additional users and roles in the future.

---

## Technology

### Development

- macOS
- Apple Silicon
- VS Code
- Python 3.14
- Python virtual environment: `.venv`

### Application

- Backend: Python / FastAPI
- Database: PostgreSQL
- Frontend: Web application
- PDF generation: ReportLab
- Excel generation: openpyxl

### Production

- Ubuntu Server
- Secure private network / VPN

---

## Architecture

```text
Frontend
    |
    v
REST API
    |
    v
Authentication
    |
    v
Authorization
    |
    v
Business Services
    |
    v
Repository / Data Access
    |
    v
PostgreSQL
```

## Implemented application foundation

The current application includes authentication/RBAC, Master Data, Railway hierarchy,
Project/LOA contracts and variations, procurement and Purchase Orders, receiving,
Supply Challans, Proforma and Tax Invoices, quotations, approved PDF/Excel document
generation, historical document snapshots, and serialized Asset lifecycle management.

Serialized Assets originate from verified accepted receipt lines, retain PO/GRN and
Project/LOA traceability, use centralized `AST-` numbering, and preserve append-oriented
movement, installation, warranty, repair, replacement, retirement, and disposal history.
Quantity-tracked and non-stock Products continue to use their authoritative transaction
quantities without creating individual Asset records.

### Local requirements

- Python 3.14 and pip
- Node.js 22+ and npm
- PostgreSQL 16+ accessible locally or through the approved private network

### Backend

Create and activate a virtual environment, then install the backend and development dependencies:

```bash
cd backend
python3.14 -m venv ../.venv
source ../.venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Copy `.env.example` to `.env` at the repository root. Set `WCDMS_DATABASE_URL` to a PostgreSQL database and replace `WCDMS_JWT_SECRET_KEY` with a unique random secret of at least 32 characters. Do not commit `.env`.

Run database migrations and start the API:

```bash
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/api/v1/health`.

The initial SUPER-ADMIN must be created only after migrations have run, using the interactive command below. It reads the password from the terminal and refuses to run if any user already exists:

```bash
cd backend
python -m app.scripts.bootstrap_super_admin --email admin@example.com
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

For a local development frontend, set `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1` in an uncommitted `frontend/.env.local` file if the frontend is served separately from the API.

### Checks

```bash
cd backend
pytest
ruff check .
alembic check

cd ../frontend
npm run test
npm run lint
npm run build
```

## Current implementation status

- Foundation: implemented
- Authentication infrastructure: JWT, Argon2 password hashing, user/role/permission schema, and secure one-time SUPER-ADMIN bootstrap command
- Phase 03 master-data foundation: organizations, parties and roles, saved addresses,
  Railway hierarchy and authorities, products/OEMs/UOM/HSN, effective-dated GST configuration,
  bank and payment details, versioned Terms & Conditions, and Project/LOA references
- Phase 04 LOA and contract management: Project/LOA records, immutable original contract items,
  controlled positive and negative variations, and derived current-approved positions
- Phase 05 procurement and Purchase Orders: centralized numbering, requirements, contract-linked
  PO commitments, GST calculations, commercial snapshots, and controlled approval/issue workflow
- Phase 06 GRN/material receiving: partial receipts, discrepancy capture, verified accepted-quantity
  control, and derived Purchase Order fulfillment
- Downstream business transactions and document generation: not implemented
- PostgreSQL migrations: authentication and master-data foundations

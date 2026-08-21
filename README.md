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
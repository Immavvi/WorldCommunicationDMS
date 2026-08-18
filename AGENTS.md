# World Communication DMS — Codex Instructions

## Project Purpose

This is the production-oriented Document Management System for World Communication.

The system will manage:

- Purchase Orders (PO)
- Proforma Invoices (PI)
- Tax Invoices
- Customers
- Vendors and OEMs
- Products/items
- Attachments and business documents
- Document history
- Reports
- Users and permissions
- Backups

## Development Principles

1. This is a production system, not a throwaway prototype.
2. Do not change the agreed architecture without discussing the reason first.
3. Do not introduce a new framework, database, library, or major dependency unnecessarily.
4. Prefer simple, maintainable and well-structured code.
5. Never hard-code passwords, API keys, database credentials or other secrets.
6. Never commit `.env` files or business data to Git.
7. Do not expose the PostgreSQL database directly to users.
8. Important business calculations must be implemented centrally and tested.
9. Historical documents must remain reproducible even when master data changes.
10. Do not silently delete or overwrite business records.
11. Important destructive operations must require explicit confirmation and be auditable.
12. Every significant feature should include appropriate tests.
13. Before making large changes, inspect the existing project structure and understand the current implementation.
14. Keep changes focused on the requested task.
15. Do not modify unrelated files.

## Current Architecture

Development:
- macOS Apple Silicon
- VS Code
- Python 3.14
- Project virtual environment: `.venv`

Planned application:
- Backend: Python / FastAPI
- Database: PostgreSQL
- Frontend: Web application
- PDF generation: ReportLab
- Excel generation: openpyxl
- Production OS: Ubuntu Server
- Remote access: Secure private network/VPN

## Business Rules

- Customer, vendor/OEM and product data should be reusable.
- Users should not repeatedly enter the same master information.
- PO, PI and Tax Invoice relationships must be traceable.
- Document numbering must be centralized and protected against duplicates.
- GST calculations must be deterministic and tested.
- Amount in Words must be generated automatically.
- PDFs must follow the finalized World Communication document format.
- PDFs must be A4 and must not contain clipping, overlapping or cut-off content.
- Historical documents must preserve the information used when they were issued.

## Development Workflow

Before implementing a significant feature:

1. Understand the requirement.
2. Inspect relevant existing files.
3. Explain the proposed approach when clarification is needed.
4. Implement the smallest coherent change.
5. Run appropriate tests/checks.
6. Review the Git diff.
7. Report what changed and whether tests passed.

## Important

Do not invent missing business requirements.

If a requirement is unclear and the decision could affect:
- database structure,
- document format,
- financial calculations,
- numbering,
- permissions,
- security,
- or deployment,

stop and ask for clarification rather than guessing.
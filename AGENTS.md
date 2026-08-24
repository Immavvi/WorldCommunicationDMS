# World Communication DMS — Codex Instructions

## 1. Project Purpose

World Communication DMS (WCDMS) is a production-oriented internal business management and document management system for World Communication.

The system is designed to manage the complete lifecycle of Railway-related business operations, including:

- Organization and master data
- Railway zones, divisions and locations
- Projects
- LOA and BOQ
- Variations
- Products, OEMs and materials
- Procurement
- Purchase Orders (PO)
- Proforma Invoices (PI)
- Dispatch
- Challans
- Railway receiving / acknowledgements
- Assets and serial-number tracking
- Installation
- Billing
- Tax Invoices
- Payments
- Business documents and attachments
- Document versioning
- Workflow and approvals
- Audit history
- Alerts and notifications
- Reports and dashboards
- Users, roles and permissions
- Backup and deployment

The central operational relationship is:

Project
→ LOA
→ LOA Item
→ Procurement
→ Purchase Order
→ Dispatch
→ Challan
→ Receiving
→ Asset
→ Billing
→ Tax Invoice
→ Payment

Maintain traceability between related transactions wherever applicable.

---

## 2. Development Philosophy

This is a production system, not a throwaway prototype.

Follow these principles:

1. Do not change the agreed architecture without identifying the reason and obtaining approval.
2. Do not introduce a new framework, database, library or major dependency unnecessarily.
3. Prefer simple, maintainable and modular code.
4. Do not create duplicate models, tables, APIs, services or utilities.
5. Reuse existing project components where appropriate.
6. Never hard-code passwords, API keys, database credentials or other secrets.
7. Never commit `.env` files, secrets or business data to Git.
8. Do not expose PostgreSQL directly to users.
9. Important business calculations must be implemented centrally and tested.
10. Historical business records must remain traceable.
11. Historical documents must remain reproducible even when master data changes.
12. Do not silently delete or overwrite business records.
13. Important destructive operations require explicit confirmation and must be auditable.
14. Significant features must include appropriate tests.
15. Keep changes focused on the requested task.
16. Do not modify unrelated files.
17. Before making significant changes, inspect the existing repository and understand the current implementation.
18. Do not invent missing business requirements.
19. If an unresolved decision can affect database structure, document format, financial calculations, numbering, permissions, security or deployment, stop and request clarification.

---

## 3. Current Technology Architecture

### Development Environment

- macOS
- Apple Silicon
- VS Code
- Python 3.14
- Project virtual environment: `.venv`

### Planned Application

- Backend: Python / FastAPI
- Database: PostgreSQL
- Frontend: React + TypeScript
- Frontend Build Tool: Vite
- Frontend Styling: Tailwind CSS
- PDF generation: ReportLab
- Excel generation: openpyxl
- Production OS: Ubuntu Server
- Remote access: Secure private network / VPN

Do not replace the agreed technology stack without approval.

---

## 4. Application Architecture

Use a modular application architecture:

Frontend
→ API
→ Authentication
→ Authorization
→ Validation
→ Service Layer
→ Repository / Data Access
→ PostgreSQL

Business logic must not be unnecessarily placed directly inside frontend components or API route handlers.

---

## 5. Database Architecture

PostgreSQL is the authoritative transactional database.

The database is logically divided into:

- Core / Organization
- Railway
- Product and Material
- Project and Contract
- Procurement
- Logistics
- Assets
- Billing and Finance
- Documents
- Workflow
- Users and Security
- Audit
- Alerts

Use:

- Foreign keys
- Unique constraints
- Appropriate indexes
- Transactions
- Check constraints
- Exact monetary numeric types
- Created/updated timestamps
- Audit information

Do not use comma-separated IDs for relationships.

Do not use floating-point values for authoritative financial calculations.

---

## 6. Core Business Entities

Important entities include:

- Organizations
- Bank accounts
- Parties
- Railway zones
- Railway divisions
- Railway locations
- Railway authorities
- Product categories
- OEMs
- Product models
- Products
- Units of measure
- Projects
- LOAs
- LOA items
- Variations
- Variation lines
- Procurement requirements
- Purchase Orders
- Purchase Order lines
- Dispatches
- Dispatch lines
- Challans
- Challan lines
- Material receipts
- Material receipt lines
- Assets
- Asset movements
- Installations
- Warranties
- Billing records
- Billing lines
- Tax Invoices
- Tax Invoice lines
- Payments
- Payment allocations
- Documents
- Document templates
- Document versions
- Workflow definitions
- Workflow steps
- Workflow instances
- Workflow actions
- Users
- Roles
- Permissions
- User scopes
- Audit logs
- Alert rules
- Alerts
- Notifications

---

## 7. Quantity Integrity

Authoritative quantity validation must happen on the backend.

Example:

Approved quantity
→ Existing committed quantity
→ Requested quantity
→ Backend validation
→ Allow / Reject

The frontend must never be trusted as the final authority for quantity validation.

The system must protect against:

- Contract quantity being exceeded
- Incorrect commitments
- Duplicate transactions
- Incorrect receiving quantities
- Invalid billing quantities

---

## 8. Financial Integrity

Financial calculations must be performed centrally on the backend and tested.

This includes:

- Taxable amount
- Discount
- CGST
- SGST
- IGST
- Other applicable tax components
- Round-off
- Invoice total
- Payment allocation
- Outstanding amount
- Project financial calculations

Frontend calculations may be used for display but are not authoritative.

---

## 9. Current User Model

Initially WCDMS has only two application roles:

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
- Billing preparation
- Tax Invoice preparation
- Documents
- Operational management

The system must remain expandable so additional users and roles can be added later without redesigning the authorization architecture.

---

## 10. Authorization

Authorization must be enforced by the backend.

Evaluate:

Authenticated User
→ Active User
→ Role
→ Permission
→ Scope
→ Record Status
→ Workflow
→ Business Rule
→ Allow / Deny

The frontend may hide unavailable actions, but the backend must always enforce authorization.

---

## 11. Workflow

Important business transactions must use controlled status transitions.

Example:

DRAFT
→ SUBMITTED
→ UNDER REVIEW
→ APPROVED
→ ISSUED
→ COMPLETED
→ CLOSED

Not every module requires every state.

Do not allow users to bypass workflow by directly modifying a protected status field.

Use explicit business actions such as:

- Submit
- Approve
- Reject
- Return
- Issue
- Cancel

where applicable.

---

## 12. Segregation of Duties

Where approval is required:

Creator
≠
Approver

The system must prevent unauthorized self-approval where configured.

SUPER-ADMIN overrides must require:

- Reason
- User
- Timestamp
- Old value
- New value
- Audit entry

---

## 13. Document Management

Initial priority document types:

- Purchase Order
- Proforma Invoice
- Challan
- Tax Invoice
- Railway Receiving / Acknowledgement

The wider document system must also support:

- LOA
- Variation
- Quotation
- Work Order
- Delivery Documents
- Warranty Documents
- Project Reports
- Other Documents
- Uploaded/scanned supporting documents

Documents are controlled business records.

---

## 14. Document Generation

Official documents must:

- Use approved World Communication templates
- Use centralized numbering
- Use authoritative backend data
- Preserve historical information
- Support versioning
- Produce appropriate DOCX/PDF output where required
- Be A4 where applicable
- Avoid clipping, overlapping or cut-off content
- Be stored with document metadata
- Be auditable

Do not invent document layouts when an approved World Communication format exists.

Before implementing a document template, inspect the actual approved source document.

---

## 15. Document Versioning

Never silently overwrite an issued document.

Use:

Version 1
→ Amendment / Revision
→ Version 2

Historical versions must remain preserved according to permissions.

Relevant historical business information must remain reproducible even after master-data changes.

---

## 16. Historical Snapshot Rule

Historical documents must not change merely because master data changes.

Example:

If a vendor's address changes after a PO was issued, the historical PO must continue to represent the information used when that PO was issued.

The same principle applies to:

- Vendor/customer information
- Product descriptions
- Rates
- Bank details
- Relevant transaction information

---

## 17. Numbering

Document numbering must be centralized and protected against duplicates.

This applies to:

- PO
- PI
- Challan
- Tax Invoice
- Other numbered business documents

Do not invent numbering formats when an existing World Communication format is available.

---

## 18. Audit

Important actions must be auditable, including:

- Create
- Update
- Submit
- Approve
- Reject
- Return
- Issue
- Cancel
- Override
- Payment operations
- Document generation
- Document versioning
- User changes
- Permission changes

Audit records should contain appropriate:

- User
- Timestamp
- Action
- Entity
- Entity ID
- Old value
- New value
- Reason where applicable
- Request/reference information

---

## 19. Soft Delete / Historical Records

Do not casually hard-delete transactional business records.

Prefer appropriate states such as:

- INACTIVE
- CANCELLED
- VOID
- ARCHIVED

Historical business records must remain traceable.

---

## 20. Alerts

The system will support alerts for conditions such as:

- PO delivery approaching
- PO overdue
- Receiving pending
- Short receipt
- Excess receipt
- Damaged material
- Rejected material
- Variation pending
- Project deadline approaching
- Project overdue
- Invoice pending
- Invoice overdue
- Payment issues
- Missing documents
- Warranty expiry
- Quantity mismatch
- Duplicate serial numbers
- Other configured business exceptions

Alerts should support severity, acknowledgement and resolution.

---

## 21. Reports and Dashboards

The system will support dashboards and reports including:

- Main Dashboard
- Project Dashboard
- LOA / BOQ Reconciliation
- Variation Register
- Procurement
- PO Register
- Vendor Performance
- Logistics
- Challan Register
- Receiving
- Asset Register
- Billing
- Receivables
- Payments
- Project Profitability
- Documents
- Exceptions

Important reports should support appropriate filtering, drill-down and export.

---

## 22. API

Use versioned APIs:

`/api/v1/`

Use consistent REST semantics.

Important business actions should use explicit endpoints rather than allowing unauthorized status manipulation.

Use standardized:

- Success responses
- Error responses
- Validation errors
- Pagination
- Filtering
- Sorting
- Search

---

## 23. Security

At minimum:

- Secure password hashing
- Authentication
- Authorization
- Input validation
- Secure sessions/tokens
- Appropriate security headers
- Rate limiting where appropriate
- Secure file uploads
- SQL injection protection
- XSS protection
- Secret management

Never log passwords, authentication tokens or secrets.

---

## 24. File Security

Uploaded files must be validated for:

- File type
- MIME type
- Extension
- Size
- Filename
- Storage destination
- User authorization

Do not trust browser-supplied filenames or MIME types.

---

## 25. Testing

A feature is not complete merely because the application runs.

Appropriate testing should cover:

- Unit tests
- API tests
- Integration tests
- Workflow tests
- Permission tests
- Document-generation tests
- End-to-end tests

The complete business chain should eventually be tested:

Project
→ LOA
→ PO
→ Dispatch
→ Challan
→ Receiving
→ Asset
→ Billing
→ Invoice
→ Payment

---

## 26. Development Workflow

Before implementing a significant feature:

1. Understand the requirement.
2. Inspect the existing repository.
3. Search for reusable existing components.
4. Identify affected architecture.
5. Check the approved documentation.
6. Implement the smallest coherent change.
7. Run appropriate tests/checks.
8. Review the Git diff.
9. Update relevant documentation.
10. Report what changed and whether tests passed.

---

## 27. Codex Rules

Do not:

- Rebuild an existing module unnecessarily.
- Create duplicate models.
- Create duplicate APIs.
- Create duplicate services.
- Create duplicate utilities.
- Change the database architecture silently.
- Invent business requirements.
- Replace approved document formats with generic templates.
- Put secrets in source code.
- Modify unrelated files.
- Perform broad refactoring without approval.

When ambiguity remains and the decision could affect:

- Database structure
- Document format
- Financial calculations
- Numbering
- Permissions
- Security
- Deployment

stop and ask for clarification.

---

## 28. Module Completion Standard

A module is complete only when applicable components are implemented and tested:

- Database
- Backend
- API
- Frontend
- Validation
- Permissions
- Workflow
- Audit
- Documents
- Tests
- Documentation

Do not declare a module complete merely because its UI exists.

---

## 29. Implementation Order

The initial implementation sequence is:

1. Foundation
2. Authentication
3. SUPER-ADMIN / ADMIN
4. Organization and Master Data
5. Railway Master
6. Project and LOA
7. Product / OEM / UOM
8. Procurement
9. Purchase Order
10. Proforma Invoice
11. Dispatch
12. Challan
13. Receiving
14. Assets
15. Billing
16. Tax Invoice
17. Payments
18. Documents
19. Workflow
20. Alerts
21. Reports / Dashboard
22. Testing and Hardening
23. Deployment

Do not begin the next major module until the previous module meets its completion criteria unless explicitly instructed otherwise.

---

## 30. Git Discipline

Use meaningful commits.

Examples:

- `feat: add project management module`
- `feat: add purchase order workflow`
- `feat: add challan generation`
- `fix: correct invoice calculation`
- `test: add PO quantity validation`
- `docs: update database architecture`

Review the Git diff before committing.

Never commit:

- `.env`
- passwords
- API keys
- database credentials
- private business data
- generated sensitive production documents

---

## 31. Completion Report

After completing a module, report:

MODULE:
STATUS:

IMPLEMENTED:
- ...

DATABASE:
- ...

API:
- ...

FRONTEND:
- ...

WORKFLOW:
- ...

PERMISSIONS:
- ...

DOCUMENTS:
- ...

TESTS:
- ...

KNOWN ISSUES:
- ...

NEXT MODULE:
- ...
---

## 32. Repository Documentation Rules

### AGENTS.md

`AGENTS.md` contains permanent instructions for AI coding agents working on WCDMS.

Update `AGENTS.md` only when:

- Development rules change.
- Architecture rules or constraints change.
- Testing or verification requirements change.
- Repository conventions change.
- Security or Git rules change.
- A new permanent instruction for coding agents is introduced.

Do not update `AGENTS.md` merely because a development phase or feature was completed.

Do not use `AGENTS.md` as a development diary or append routine phase-completion reports to it.

### README.md

`README.md` describes the current WCDMS application for developers and maintainers.

Update `README.md` when:

- A module or major feature is added or materially changed.
- Application architecture changes.
- Installation or setup instructions change.
- Runtime dependencies change.
- Database or migration setup changes.
- Backend or frontend startup procedures change.
- Important operational usage changes.

Do not use `README.md` as a chronological development diary.

Do not append repetitive phase-completion reports, temporary test counts,
temporary implementation notes, or per-phase file lists.

Keep `README.md` consolidated so that it describes the current state of WCDMS.

### Completion Reports

Detailed Codex completion reports should normally remain in the Codex
conversation/output.

Do not automatically copy completion reports into `README.md` or `AGENTS.md`
unless the information has lasting documentation value.

Test counts, temporary QA results, migration verification output, temporary
sample-file locations, and per-phase Git status do not normally belong in
permanent repository documentation.

---

## 33. Authoritative World Communication Document Templates

Files under:

`document_templates/`

are the authoritative World Communication visual references for supported
business documents.

These templates include approved formats for documents such as:

- Purchase Order
- Proforma Invoice
- Tax Invoice
- Quotation
- Supply / Delivery Challan
- Other approved World Communication documents added later

Do not redesign approved documents based on agent preferences.

Do not replace approved World Communication formats with generic invoice,
quotation, PO, challan, or document layouts.

Before implementing or materially changing document rendering, inspect the
actual relevant source template under `document_templates/`.

### Template vs Business Data

The files under `document_templates/` define PRESENTATION and VISUAL STRUCTURE.

They are not authoritative sources for transactional business data,
calculations, quantities, rates, taxes, document numbers, workflow states,
party identities, or other live business values.

Authoritative business values must come from WCDMS backend records and
historical snapshots.

Generated documents must dynamically populate information from the relevant
WCDMS records.

Never hard-code sample or test values into production document rendering,
including:

- Customer names
- Indian Railways
- Railway zones or divisions
- Railway authorities
- Vendor / supplier names
- OEM names
- Project references
- LOA numbers
- LOA dates
- Addresses
- Billing addresses
- Shipping addresses
- Consignees
- Product descriptions
- Models / part numbers
- Quantities
- Rates
- Taxes
- Document dates
- Reference numbers
- Bank information
- Payment terms

If a generated test/sample document displays values such as `Indian Railways`,
those values must originate from the test/sample record supplied to the
renderer and must not be embedded as production defaults.

### Historical Document Integrity

Issued historical documents must remain reproducible from persisted
transactional data and historical snapshots.

Do not populate an old issued document from mutable current master data when
the appropriate historical snapshot exists.

If a required historical value was not captured at issuance, identify the
missing snapshot requirement rather than silently substituting current master
data.

### Document-Specific Business Context

Different document types must expose the business information appropriate to
their purpose.

Do not make all documents generic forms with only the document title changed.

For example:

#### Purchase Order

Where applicable, include:

- Vendor / Supplier
- Vendor address
- Vendor GSTIN
- Buyer organization
- Billing address
- Ship-To / Delivery address
- Project / Work reference
- LOA reference and date
- Procurement requirement reference
- OEM / Make
- Model / Part Number
- HSN
- UOM
- Quantity
- Purchase rate
- Taxes
- Payment terms
- Terms & Conditions

A Purchase Order must identify the counterparty as Vendor / Supplier, not
Customer.

Vendor and OEM are separate business concepts and must not be assumed to be
the same entity.

#### Proforma Invoice

Where applicable, include:

- Customer
- Customer GSTIN
- Bill-To
- Ship-To
- Project / Work reference
- LOA reference and date
- Railway division
- Railway authority / consignee
- Challan / dispatch references
- Relevant reference dates
- Payment terms
- Bank details
- Terms & Conditions

#### Tax Invoice

Where applicable, include:

- Customer
- Customer GSTIN
- Bill-To
- Ship-To
- Invoice number and date
- Due date
- Place of supply
- Project / Work reference
- LOA reference and date
- Railway division / authority
- PI reference
- Challan reference
- Relevant source/reference dates
- Payment terms
- Bank details
- Terms & Conditions

#### Quotation

Where applicable, include:

- Customer
- Customer GSTIN
- Quotation number
- Quotation date
- Revision
- Validity
- Customer enquiry / tender reference
- Reference date
- Project / Work reference
- Railway division / authority
- Bill-To / customer address
- Ship-To where applicable
- Payment terms
- Terms & Conditions

#### Supply / Delivery Challan

Where applicable, include:

- Challan number and date
- Customer
- Project / Work reference
- LOA reference and date
- Railway division
- Consignee / receiving authority
- Delivery / Ship-To address
- Dispatch-From address
- Transporter
- Vehicle number
- LR / RR / transport reference
- E-Way Bill reference where available
- Dispatch / delivery references
- Receiver acknowledgement

Railway Challans must remain non-financial and must not expose procurement
rates, vendor costs, purchase taxes, margins, or other confidential commercial
information.

### Dynamic Layout and Pagination

Approved templates may contain fixed rows or fixed visual structures because
they originated as manually maintained Excel documents.

WCDMS-generated documents must safely adapt those designs for dynamic data.

Support:

- Single-line documents
- Multi-line documents
- Large item counts
- Long product descriptions
- Long addresses
- Long notes
- Long Terms & Conditions
- Multi-page documents

Preserve the approved World Communication visual language while preventing:

- Clipping
- Overlapping
- Cut-off text
- Broken tables
- Uncontrolled page breaks
- Orphan headings
- Poorly fragmented Terms & Conditions

Table headings should repeat on continuation pages where appropriate.

Terms & Conditions should paginate as a deliberate section.

Do not leave a `Terms & Conditions` heading orphaned at the bottom of a page.

Where long Terms & Conditions require multiple pages, split them between
logical terms or paragraphs where practical and use a clear continuation
heading where appropriate.

Do not place an Authorised Signatory block in the middle of a continuing
Terms & Conditions section.

### Logo and Corporate Identity

Use the official World Communication logo supplied through the approved
templates or repository assets.

Do not fabricate, approximate, redraw, or substitute an unofficial logo when
the approved asset is available.

Corporate styling should follow the authoritative World Communication
templates.

### PDF and Excel

PDF and Excel versions of the same business document should represent the same
authoritative business record.

They may use renderer-specific technical adaptations, but they must not
contradict each other in:

- Document number
- Date
- Party
- Project
- LOA
- Addresses
- Items
- Quantities
- Rates
- Taxes
- Totals
- Terms
- Bank information
- Other business references

PDF generation must prioritize reliable print output and pagination.

Excel generation must preserve typed numeric values and usable spreadsheet
structure while following the approved visual template as closely as practical.

Do not rely on spreadsheet formulas as the authoritative source of WCDMS
business calculations.

### Template and Output Directories

`document_templates/`

contains permanent authoritative source/reference templates.

`outputs/`

contains generated documents, QA samples, previews, and other output artifacts.

Generated output files must never be treated as authoritative source templates.

Temporary visual-QA artifacts should not be committed unless they are
intentionally required as test fixtures.

Repository ignore rules for generated outputs must not accidentally ignore
`document_templates/` or required document-engine assets.
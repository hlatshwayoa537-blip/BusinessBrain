# VEXION release-readiness register

**Product:** VEXION — The Business Control System  
**Register date:** 20 November 2026 (updated after PR #88 merge)  
**Purpose:** prevent features, deployments or third-party integrations from being described as production-ready before they have been verified.

## Status rules

- **Ready** — implemented and covered by relevant automated checks. This does not automatically mean a real provider integration or business workflow has been validated.
- **Needs fixing** — an engineering gap, defect, missing safeguard or incomplete workflow remains.
- **Needs external access** — requires provider credentials, infrastructure configuration, a POS/bank feed or another external dependency.
- **Needs your validation** — requires realistic business records, a real user or an agreed pilot.

A feature is not release-approved solely because its pull request merged, CI passed or Render reports a deployment as live.

## Current release register

| Area | Status | Verified boundary / outstanding work |
|---|---|---|
| Authentication and business workspaces | Ready | Registration, login, signed access tokens, business membership and selected-workspace switching are implemented and covered by automated tests. Complete a full permission and tenant-isolation review before launch. |
| Email verification and password recovery | Needs external access / Needs fixing | Password-reset request and confirmation endpoints plus frontend screens are implemented. Tokens are hashed, one-time, expire after 30 minutes, and successful resets revoke existing sessions. SMTP is not configured, so real delivery cannot be tested; email verification is still not implemented. |
| POS ingestion | Ready | Generic normalized transaction ingestion, webhook authentication, idempotency, terminal discovery and mapped CSV import exist. Linked refunds use provider-native original receipt and line references (PR #79); legacy VEXION UUID references remain supported. POS timestamps must include an explicit timezone offset; stored values are normalized to UTC and daily analytics group by Africa/Johannesburg local date (PR #81). |
| Named POS provider integrations | Needs external access | No named vendor adapter has been proven against a live POS provider. Do not claim a vendor is integrated until its adapter and real feed are tested. |
| Daily Business Close | Ready | Close and reconciliation workflows are implemented with automated coverage. Verify calculations against real till close reports before pilot sign-off. |
| Invoices | Ready | Invoice creation, VAT/tax calculations and status tracking are implemented in the workspace. PDF generation, email delivery, payment links and credit notes are not included yet. |
| Customers & CRM | Needs fixing | There is no complete customer relationship management module; customer records used by receivables are not a full CRM. |
| AI Business Manager | Needs fixing | The dashboard correctly marks this module as planned. No AI assistant API route or model-provider integration is present yet, so grounded natural-language business Q&A is not available. |
| Discrepancy management | Ready | Case creation, assignment, status changes, notes and supporting evidence workflows exist. Wording remains neutral: a discrepancy is not proof of wrongdoing. |
| Deal Room document uploads | Ready | Private upload, content validation, malware scan and clean-file promotion are implemented. PR #73 adds content-signature validation and checks the promoted object before it becomes available. |
| Private object storage and malware scanning | Needs external access | The code supports S3-compatible storage and ClamAV. Production bucket credentials, private access policy, CORS, scanner connectivity and provider-side lifecycle rules must be configured and tested. |
| Abandoned quarantine cleanup | Needs fixing | Failed/abandoned uploads can leave pending quarantine objects. Configure and verify provider lifecycle cleanup or add a scheduled cleanup process; do not assume the application currently removes every abandoned object. |
| Temporary AI/document processing uploads | Needs fixing | The selected design is Cloudflare R2 temporary storage. This processing workflow is not implemented yet. Its requirement is deletion within 60 seconds after processing completes. Keep this separate from durable Deal Room attachments and discrepancy evidence. |
| Durable Deal Room and discrepancy evidence | Ready | These are business records and remain stored until a permitted deletion. Their signed download links expire after 60 seconds; that expiry does not delete the underlying document. |
| Bank statement reconciliation | Ready | CSV statement import, match suggestions, confirmed links and ledger workflows are implemented. |
| Live bank connections | Needs external access | No live bank/open-banking connection has been configured or tested. |
| Supplier purchasing and payables | Ready | Purchase orders, supplier invoice matching/approval, payables and bank reconciliation workflows exist. Validate the accounting treatment with real records. |
| Customer receivables | Ready | Customer invoice and cash collection ledger workflows exist. Receipts are manually recorded unless independently matched to imported bank transactions. |
| Inventory and costing | Ready | Stock movements, costing and POS-linked return workflows exist. Reliable COGS requires complete valued opening stock and stock receipts. |
| Expenses and cash control | Ready | Expense and cash-control workflows exist. Forecasts use recorded/scheduled movements; they do not assume future sales or collections. |
| Financial reports and business intelligence | Needs your validation | Automated tests exist, but P&L, cash flow, inventory valuation, forecasts and VAT-related outputs must be reconciled against sample SME books and source documents. Reports now disclose that manual paid income is additive to POS sales and that bank statement CSV reconciliation is separate from the cash-flow report (PR #78). |
| Referral programme | Needs external access | Direct referrals, payment verification, and the five-referral R399 calculation are implemented. The billing overview detects when the provider-confirmed recurring price is out of sync with active terminal count or referral eligibility. An owner/admin can request the update; VEXION only records the new price after PayFast confirms it. This is a user-initiated control, not an automatic background update. Run end-to-end tests when PayFast is available. |
| PayFast subscription code | Needs external access | Hosted checkout, secure HTTPS return/cancel URLs, signature and merchant checks, Cloudflare client-IP validation, server-side ITN validation, initial activation, token-based recurring charge processing, status-aware idempotency, cancellation handling and a recurring charge ledger are implemented and CI-tested. PR #88 adds owner/admin-only in-app cancellation, only marks local cancellation after PayFast confirms it, preserves the last provider-confirmed price until an update succeeds, detects recurring price drift, avoids redundant provider updates and indexes subscription tokens for token-only ITNs. CI passed 160 backend tests plus frontend dependency audit/build. Both Render API and frontend deployments are live on merge commit `6ddb76d`; startup logs confirm migration `0034_payfast_token_index` applied. The merchant account/credentials are unavailable because PayFast registration is blocked; no sandbox or live transaction has been tested. |
| PayFast notification source-IP handling | Ready | PR #72 uses Cloudflare's client-IP header for Render-hosted requests, avoids trusting a client-supplied X-Forwarded-For chain, and performs the server-side validation asynchronously. Still requires a real PayFast sandbox ITN test. |
| Subscription lifecycle | Needs external access | Recurring `COMPLETE` and `CANCELLED` notifications, optional `m_payment_id` handling by subscription token, charge history, late-notification protection and reactivation are implemented and CI-tested. PR #88 adds an owner/admin cancellation control and explicit recurring price synchronization when terminal count/referral eligibility changes; cancellation and price updates are recorded only after provider confirmation. Still requires live sandbox testing for cancellation, retries, provider-side failures, token changes, refunds, disputes and recurring amount updates. |
| Activity/audit trail | Needs fixing | The current activity aggregation covers selected workflows (daily closes, discrepancies, evidence, purchase orders, supplier invoices and bank matches), not every consequential business change. Expand coverage before a regulated or high-assurance rollout. |
| Health/readiness diagnostics | Ready | Liveness and database/schema readiness endpoints are implemented and covered by tests. Optional storage, scanner, PayFast and email flags indicate configuration only, not successful provider connectivity. |
| Render API health-check configuration | Needs external access | The Render API service currently has an empty `healthCheckPath`. Configure `/api/v1/health/ready` in the Render service settings. Until this is set, a `live` deployment only confirms that the process started; it does not prove database/schema readiness to Render. The available Render connection can inspect this setting but cannot update it. |
| External production HTTP smoke test | Needs your validation | The deployment platform reports live, but this environment could not retrieve the readiness endpoint directly. A successful HTTP check from an independent client remains outstanding. |
| Database migrations | Ready | Production API startup logs confirm the migration chain applied through `0034_payfast_token_index` on 20 November 2026; the API deployment then reported live. Direct database revision query and independent readiness HTTP check remain outstanding. Revision IDs are regression-tested against Alembic's 32-character version column. |
| Backups and restore | Needs external access | Verify backup schedule, retention, point-in-time recovery availability and a successful restore drill. |
| Database continuity | Needs fixing | The current Render Postgres free instance is scheduled to expire on 16 December 2026 unless renewed or upgraded. Decide on durable production hosting before onboarding paying businesses. |
| Security review | Needs fixing | Automated permission and validation tests exist, but a full authorization matrix, rate-limit review, dependency audit beyond the frontend high-severity gate, secrets review and independent security assessment remain outstanding. |
| POPIA and customer terms | Needs fixing | Finalize privacy notice, processing purposes, retention/deletion schedule, access/deletion requests, processor/subprocessor disclosures, terms and customer agreement with qualified South African legal guidance. |
| Customer onboarding and support | Needs your validation | Test business setup, user roles, importing records, explaining exceptions, support escalation and recovery with real SME users. |
| Real-world pilot | Needs your validation | No real SME pilot has completed end-to-end validation. Use consented, representative records and reconcile outputs against source records. |
| Final validation guide and sign-off PDF | Needs fixing | Produce only after engineering fixes and deployment checks are complete. It must cover each module, setup prerequisites, step-by-step tests, expected results, failure recording, limitations and final sign-off. |

## Important document-retention distinction

VEXION has two different document use cases:

1. **Temporary AI/document processing:** the agreed design uses Cloudflare R2. A document is temporary and must be deleted within 60 seconds after processing finishes. This workflow is not yet implemented.
2. **Durable business records:** Deal Room attachments and discrepancy evidence are deliberately retained until a permitted user deletes them. Their download URLs expire after 60 seconds, but the stored records do not automatically expire after one minute.

Do not apply the temporary-processing deletion rule to durable case evidence, invoices, settlement records or Deal Room attachments.

## External prerequisites before a business pilot

- PayFast merchant registration, sandbox/live credentials and successful ITN/payment lifecycle testing.
- Private S3-compatible/R2 bucket configuration for durable documents, private access controls, CORS, ClamAV availability and quarantine lifecycle cleanup.
- Representative POS exports or a supported live provider adapter.
- Representative bank statement CSVs and source financial records.
- Database continuity plan, backups and a successful restore drill.
- Approved POPIA/customer documentation and operational support process.

## Release gate

The product may move to supervised real-world validation only after all engineering defects marked **Needs fixing** that affect the pilot scope are resolved, all relevant deployments are confirmed live, external prerequisites for that scope are satisfied, and the user has received the complete step-by-step validation guide. Wider commercial rollout requires successful real-world validation and explicit sign-off.

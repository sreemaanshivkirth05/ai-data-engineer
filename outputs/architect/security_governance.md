# 1. Overview

This lakehouse design on AWS contains operational and analytical data across orders, customers, products, payments, shipments, returns, website events, and marketing campaigns. Even though the dataset profile does not explicitly list PII columns, the contract clearly includes **direct and indirect personal data** and **financial data**.

Recommended security posture:

- **Bronze**: raw, restricted, immutable ingestion zone
- **Silver**: cleansed, standardized, access-controlled curated zone
- **Gold**: business-ready, aggregated, least-privilege consumption zone

Primary goals:

- Protect customer and payment-related data
- Enforce least privilege and separation of duties
- Support auditability, lineage, and compliance
- Minimize exposure of PII through masking, tokenization, and aggregation

---

# 2. Data Classification & PII Handling

## 2.1 Data Classification

### Highly Sensitive
- `Customers.email`
- `Customers.name`
- `Payments.payment_id` if linkable to a person/order
- `WebsiteEvents.customer_id`, `session_id` when linked to identity
- Any joinable identifiers that can re-identify a person
- Payment-related records and refund data
- Potentially `Shipping` records if they can be linked to a customer identity

### Sensitive / Confidential
- `customer_id`, `order_id`, `payment_id`, `shipping_id`, `session_id`
- `order_date`, `signup_date`, `event_time`, `delivered_date` when combined with identity
- `country`, `city`, `segment`, `device_type`, `source`, `page_name`, `product_id`
- `return_reason` if it may reveal personal circumstances

### Internal / Business Confidential
- `Products.cost_price`, `supplier_id`
- `MarketingCampaigns.spend`, `impressions`, `clicks`, `conversions`
- `Orders.quantity`, `unit_price`, `discount`, `total_amount`
- `Payments.amount`, `payment_status`
- `Shipments.carrier`, `shipping_status`, `region`

## 2.2 PII Handling Strategy

### Bronze Layer
- Store raw data with **restricted access only**
- No broad analyst access
- Encrypt and isolate by account/bucket/prefix
- Retain original values for traceability and replay, but only for approved engineering/security roles

### Silver Layer
- Apply **standardization and minimization**
- Replace direct identifiers with pseudonymous keys where possible
- Mask or tokenize:
  - `name` → masked or tokenized
  - `email` → hashed/tokenized, domain optionally retained only if business-approved
  - `session_id` → pseudonymous token
- Remove unnecessary fields if not required for downstream use

### Gold Layer
- Prefer **aggregated, de-identified outputs**
- Expose only business metrics and dimensions approved for analytics
- Avoid row-level customer views unless explicitly required and approved
- If customer-level reporting is needed, use masked identifiers and strict row-level security

## 2.3 Masking Rules

### Static Masking
Use for non-production copies, QA, and sandbox environments:
- `name`: `J*** D***`
- `email`: `j***@domain.com` or fully tokenized
- `customer_id`: surrogate key or token
- `session_id`: random token
- `return_reason`: redact free-text if it may contain personal details

### Dynamic Masking
Use in production query paths:
- Analysts see masked `email`, `name`, and any direct identifiers
- Privileged users can access unmasked values only through approved break-glass or controlled workflows

### Tokenization / Hashing
- Use deterministic tokenization for joinability across domains
- Use salted hashing only when reversibility is not required
- Keep token vault separate from analytics environment

## 2.4 Data Minimization
- Do not replicate PII into Gold unless explicitly justified
- Remove unused columns during Silver transformation
- Limit retention of raw event-level identity data
- Prefer aggregated customer segments and cohorts over individual records

---

# 3. Access Control & IAM

## 3.1 IAM Principles
- **Least privilege**
- **Separation of duties**
- **Default deny**
- **Need-to-know**
- **Environment isolation**: dev / test / prod separated by AWS accounts or strong boundaries

## 3.2 Recommended AWS Control Model

### Storage and Compute
- Use **AWS IAM roles** for workloads, not long-lived access keys
- Use **S3 bucket policies**, **Lake Formation permissions**, and **IAM** together
- Use **KMS key policies** to restrict decryption
- Use **VPC endpoints** for private access to S3, Glue, Athena, Redshift, and KMS where applicable

### Role-Based Access Control

#### Data Engineering
- Read/write Bronze and Silver
- No access to Gold business consumption unless needed
- No access to unmasked PII unless explicitly approved

#### Analytics Engineers
- Read Silver
- Write Gold
- Limited access to Bronze for debugging only

#### Data Analysts
- Read Gold only
- Masked or aggregated access to Silver if approved
- No direct access to raw PII

#### Data Scientists
- Read approved Silver datasets
- Access to pseudonymized customer-level data only if business case approved
- No direct access to raw identifiers unless governed exception exists

#### Security / Compliance
- Read audit logs, lineage, and metadata
- Access to sensitive datasets only for investigations

#### Business Users
- Gold only, via governed BI tools and semantic layer

## 3.3 Row-Level and Column-Level Security
Implement:
- **Column-level security** for `name`, `email`, `session_id`, payment identifiers
- **Row-level security** for:
  - region-based access
  - business unit access
  - customer segment restrictions if needed
- Use Lake Formation LF-tags or equivalent policy tags to classify and enforce access

## 3.4 Privileged Access
- Break-glass access for incident response only
- Time-bound approvals
- Session logging and post-access review
- MFA required for all privileged roles

## 3.5 Service-to-Service Access
- Use short-lived credentials via IAM roles
- No embedded secrets in code
- Restrict cross-account access with explicit trust policies
- Separate ingestion, transformation, and consumption roles

---

# 4. Encryption & Secrets Management

## 4.1 Encryption at Rest
Use **AWS KMS-managed encryption** for all storage and services:

- **S3**: SSE-KMS for Bronze, Silver, Gold
- **Glue Data Catalog** metadata encryption where applicable
- **Athena query results** encrypted with KMS
- **Redshift / EMR / RDS** if used in the platform, encrypted with KMS
- **Backups and snapshots** encrypted

### Key Management
- Separate KMS keys by environment and, ideally, by sensitivity tier
- Rotate keys regularly
- Restrict key usage to approved roles and services
- Log all KMS decrypt and key administration events

## 4.2 Encryption in Transit
- Enforce **TLS 1.2+** for all data movement
- Require HTTPS for S3 access
- Use private networking where possible:
  - VPC endpoints
  - PrivateLink
  - no public bucket access
- Encrypt inter-service traffic for ETL/ELT pipelines and BI tools

## 4.3 Secrets Management
- Store credentials in **AWS Secrets Manager** or **SSM Parameter Store**
- Rotate secrets automatically where possible
- Never store secrets in notebooks, code repositories, or environment files
- Use IAM roles instead of static credentials for AWS-native access
- For tokenization systems, keep token vault credentials isolated and tightly controlled

## 4.4 Sensitive Field Protection
- Hash/tokenize direct identifiers before broad distribution
- Consider format-preserving encryption for operational compatibility if needed
- Use deterministic encryption only when joinability is required and risk is accepted

---

# 5. Audit Logging & Lineage

## 5.1 Audit Logging
Enable and retain logs for:

- **AWS CloudTrail** for API activity
- **S3 access logs / CloudTrail data events** for object-level access
- **Lake Formation access logs** for governed table access
- **KMS logs** for decrypt and key usage
- **Glue job logs**, workflow logs, and failure events
- **Athena query logs** and query history
- BI tool access logs if dashboards expose sensitive data

## 5.2 Logging Requirements
Capture:
- Who accessed what
- When access occurred
- From where access occurred
- What action was taken
- Which dataset/version was used
- Whether masking was applied
- Whether access was approved or denied

## 5.3 Retention
- Retain security logs according to policy and regulatory requirements
- Store logs in a separate, immutable security account or log archive
- Apply WORM/immutability controls where required
- Protect logs from alteration and deletion

## 5.4 Lineage
Implement end-to-end lineage across:
- Source system → Bronze ingestion
- Bronze → Silver transformations
- Silver → Gold models
- Gold → BI dashboards / ML features

Recommended metadata capture:
- Source file/table name
- Ingestion timestamp
- Transformation job ID
- Schema version
- Column mappings
- Data quality checks
- Downstream dependencies

Use a metadata catalog and lineage tooling integrated with Glue, orchestration, and BI layers.

---

# 6. Governance Processes

## 6.1 Data Ownership
Assign:
- **Data Owner** for each domain: Orders, Customers, Products, Payments, Shipments, Returns, WebsiteEvents, MarketingCampaigns
- **Data Steward** for definitions, quality, and access approvals
- **Platform Owner** for infrastructure and controls
- **Security/Privacy Owner** for policy enforcement

## 6.2 Data Contract Governance
- Version the contract
- Define schema evolution rules:
  - backward-compatible additions allowed with review
  - breaking changes require approval and migration plan
- Validate incoming data against contract at ingestion
- Reject or quarantine non-conforming records

## 6.3 Access Review Process
- Quarterly access recertification
- Review privileged roles monthly
- Remove stale permissions automatically
- Track exceptions with expiry dates

## 6.4 Data Quality and Control Gates
Before promotion from Bronze to Silver and Silver to Gold:
- schema validation
- null/duplicate checks
- referential integrity checks
- PII detection checks
- anomaly detection on key metrics
- completeness and freshness checks

## 6.5 Retention and Deletion
- Define retention by dataset and sensitivity
- Minimize retention of raw PII
- Support legal hold and deletion workflows
- Ensure downstream deletion propagation where required

## 6.6 Change Management
- All pipeline, schema, and permission changes via IaC and code review
- Approval workflow for sensitive data exposure changes
- Maintain release notes for data products

---

# 7. Compliance Considerations

## 7.1 Likely Applicable Regulations
Depending on geography and customer base:
- **GDPR / UK GDPR**: customer identity, event tracking, profiling, deletion rights
- **CCPA/CPRA**: personal information, sharing, deletion, access rights
- **PCI DSS**: if payment data ever includes cardholder data; current contract does not show PAN, but payment data is still sensitive
- **SOX**: if financial reporting relies on these datasets
- **ISO 27001 / SOC 2**: security controls, logging, access management
- **Data residency laws**: if country-specific storage restrictions apply

## 7.2 GDPR/Privacy Controls
- Lawful basis and purpose limitation
- Data minimization
- Right to access, rectification, deletion
- Pseudonymization for analytics
- DPIA for high-risk processing such as behavioral tracking in `WebsiteEvents`
- Consent management for marketing and tracking data where required

## 7.3 Payment Data
- Do not store card numbers, CVV, or sensitive authentication data unless explicitly required and PCI-scoped
- If payment processor data is ingested, isolate PCI-relevant fields and scope
- Prefer processor tokens over raw payment credentials

## 7.4 Cross-Border and Residency
- Enforce region-specific storage and processing if required
- Restrict replication of PII across regions
- Document data transfer mechanisms and legal basis

## 7.5 Auditability
- Maintain evidence for:
  - access approvals
  - masking enforcement
  - encryption configuration
  - retention policies
  - deletion requests
  - lineage and data quality controls

---

# 8. Risks & Gaps

## 8.1 Key Risks
- **PII not explicitly listed in the profile but present in the contract**: `name`, `email`, `customer_id`, `session_id`
- **Re-identification risk** from joins across Orders, Customers, WebsiteEvents, Shipments, and Returns
- **Behavioral profiling risk** from event tracking and campaign attribution
- **Overexposure in Gold** if row-level customer data is published broadly
- **Payment sensitivity** if payment records are not properly scoped
- **Free-text risk** in `return_reason` if users enter personal information

## 8.2 Gaps to Resolve
- Confirm whether `customer_id` is a direct identifier or surrogate key
- Confirm whether `payment_id` links to cardholder data or only internal transaction IDs
- Define exact masking rules for BI and ad hoc analysis
- Define retention periods per dataset and jurisdiction
- Confirm whether `WebsiteEvents` requires consent gating and cookie/trackers governance
- Define whether supplier data is confidential or shared externally
- Establish a formal data classification standard and tag all columns

## 8.3 Recommended Next Actions
- Implement column-level classification tags in the catalog
- Enforce Lake Formation permissions by sensitivity tier
- Add automated PII detection in ingestion and CI/CD
- Create approved masked Gold views for analysts
- Set up audit log centralization and immutable retention
- Document privacy notices, consent handling, and deletion workflows


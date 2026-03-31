# 1. Overview

This design assumes a **Bronze / Silver / Gold lakehouse on AWS** with mixed operational and analytical data across orders, customers, products, inventory, marketing, web traffic, and suppliers.

## Security and governance objectives
- Protect **customer PII** and any derived sensitive attributes.
- Enforce **least privilege** across ingestion, transformation, and consumption layers.
- Apply **data minimization** and **purpose-based access**.
- Maintain **end-to-end lineage**, auditability, and traceability.
- Support compliance with common privacy and security obligations.

## Data sensitivity summary
Based on the contract, the dataset contains:
- **Direct identifiers / PII**: `customer_name`, `email`, potentially `customer_id` if it maps to a person.
- **Quasi-identifiers**: `state`, `city`, `country`, `device_type`, `traffic_source`, `session_id`.
- **Commercially sensitive data**: `unit_price`, `discount`, `sales`, `profit`, `cost_price`, `spend`, `impressions`, `clicks`, `conversions`, `stock_on_hand`, `reorder_level`, `lead_time_days`.
- **Low sensitivity operational data**: `order_date`, `signup_date`, `campaign_date`, `last_updated`, product/category metadata.

---

# 2. Data Classification & PII Handling

## Recommended classification model
Use four data classes:

| Class | Definition | Examples |
|---|---|---|
| Public | Safe for broad internal use | product category, generic campaign metadata |
| Internal | Non-public but low risk | order dates, inventory levels |
| Confidential | Business-sensitive | sales, profit, spend, supplier terms |
| Restricted | PII, identifiers, regulated or highly sensitive | customer_name, email, customer_id if linkable to person |

## Column-level classification
### Restricted
- `Customers.customer_name`
- `Customers.email`
- `Customers.customer_id` if it is a persistent customer identifier tied to a person
- `WebTraffic.customer_id` if linkable to a person
- Any joined/derived dataset that can re-identify a customer

### Confidential
- `Orders.sales`, `Orders.profit`, `Orders.unit_price`, `Orders.discount`
- `Products.cost_price`
- `Inventory.stock_on_hand`, `Inventory.reorder_level`
- `MarketingCampaigns.spend`, `impressions`, `clicks`, `conversions`
- `Suppliers.lead_time_days`
- `supplier_name` if supplier relationships are sensitive

### Internal
- Dates, geography, product metadata, campaign names, traffic source, device type, session metrics

## PII handling rules
### Bronze layer
- Store raw ingested data in a **restricted landing zone**.
- No broad analyst access.
- Apply **immutable retention controls** and **object-level encryption**.
- Do not transform or mask in-place unless required for ingestion safety.

### Silver layer
- Standardize and validate data.
- **Tokenize or pseudonymize** direct identifiers where possible:
  - Replace `customer_name` with a surrogate key or token.
  - Replace `email` with a hashed/tokenized value for matching use cases.
- Keep a separate **secure identity mapping table** in a highly restricted account or schema.

### Gold layer
- Publish only **minimum necessary fields**.
- Default to:
  - masked email
  - pseudonymized customer identifiers
  - aggregated or thresholded outputs for sensitive metrics
- Avoid exposing direct PII unless there is a documented business need and approval.

## Masking strategy
### Static masking
Use for non-production copies, QA, and analytics sandboxes:
- `customer_name` → `J*** D***`
- `email` → `j***@domain.com`
- `customer_id` → surrogate token

### Dynamic masking
Use at query time for restricted fields:
- Analysts see masked values.
- Privileged users see unmasked values only with approved role and purpose.

### Tokenization / hashing
- Use **deterministic tokenization** for joinability across datasets.
- If hashing emails, use **salted HMAC** rather than plain hashing to reduce re-identification risk.
- Store salts/keys in AWS KMS or a dedicated secrets service.

## De-identification guidance
- Remove direct identifiers from Gold unless explicitly required.
- Apply **k-anonymity style review** for small segments or geographic slices.
- Suppress or aggregate low-count groups to prevent re-identification.

---

# 3. Access Control & IAM

## AWS control plane design
Use separate AWS accounts or at minimum separate environments for:
- **Ingestion / Bronze**
- **Transformation / Silver**
- **Serving / Gold**
- **Security / Audit**
- **Sandbox / Non-prod**

## IAM principles
- **Least privilege**
- **Separation of duties**
- **Deny by default**
- **Role-based access control (RBAC)** with optional attribute-based controls (ABAC)
- **No long-lived access keys** for humans

## Recommended roles
### Platform roles
- `data-platform-admin`
- `lakehouse-security-admin`
- `data-engineering-role`
- `etl-service-role`

### Data consumer roles
- `analyst-read-gold`
- `analyst-read-aggregated`
- `marketing-analyst-limited`
- `finance-analyst-confidential`
- `customer-ops-privileged`
- `auditor-readonly`

### PII-specific roles
- `pii-steward`
- `privacy-officer`
- `restricted-data-access`

## Access by layer
### Bronze
- Write access: ingestion service roles only
- Read access: data engineering, security, audit
- No general analyst access

### Silver
- Read/write: transformation jobs, data engineering
- Read: limited operational users and stewards
- PII access only if required for matching or quality checks

### Gold
- Read: business users based on domain and purpose
- Restricted columns masked by default
- Separate views for:
  - aggregated reporting
  - row-level operational access
  - privileged PII access

## Fine-grained controls
Implement:
- **Lake Formation** for table/column/row permissions
- **Column-level security** for PII fields
- **Row-level security** by region, business unit, or tenant if applicable
- **Tag-based access control** using data classification tags

## Recommended policy patterns
- Analysts can query Gold views, not raw tables.
- Only approved service roles can access Bronze/Silver raw objects.
- PII access requires:
  - business justification
  - time-bound approval
  - logged access
  - periodic recertification

## Network and identity controls
- Use **IAM Identity Center / SSO** for human access.
- Enforce **MFA** for privileged roles.
- Restrict access via **VPC endpoints / private connectivity** where possible.
- Use **cross-account roles** instead of sharing credentials.

---

# 4. Encryption & Secrets Management

## Encryption at rest
Enable encryption for all storage and services:
- **S3 SSE-KMS** for all lakehouse buckets
- **AWS KMS customer-managed keys** for sensitive datasets
- Separate keys by environment and, ideally, by domain or sensitivity tier

### Key management recommendations
- Rotate keys regularly
- Restrict KMS key administration to security admins
- Use key policies plus IAM policies
- Log all KMS usage in CloudTrail

## Encryption in transit
- Enforce **TLS 1.2+** for all data movement
- Use HTTPS for S3 access
- Use encrypted JDBC/ODBC connections for query engines
- Require private networking where feasible

## Secrets management
- Store credentials, API keys, and tokens in **AWS Secrets Manager** or **SSM Parameter Store**
- Never embed secrets in code, notebooks, or CI/CD variables in plaintext
- Use short-lived credentials via IAM roles and federation
- Rotate secrets automatically where supported

## Sensitive derived data
- Treat tokenization keys, salts, and mapping tables as highly restricted secrets
- Keep identity resolution assets in a separate secure boundary

---

# 5. Audit Logging & Lineage

## Audit logging requirements
Capture:
- Data access events
- Permission changes
- Query execution logs
- Object read/write/delete events
- KMS key usage
- Failed authentication and authorization attempts
- Data export/download events

## AWS logging stack
Recommended services:
- **AWS CloudTrail** for API and IAM activity
- **S3 server access logs** or CloudTrail data events for object access
- **Lake Formation audit logs**
- **CloudWatch Logs** for application and pipeline logs
- **Glue job logs** or equivalent ETL logs
- **Athena/warehouse query logs** if used

## Audit log retention
- Retain security logs per policy, typically **1–7 years** depending on regulatory needs
- Protect logs from tampering with:
  - separate security account
  - write-once or immutable storage controls
  - restricted delete permissions

## Lineage requirements
Track lineage at:
- source file / source table
- Bronze object
- Silver transformation
- Gold dataset / semantic layer
- downstream dashboard or ML feature set

## Lineage implementation
- Use a metadata catalog such as **AWS Glue Data Catalog**
- Capture transformation metadata in orchestration jobs
- Record:
  - source-to-target mappings
  - schema changes
  - job version
  - run ID
  - data quality checks
  - owner and steward
- If available, integrate with a lineage tool or OpenLineage-compatible framework

## Operational expectations
- Every Gold dataset should be traceable back to source tables.
- Every PII field should have a documented purpose and masking rule.
- Every access to restricted data should be attributable to a user or service principal.

---

# 6. Governance Processes

## Data ownership model
Assign:
- **Data Owner**: accountable for business use and access approval
- **Data Steward**: manages definitions, quality, and classification
- **Security/Privacy Officer**: approves restricted data handling
- **Platform Owner**: manages infrastructure and controls

## Required governance artifacts
- Data classification register
- Data dictionary / business glossary
- Data contract with schema and quality rules
- Access request and approval workflow
- Retention schedule
- Masking and tokenization standards
- Exception register for approved deviations

## Change management
- Schema changes require:
  - contract review
  - backward compatibility assessment
  - impact analysis on downstream consumers
- Breaking changes must be versioned and communicated before deployment

## Data quality governance
- Validate:
  - primary keys
  - referential integrity
  - null thresholds
  - allowed values
  - freshness and completeness
- Quarantine bad records in Bronze/Silver with error codes
- Track quality metrics over time

## Retention and deletion
- Define retention by data class and use case
- Implement deletion workflows for:
  - expired records
  - legal holds
  - privacy requests
- Ensure deletes propagate to derived datasets where required

## Periodic reviews
- Quarterly access recertification
- Annual classification review
- Regular privacy impact assessment for new use cases
- Review of privileged access and break-glass usage

---

# 7. Compliance Considerations

## Likely applicable frameworks
Depending on geography and business model, consider:
- **GDPR / UK GDPR** for EU/UK personal data
- **CCPA/CPRA** for California residents
- **SOC 2** for security, availability, confidentiality
- **ISO 27001** alignment for security management
- **PCI DSS** only if payment card data is introduced later
- Sector-specific rules if customers or suppliers fall under regulated industries

## GDPR/Privacy controls
- Lawful basis and purpose limitation
- Data minimization
- Right to access, rectify, delete, and restrict processing
- Pseudonymization for analytics
- Records of processing activities
- Data processing agreements with vendors

## CCPA/CPRA controls
- Notice at collection
- Consumer rights handling
- Data sharing/sale assessment
- Sensitive personal information handling if expanded later

## Security compliance controls
- MFA for privileged access
- Encryption at rest and in transit
- Logging and monitoring
- Vulnerability management
- Incident response procedures
- Least privilege and periodic access reviews

## Cross-border and residency
- If data includes customer or supplier records across countries, assess:
  - data residency requirements
  - cross-border transfer restrictions
  - regional storage and processing boundaries

## Retention and legal hold
- Ensure retention schedules do not conflict with legal obligations
- Support legal hold to prevent deletion during investigations or disputes

---

# 8. Risks & Gaps

## Key risks
1. **Re-identification risk**
   - Joining `customer_id`, geography, and web traffic can reveal individuals even if names/emails are masked.

2. **Overexposure in Gold**
   - Business users may receive more detail than necessary, especially on customer-level or campaign-level data.

3. **Weak identity mapping protection**
   - Tokenization tables or salts becoming accessible would undermine masking controls.

4. **Inconsistent classification**
   - If classification is not automated and enforced, sensitive fields may leak into downstream datasets.

5. **Uncontrolled extracts**
   - CSV exports, notebooks, and ad hoc shares can bypass lakehouse controls.

6. **Lineage gaps**
   - Without strong metadata capture, it will be difficult to prove provenance or support audits.

7. **Privilege creep**
   - Access granted for one project may persist beyond its need.

## Gaps to address before production
- Confirm whether `customer_id` is a true pseudonymous key or directly linkable to a person.
- Define exact masking rules for each restricted field.
- Implement row/column-level security in the query layer.
- Establish a secure tokenization service and key custody model.
- Define retention periods for each dataset and layer.
- Add formal approval workflow for PII access.
- Validate whether any jurisdictional privacy laws apply to customers, employees, or suppliers.

## Recommended next steps
- Create a **data classification matrix** for every column.
- Implement **Lake Formation permissions** and **KMS key separation**.
- Build **masked Gold views** as the default consumption layer.
- Set up **CloudTrail, audit logs, and lineage capture** from day one.
- Run a **privacy impact assessment** before broad analyst access is enabled.
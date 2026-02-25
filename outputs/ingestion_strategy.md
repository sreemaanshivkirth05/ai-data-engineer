# Data Ingestion Strategy for E-commerce Analytics

## 1. Overview
This document outlines the data ingestion strategy for an e-commerce company requiring analytics on revenue, orders, customers, and payments. The strategy is designed to ensure a scalable architecture on AWS, facilitating daily dashboards and compliance with data governance policies, particularly concerning PII.

## 2. Ingestion Sources
The primary ingestion sources for this strategy include:
- Employee dataset (as described in the dataset profile)
- Additional datasets related to orders, payments, and customer interactions, which may also contain PII.

## 3. Ingestion Approach (Batch / CDC / Streaming)
Given the dataset profile and business requirements, a **Batch ingestion approach** is recommended. This approach is suitable due to:
- The manageable size of the dataset (1034 rows).
- The requirement for daily dashboards, which aligns well with batch processing.
- Simplicity in implementation and maintenance compared to CDC or streaming for this dataset.

## 4. AWS Services & Components
The following AWS services will be utilized for the ingestion strategy:
- **Amazon S3**: For data storage and landing zone.
- **AWS Glue**: For ETL processes, schema management, and data cataloging.
- **AWS Lambda**: For serverless processing and triggering ETL jobs.
- **Amazon EventBridge**: To schedule and trigger ingestion workflows.
- **AWS Identity and Access Management (IAM)**: For managing access and permissions, especially concerning PII.

## 5. Load Frequency & Scheduling
The ingestion frequency will be set to **daily**, with a scheduled job running during off-peak hours (e.g., 2 AM UTC) to minimize impact on system performance. This aligns with the need for daily dashboards and allows for adequate processing time.

## 6. Data Landing & File Formats
Data will be landed in **Amazon S3** in **Parquet format** due to its efficient storage and query performance. The landing zone structure will be organized as follows:
```
s3://your-bucket-name/landing/
    ├── employee/
    │   ├── year=2023/
    │   │   ├── month=10/
    │   │   │   ├── day=01/
    │   │   │   │   └── employee_data.parquet
```
This structure allows for easy partitioning and querying.

## 7. Idempotency, Deduplication & Backfills
To ensure idempotency and deduplication:
- Use a composite key formed by `First Name`, `Last Name`, and `Age` to identify unique records.
- Implement a deduplication step in the ETL process to filter out duplicate records based on the composite key.
- For backfills, maintain a versioning strategy in S3 to allow reprocessing of historical data without overwriting current datasets.

## 8. Failure Handling & Retries
Failure handling will be implemented through:
- **AWS Lambda**: Automatically retries failed ETL jobs up to three times with exponential backoff.
- **AWS CloudWatch**: Monitor and alert on failures, allowing for manual intervention if necessary.
- Error logs will be stored in S3 for troubleshooting and auditing.

## 9. SLAs & Freshness Guarantees
The SLAs for this ingestion strategy include:
- Data availability within **24 hours** of the last ingestion.
- Data freshness guarantees ensuring that the dashboards reflect the most recent data from the previous day’s ingestion.

## 10. Risks & Tradeoffs
### Risks:
- **Data Quality**: Potential issues if constraints are not enforced during data entry.
- **PII Management**: Risks associated with handling personal data, necessitating strict compliance with data governance policies.
- **Schema Evolution**: Changes in business requirements may lead to frequent updates in the schema, risking backward compatibility.

### Tradeoffs:
- **Batch vs. Real-Time**: While batch processing is simpler and sufficient for daily dashboards, it may not support near-real-time analytics if business needs evolve.
- **Cost vs. Performance**: Using services like AWS Glue and Lambda incurs costs, but they provide scalability and ease of use compared to self-managed solutions.

This ingestion strategy aims to provide a robust, scalable, and compliant framework for managing the e-commerce analytics dataset effectively.
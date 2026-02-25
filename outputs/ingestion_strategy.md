# Data Ingestion Strategy for MLB Analysis

## 1. Overview
This document outlines the data ingestion strategy for a dataset containing employee information relevant to an MLB team. The goal is to establish a robust, production-grade ingestion pipeline on AWS that ensures data integrity, consistency, and compliance with business requirements while enabling efficient analysis of the MLB season.

## 2. Ingestion Sources
The primary ingestion source will be a CSV file containing employee data. This dataset includes personal and demographic information, which may contain PII (Personally Identifiable Information). The dataset profile indicates that it is relatively small (1034 rows, 7 columns) and free of null values, making it suitable for both batch and near-real-time ingestion approaches.

## 3. Ingestion Approach (Batch / CDC / Streaming)
Given the dataset size and the nature of the data, a **Batch ingestion approach** is recommended. This approach is suitable as the dataset does not require real-time updates and can be processed periodically without significant latency concerns. 

## 4. AWS Services & Components
To implement the ingestion strategy, the following AWS services will be utilized:
- **Amazon S3**: For storing the raw CSV files and processed data.
- **AWS Glue**: For ETL (Extract, Transform, Load) operations to clean and prepare the data for analysis.
- **AWS Lambda**: To trigger processing jobs based on events (e.g., new files uploaded to S3).
- **Amazon EventBridge**: To schedule ingestion jobs and manage event-driven workflows.

## 5. Load Frequency & Scheduling
The ingestion frequency will be set to **daily**. A scheduled job will run every 24 hours to check for new data files in the designated S3 bucket. This frequency aligns with the business requirement to analyze the MLB season without the need for real-time data.

## 6. Data Landing & File Formats
- **Landing Zone**: Raw CSV files will be stored in an S3 bucket (e.g., `s3://mlb-team-data/raw/`).
- **Processed Data**: After ETL, the cleaned data will be stored in a separate S3 bucket (e.g., `s3://mlb-team-data/processed/`).
- **File Format**: The raw data will remain in CSV format for initial ingestion, while processed data can be converted to Parquet format for optimized storage and query performance.

## 7. Idempotency, Deduplication & Backfills
- **Idempotency**: The ingestion process will be designed to be idempotent, meaning that reprocessing the same file will not result in duplicate records. This can be achieved by checking for existing records based on the composite key (first_name, last_name) before inserting new records.
- **Deduplication**: During the ETL process, any duplicates identified based on the composite key will be removed.
- **Backfills**: If historical data needs to be ingested, a separate backfill process can be implemented to load older datasets without affecting the daily ingestion pipeline.

## 8. Failure Handling & Retries
- **Failure Handling**: If an ingestion job fails, an alert will be sent via Amazon SNS (Simple Notification Service) to notify the data engineering team.
- **Retries**: The ingestion job will be retried up to three times with exponential backoff in case of transient errors (e.g., network issues).
- **Reprocessing**: Failed records will be logged, and a separate process will be created to reprocess these records after resolving the underlying issues.

## 9. SLAs & Freshness Guarantees
- **SLA**: The ingestion process will have a Service Level Agreement (SLA) of 99.9% uptime, ensuring that data is ingested daily without significant delays.
- **Freshness Guarantees**: Data will be considered fresh if ingested within 24 hours of the latest available data. The daily ingestion schedule will ensure that data is updated regularly.

## 10. Risks & Tradeoffs
- **Risks**:
  - **Data Collisions**: The composite primary key (first_name, last_name) may lead to collisions, especially for common names, which could affect data integrity.
  - **PII Compliance**: Handling PII data requires adherence to regulations (e.g., GDPR, CCPA), which may introduce additional complexity in data processing and storage.
  - **Dependency on External Sources**: Any changes to the format or availability of the CSV files could disrupt the ingestion process.

- **Tradeoffs**:
  - While batch ingestion is simpler and sufficient for the current dataset size, it may not scale well if the volume of data increases significantly in the future.
  - The choice of CSV format for raw data is user-friendly but may not be as efficient as binary formats like Parquet for large datasets.

This strategy provides a comprehensive framework for ingesting and processing employee data for MLB analysis, ensuring data quality and compliance while being adaptable to future requirements.
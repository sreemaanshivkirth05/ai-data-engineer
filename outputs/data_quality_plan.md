# Data Quality Strategy for MLB Employee Data Pipeline

## 1. Data Quality Goals
The primary goals for ensuring data quality in the MLB employee data pipeline are:
- **Completeness**: Ensure all required fields are populated without null values.
- **Uniqueness**: Guarantee that each employee is uniquely identified, preventing duplicate entries.
- **Validity**: Validate that all data adheres to defined constraints (e.g., acceptable ranges for height, weight, and age).
- **Consistency**: Maintain consistent data across different datasets and versions.
- **Timeliness**: Ensure data is up-to-date and reflects the latest information.

## 2. Critical Tables & Columns
### Critical Tables
- **Fact Table**: `fact_employee`
- **Dimension Tables**: 
  - `dim_team`
  - `dim_position`

### Critical Columns
- **Fact Table**: 
  - `employee_id` (INT, PK)
  - `first_name` (STRING, PII)
  - `last_name` (STRING, PII)
  - `team_id` (INT, FK)
  - `position_id` (INT, FK)
  - `height_inches` (INT)
  - `weight_pounds` (INT)
  - `age` (FLOAT)
  - `record_date` (DATE)

- **Dimension Tables**:
  - `dim_team`: `team_id`, `team_name`, `league`
  - `dim_position`: `position_id`, `position_name`

## 3. Validation Rules & Checks
### Completeness Checks
- Ensure that all columns in the `fact_employee` table are populated (0% null values).
- Validate that `team_id` and `position_id` in the `fact_employee` table correspond to existing records in `dim_team` and `dim_position`.

### Uniqueness Checks
- Implement a check to ensure that the combination of `first_name` and `last_name` is unique before inserting records into the `fact_employee` table.
- Use `employee_id` as the primary key to prevent duplicate entries.

### Validity Checks
- **Height Check**: Ensure `height_inches` is between 67 and 83.
- **Weight Check**: Ensure `weight_pounds` is between 150 and 290.
- **Age Check**: Ensure `age` is between 21 and 48.
- Validate that `record_date` is not a future date.

### Consistency Checks
- Ensure that `team` and `position` values in the raw data match the corresponding values in `dim_team` and `dim_position` respectively.
- Check for consistent naming conventions across datasets.

## 4. Freshness & SLA Definitions
### Freshness Expectations
- Data should be ingested and processed daily, with the latest data available by 6 AM UTC each day.
- The `record_date` field in the `fact_employee` table should reflect the date of the latest data snapshot.

### SLA Definitions
- **Data Ingestion SLA**: 99% of data ingestion jobs should complete successfully within 30 minutes of the scheduled time.
- **Data Quality SLA**: 95% of records should pass all validation checks on the first attempt.
- **Data Availability SLA**: 99.9% uptime for accessing the processed data in the Silver and Gold layers.

## 5. Monitoring & Alerting Strategy
### Monitoring
- Utilize Apache Airflow's built-in monitoring capabilities to track the success and failure of each task in the DAG.
- Implement data quality checks as part of the ETL process using AWS Glue, logging results to a centralized logging system (e.g., AWS CloudWatch).

### Alerting
- Integrate Amazon SNS to send notifications for:
  - Task failures in Airflow.
  - SLA breaches for data ingestion and quality checks.
  - Data validation failures (e.g., records failing completeness or validity checks).

### Dashboard
- Create a monitoring dashboard using Grafana or AWS CloudWatch to visualize:
  - Data ingestion success rates.
  - Data quality check results.
  - SLA compliance metrics.

## 6. Failure Handling & Remediation
### Failure Handling
- Implement retry logic in Airflow for transient failures during data ingestion and processing.
- If data quality checks fail, log the errors and alert the data engineering team via SNS.

### Remediation Steps
- For ingestion failures, review error logs to identify issues (e.g., malformed CSV files) and correct them.
- For validation failures, flag erroneous records for manual review and correction.
- Implement a feedback loop to improve data quality checks based on failure patterns observed.

## 7. Assumptions & Risks
### Assumptions
- The data sources will consistently provide data in the expected format and structure.
- The team will adhere to data governance policies regarding PII handling and compliance.

### Risks
- **Data Collisions**: The reliance on `first_name` and `last_name` for uniqueness may lead to collisions; hence the introduction of `employee_id` mitigates this risk.
- **Data Quality**: Inconsistent data from source systems may lead to validation failures.
- **Regulatory Compliance**: Failure to comply with PII regulations could result in legal repercussions.

This data quality strategy is designed to ensure that the MLB employee data pipeline maintains high data integrity, enabling accurate and reliable analytics for decision-making.
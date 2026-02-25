# Data Orchestration and Scheduling for MLB Employee Data Platform

## 1. Overview
This document outlines the orchestration and scheduling design for the production data platform dedicated to ingesting, processing, and analyzing employee data for an MLB team. The design leverages AWS services and follows a structured approach to ensure data quality, reliability, and compliance with business requirements.

## 2. Orchestration Tool Choice
For this data platform, **Apache Airflow** is chosen as the orchestration tool due to its flexibility, rich scheduling capabilities, and strong community support. Airflow allows for defining complex workflows as Directed Acyclic Graphs (DAGs), making it suitable for managing the ingestion and processing of the employee dataset.

## 3. DAG / Workflow Design
The DAG will consist of the following key tasks:
- **Task 1: Ingest Raw Data** - Load CSV files from the S3 landing zone into the Bronze layer.
- **Task 2: ETL Process** - Execute AWS Glue jobs to clean, deduplicate, and transform the data into the Silver layer.
- **Task 3: Load Processed Data** - Store the transformed data in Parquet format in the Silver layer.
- **Task 4: Aggregate Data** - Run scheduled jobs to create summary tables and metrics in the Gold layer.
- **Task 5: Notify on Failure** - Send notifications via Amazon SNS if any task fails.

```python
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.operators.dummy_operator import DummyOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'data_engineer',
    'depends_on_past': False,
    'start_date': datetime(2023, 10, 1),
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

dag = DAG('mlb_employee_data_pipeline', default_args=default_args, schedule_interval='@daily')

start = DummyOperator(task_id='start', dag=dag)

ingest_raw_data = PythonOperator(task_id='ingest_raw_data', python_callable=ingest_raw_data_function, dag=dag)
etl_process = PythonOperator(task_id='etl_process', python_callable=etl_process_function, dag=dag)
load_processed_data = PythonOperator(task_id='load_processed_data', python_callable=load_processed_data_function, dag=dag)
aggregate_data = PythonOperator(task_id='aggregate_data', python_callable=aggregate_data_function, dag=dag)
notify_failure = PythonOperator(task_id='notify_failure', python_callable=notify_failure_function, dag=dag)

start >> ingest_raw_data >> etl_process >> load_processed_data >> aggregate_data
```

## 4. Task Dependencies
The tasks are structured in a linear fashion, where each task depends on the successful completion of the previous task:
- **Ingest Raw Data** → **ETL Process** → **Load Processed Data** → **Aggregate Data**
- **Notify on Failure** is a separate task that can be triggered by any task failure.

## 5. Scheduling & SLAs
- **Scheduling**: The DAG is scheduled to run **daily** at a specified time (e.g., midnight) to align with the ingestion frequency.
- **SLAs**: Each task will have an SLA of 2 hours, ensuring that data is processed and available for analysis within this timeframe. If any task exceeds this duration, an alert will be triggered.

## 6. Retries, Backfills & Recovery
- **Retries**: Each task will be retried up to three times with an exponential backoff strategy in case of transient errors.
- **Backfills**: In the event of historical data needing to be ingested, a backfill mechanism will be implemented to allow for re-running the DAG for specific dates.
- **Recovery**: Failed tasks will log the error details, and a separate recovery process will be initiated to handle reprocessing of failed records.

## 7. Monitoring & Observability
- **Monitoring Hooks**: Airflow's built-in monitoring capabilities will be utilized to track task execution times, success rates, and failure counts.
- **Alerts**: Integration with Amazon SNS will be set up to send alerts to the data engineering team in case of task failures or SLA breaches.
- **Dashboard**: A monitoring dashboard will be created using tools like Grafana or AWS CloudWatch to visualize the health of the data pipeline.

## 8. Risks & Tradeoffs
- **Data Collisions**: The composite key may lead to data integrity issues if not managed properly during the ETL process.
- **PII Compliance**: Handling PII data requires strict adherence to compliance regulations, which may complicate the ingestion and processing workflows.
- **Tool Complexity**: While Airflow provides powerful orchestration capabilities, it may introduce complexity in setup and maintenance, requiring skilled personnel to manage the environment.

This orchestration and scheduling design aims to provide a robust framework for the MLB employee data platform, ensuring data quality, reliability, and compliance while facilitating efficient analysis of the MLB season.
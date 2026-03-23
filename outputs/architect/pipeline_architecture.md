
DATA PIPELINE ARCHITECTURE

Data Sources
------------
Business data sources defined by requirements.

Ingestion Layer
---------------
Batch ingestion via Airflow or streaming via Kafka depending on source requirements.

Processing Layer
----------------
Transformations and data validation.

Storage Layer
-------------
Bronze / Silver / Gold architecture using a lakehouse design on AWS.

Orchestration
-------------
Airflow DAG orchestration with monitoring, retries, and backfills.

Serving Layer
-------------
Data warehouse or analytics layer.

Monitoring
----------
Logging, data quality checks, alerts.

class PipelineArchitectAgent:

    def run(self, context):

        requirements = context.get("requirements_analysis", "")
        ingestion = context.get("ingestion_strategy", "")
        storage = context.get("storage_layout", "")
        orchestration = context.get("orchestration", "")

        architecture = f"""
DATA PIPELINE ARCHITECTURE

Data Sources
------------
Business data sources defined by requirements.

Ingestion Layer
---------------
{ingestion}

Processing Layer
----------------
Transformations and data validation.

Storage Layer
-------------
{storage}

Orchestration
-------------
{orchestration}

Serving Layer
-------------
Data warehouse or analytics layer.

Monitoring
----------
Logging, data quality checks, alerts.
"""

        return {
            "markdown": architecture
        }
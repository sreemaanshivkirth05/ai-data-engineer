flowchart TD
    subgraph DataSources
        A1[CRM]
        A2[ERP]
        A3[Web Analytics]
        A4[Social Media]
    end

    subgraph IngestionLayer
        B1[Batch Ingestion]
        B2[Streaming Ingestion]
    end

    subgraph StorageLayer
        subgraph Bronze
            C1[Raw Data]
        end
        subgraph Silver
            C2[Cleaned Data]
            C3[Transformed Data]
        end
        subgraph Gold
            C4[Curated Data]
        end
    end

    subgraph Orchestration
        D1[Airflow DAG]
    end

    subgraph Governance
        E1[Data Quality Checks]
        E2[Access Control]
        E3[Audit Logging]
    end

    subgraph Analytics
        F1[BI Dashboards]
        F2[Ad-hoc Analysis]
    end

    A1 -->|Ingest| B1
    A2 -->|Ingest| B1
    A3 -->|Ingest| B2
    A4 -->|Ingest| B2

    B1 --> C1
    B2 --> C1

    C1 -->|Clean| C2
    C2 -->|Transform| C3
    C3 -->|Curate| C4

    D1 --> C1
    D1 --> C2
    D1 --> C3

    C4 --> F1
    C4 --> F2

    C1 --> E1
    C2 --> E1
    C3 --> E1
    C1 --> E2
    C2 --> E2
    C3 --> E2
    C1 --> E3
    C2 --> E3
    C3 --> E3
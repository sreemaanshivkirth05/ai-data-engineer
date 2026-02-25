flowchart TD
    subgraph DataSources
        A1[Player Dataset]
        A2[Game Dataset]
        A3[Team Dataset]
        A4[Injury Reports]
    end

    subgraph IngestionLayer
        B1[Batch Ingestion]
        B2[Amazon S3]
        B3[AWS Glue]
        B4[AWS Lambda]
        B5[Amazon EventBridge]
    end

    subgraph StorageLayers
        subgraph BronzeLayer
            C1[Raw Data]
            C2[CSV Format]
        end
        subgraph SilverLayer
            D1[Cleaned Data]
            D2[Parquet Format]
        end
        subgraph GoldLayer
            E1[Aggregated Data]
            E2[Data Warehouse]
        end
    end

    subgraph Orchestration
        F1[Apache Airflow]
        F2[Scheduled Jobs]
    end

    subgraph DataQualityGovernance
        G1[Data Quality Checks]
        G2[Access Control]
        G3[Audit Logging]
    end

    subgraph AnalyticsBI
        H1[Dashboards]
        H2[Reports]
        H3[Ad-hoc Analysis]
    end

    A1 -->|Ingest| B1
    A2 -->|Ingest| B1
    A3 -->|Ingest| B1
    A4 -->|Ingest| B1

    B1 -->|Store| B2
    B2 -->|Process| B3
    B3 -->|Trigger| B4
    B4 -->|Schedule| B5

    B2 -->|Store| C1
    C1 -->|Transform| B3
    B3 -->|Store| D1
    D1 -->|Aggregate| E1
    E1 -->|Store| E2

    F1 -->|Manage| B1
    F1 -->|Manage| B3
    F1 -->|Manage| E1

    G1 -->|Ensure| D1
    G2 -->|Control| E2
    G3 -->|Log| E2

    E2 -->|Visualize| H1
    E2 -->|Generate| H2
    E2 -->|Explore| H3

    style DataSources fill:#f9f,stroke:#333,stroke-width:2px
    style IngestionLayer fill:#ccf,stroke:#333,stroke-width:2px
    style StorageLayers fill:#cfc,stroke:#333,stroke-width:2px
    style Orchestration fill:#fcf,stroke:#333,stroke-width:2px
    style DataQualityGovernance fill:#ffc,stroke:#333,stroke-width:2px
    style AnalyticsBI fill:#cff,stroke:#333,stroke-width:2px
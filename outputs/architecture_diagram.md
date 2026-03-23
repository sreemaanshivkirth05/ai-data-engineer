flowchart TD
    subgraph DataSources
        A1[Orders Table]
        A2[Customers Table]
        A3[Order Items Table]
        A4[Products Table]
    end

    subgraph IngestionLayer
        B1[Batch Ingestion]
        B2[CDC Ingestion]
    end

    subgraph StorageLayer
        subgraph BronzeLayer
            C1[Raw Data]
        end
        subgraph SilverLayer
            C2[Processed Data]
        end
        subgraph GoldLayer
            C3[Aggregated Data]
        end
    end

    subgraph Orchestration
        D1[Apache Airflow]
    end

    subgraph DataQualityGovernance
        E1[Data Quality Checks]
        E2[Data Governance]
    end

    subgraph AnalyticsBI
        F1[Sales Dashboard]
        F2[Customer Insights]
        F3[Inventory Alerts]
        F4[Marketing Attribution]
    end

    A1 -->|Ingests| B1
    A2 -->|Ingests| B1
    A3 -->|Ingests| B1
    A4 -->|Ingests| B1

    A1 -->|CDC| B2
    A2 -->|CDC| B2

    B1 --> C1
    B2 --> C1
    C1 --> C2
    C2 --> C3

    C3 --> D1
    D1 --> E1
    D1 --> E2

    C3 --> F1
    C3 --> F2
    C3 --> F3
    C3 --> F4

    style DataSources fill:#f9f,stroke:#333,stroke-width:2px;
    style IngestionLayer fill:#bbf,stroke:#333,stroke-width:2px;
    style StorageLayer fill:#bfb,stroke:#333,stroke-width:2px;
    style Orchestration fill:#ffb,stroke:#333,stroke-width:2px;
    style DataQualityGovernance fill:#fbf,stroke:#333,stroke-width:2px;
    style AnalyticsBI fill:#ff9,stroke:#333,stroke-width:2px;
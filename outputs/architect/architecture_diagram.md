```mermaid
flowchart LR
  %% =========================
  %% Data Platform Architecture
  %% =========================

  subgraph S[Sources]
    S1[Operational Databases]
    S2[SaaS Applications]
    S3[Files / SFTP / APIs]
    S4[Event Producers / IoT / Apps]
  end

  subgraph I[Ingestion]
    I1[Batch Ingestion\n(Airflow)]
    I2[Streaming Ingestion\n(Kafka)]
  end

  subgraph O[Orchestration & Monitoring]
    O1[Airflow DAGs]
    O2[Retries / Backfills]
    O3[Monitoring & Alerting]
  end

  subgraph L[Lakehouse Storage on AWS]
    L1[Bronze\nRaw Landing Zone]
    L2[Silver\nCleansed / Conformed]
    L3[Gold\nCurated / Business Ready]
  end

  subgraph W[Warehouse]
    W1[Analytics Warehouse]
  end

  subgraph B[BI & Analytics]
    B1[BI Dashboards]
    B2[Analytics Users]
    B3[Data Science / Ad Hoc SQL]
  end

  S1 --> I1
  S2 --> I1
  S3 --> I1
  S4 --> I2

  O1 -. orchestrates .-> I1
  O1 -. orchestrates .-> I2
  O2 -. supports .-> O1
  O3 -. observes .-> O1
  O3 -. observes .-> I1
  O3 -. observes .-> I2
  O3 -. observes .-> L1
  O3 -. observes .-> L2
  O3 -. observes .-> L3

  I1 --> L1
  I2 --> L1
  L1 --> L2
  L2 --> L3
  L3 --> W1

  W1 --> B1
  W1 --> B2
  W1 --> B3

  classDef source fill:#f8f9fa,stroke:#6c757d,color:#212529;
  classDef ingest fill:#e7f5ff,stroke:#339af0,color:#0b2e4f;
  classDef orchestration fill:#fff4e6,stroke:#f08c00,color:#5c3d00;
  classDef storage fill:#e6fcf5,stroke:#12b886,color:#0b3d2e;
  classDef warehouse fill:#f3f0ff,stroke:#7950f2,color:#2f1f66;
  classDef bi fill:#fff0f6,stroke:#d6336c,color:#5c1a31;

  class S1,S2,S3,S4 source;
  class I1,I2 ingest;
  class O1,O2,O3 orchestration;
  class L1,L2,L3 storage;
  class W1 warehouse;
  class B1,B2,B3 bi;
```
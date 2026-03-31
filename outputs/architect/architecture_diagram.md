```mermaid
flowchart LR
  %% =========================
  %% Sources
  %% =========================
  subgraph S[Data Sources]
    S1[Operational Databases]
    S2[SaaS Applications]
    S3[Files / SFTP]
    S4[IoT / Event Streams]
    S5[External APIs]
  end

  %% =========================
  %% Ingestion
  %% =========================
  subgraph I[Ingestion]
    I1[Batch Ingestion\n(Airflow)]
    I2[Streaming Ingestion\n(Kafka)]
  end

  %% =========================
  %% Orchestration / Monitoring
  %% =========================
  subgraph O[Orchestration & Monitoring]
    O1[Airflow DAGs]
    O2[Retries / Backfills]
    O3[Monitoring & Alerting]
  end

  %% =========================
  %% Storage Layers
  %% =========================
  subgraph L[Lakehouse Storage on AWS]
    L1[Bronze\nRaw Landing Zone]
    L2[Silver\nCleansed / Conformed]
    L3[Gold\nCurated / Business Ready]
  end

  %% =========================
  %% Warehouse / BI
  %% =========================
  subgraph W[Analytics Serving]
    W1[Warehouse / SQL Serving Layer]
    W2[BI Dashboards]
    W3[Analytics Users]
  end

  %% =========================
  %% Flows
  %% =========================
  S1 --> I1
  S2 --> I1
  S3 --> I1
  S5 --> I1
  S4 --> I2

  I1 --> L1
  I2 --> L1

  L1 --> L2 --> L3 --> W1
  W1 --> W2
  W1 --> W3

  %% =========================
  %% Orchestration links
  %% =========================
  O1 -. orchestrates .-> I1
  O1 -. orchestrates .-> I2
  O1 -. manages .-> O2
  O1 -. observes .-> O3
  O3 -. monitors .-> I1
  O3 -. monitors .-> I2
  O3 -. monitors .-> L1
  O3 -. monitors .-> L2
  O3 -. monitors .-> L3
  O3 -. monitors .-> W1
```
flowchart LR
  %% Sources
  subgraph S[Data Sources]
    DB[(Transactional DBs)]
    CSV[CSV Uploads]
    API[Marketing APIs]
    WEB[Web Events]
  end

  %% Ingestion
  subgraph I[Ingestion Layer]
    AF[Airflow Ingest]
    KAF[Kafka Stream]
    SEC[Secrets Manager]
  end

  %% Lakehouse Storage
  subgraph L[Lakehouse on AWS]
    subgraph B[Bronze]
      BR[(Raw Landing)]
      BQ[Quarantine]
    end
    subgraph SL[Silver]
      ST[Standardize]
      DQ[Validate & Dedupe]
      PII[Tokenize / Mask PII]
      SM[(Curated Silver)]
      IDM[(Identity Map)]
    end
    subgraph G[Gold]
      AGG[BI Views]
      SEM[Semantic Layer]
      FEAT[Feature Sets]
      GD[(Gold Datasets)]
    end
  end

  %% Orchestration
  subgraph O[Orchestration]
    DAG[Airflow DAGs]
    MON[Monitoring / Retries / Backfills]
  end

  %% Governance
  subgraph GRC[Data Quality / Governance]
    CAT[Glue Catalog]
    LF[Lake Formation]
    AUD[CloudTrail / Audit Logs]
    KMS[KMS Encryption]
    RLS[RBAC / Row-Column Security]
  end

  %% Consumption
  subgraph C[Analytics / BI Consumption]
    BI[BI Dashboards]
    ADHOC[Analysts]
    LEAD[Leadership Realtime]
    ML[ML / Forecasting]
  end

  %% Flows
  DB --> AF
  CSV --> AF
  API --> AF
  WEB --> KAF

  SEC --> AF
  SEC --> KAF

  AF --> BR
  KAF --> BR

  BR --> BQ
  BR --> DAG

  DAG --> ST
  DAG --> DQ
  DAG --> PII

  ST --> SM
  DQ --> SM
  PII --> SM
  SM --> IDM

  SM --> GD
  IDM --> GD
  GD --> AGG
  GD --> SEM
  GD --> FEAT

  AGG --> BI
  SEM --> BI
  AGG --> ADHOC
  SEM --> LEAD
  FEAT --> ML

  DAG --> MON
  DAG --> CAT
  CAT --> LF
  LF --> RLS
  KMS --> BR
  KMS --> SM
  KMS --> GD
  AUD --> DAG
  AUD --> BI

  LF -. governs .-> BR
  LF -. governs .-> SM
  LF -. governs .-> GD
  RLS -. controls .-> BI
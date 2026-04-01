flowchart LR

subgraph SRC[Data Sources]
  Web[Website]
  Pay[Payments]
  Ord[Orders DB]
  Ship[Shipping]
  Mkt[Marketing]
end

subgraph ING[Ingestion]
  Kaf[Kafka\nStreaming]
  Air[Airflow\nBatch]
end

subgraph ORCH[Orchestration]
  DAG[Airflow DAGs\nMonitor • Retry • Backfill]
end

subgraph GOV[Governance & Security]
  Cat[Catalog / Lineage]
  DQ[Data Quality\nSchema • Nulls • Dups • Freshness]
  LF[Lake Formation\nRBAC • RLS • CLS]
  KMS[KMS / Secrets]
  Audit[CloudTrail / Logs]
end

subgraph LAKE[Lakehouse on AWS]
  Brz[Bronze\nRaw • Restricted • Immutable]
  Slv[Silver\nCleansed • Standardized\nMasked / Tokenized]
  Gld[Gold\nCurated • Aggregated\nLeast Privilege]
end

subgraph CONSUME[Analytics / BI]
  BI[BI Dashboards]
  Adhoc[Ad hoc Analysis]
  DS[Data Science / ML Features]
  Exec[Leadership Metrics]
end

Web --> Kaf
Pay --> Air
Ord --> Air
Ship --> Air
Mkt --> Air

Kaf --> DAG
Air --> DAG

DAG --> Brz
Brz --> DQ
DQ --> Slv
Slv --> DQ
DQ --> Gld

Brz --> Cat
Slv --> Cat
Gld --> Cat

LF --- Brz
LF --- Slv
LF --- Gld
KMS --- Brz
KMS --- Slv
KMS --- Gld
Audit --- DAG
Audit --- LF
Audit --- Cat

Gld --> BI
Gld --> Exec
Gld --> Adhoc
Slv --> DS
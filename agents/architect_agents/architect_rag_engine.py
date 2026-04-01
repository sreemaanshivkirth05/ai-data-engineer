"""
architect_rag_engine.py

RAG (Retrieval-Augmented Generation) engine for the Data Architect pipeline.

Flow:
  1. ArchitectResearchAgent  — searches the web for real-world architectures
                               matching the detected domain + business requirements.
  2. ArchitectKnowledgeBase  — curated in-memory library of reference architecture
                               patterns. No external vector DB needed — uses TF-IDF
                               cosine similarity for fast lightweight retrieval.
  3. RAGContextBuilder       — assembles the retrieved web findings + matched patterns
                               into a structured context block that each architect agent
                               prepends to its own prompt.

Usage (in architect_pipeline.py):
    from agents.architect_agents.architect_rag_engine import RAGContextBuilder

    rag = RAGContextBuilder(
        business_requirements=requirements,
        dataset_profile=profile,
        domain=detected_domain
    )
    rag_context = rag.build()   # Call once, reuse across all agents

    # Each agent receives rag_context and injects it into its prompt:
    #   self.rag_context = rag_context
    #   ... in _build_prompt(): f"{self.rag_context}\n\n{main_prompt}"
"""

import re
import math
import json
import time
from typing import Dict, Any, List, Optional
from collections import Counter

# Web search — uses the requests library (standard in most Python envs)
try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# 1. CURATED REFERENCE ARCHITECTURE KNOWLEDGE BASE
# ─────────────────────────────────────────────────────────────────────────────

REFERENCE_ARCHITECTURES = [
    {
        "id": "lambda_batch_streaming",
        "title": "Lambda Architecture — Batch + Speed Layer",
        "domains": ["ecommerce", "retail", "finance", "logistics", "iot"],
        "keywords": ["real-time", "streaming", "batch", "lambda", "speed layer",
                     "kafka", "kinesis", "historical", "low latency"],
        "pattern": """
REFERENCE PATTERN: Lambda Architecture (Batch + Speed Layer)
Source: Nathan Marz, widely adopted in e-commerce and finance.

Layers:
- Batch Layer: Hadoop/Spark on S3, recomputes views over all historical data nightly.
- Speed Layer: Kafka/Kinesis + Flink/Spark Streaming for sub-minute latency.
- Serving Layer: Merged views from both layers exposed via Presto/Redshift.

Best for: When you need both historical accuracy AND real-time dashboards.
Trade-off: Maintaining two codebases (batch + streaming) adds complexity.

Real-world examples: Netflix content recommendations, LinkedIn feed ranking,
Twitter analytics, Amazon order tracking.

Key services: Apache Kafka, Apache Flink, AWS Kinesis Data Streams,
AWS Glue (batch), Amazon Redshift (serving), Apache Iceberg (storage).
""",
        "cost_range": "$500–$5,000/month depending on throughput",
        "complexity": "high"
    },
    {
        "id": "kappa_streaming_only",
        "title": "Kappa Architecture — Streaming-Only",
        "domains": ["iot", "fintech", "telecommunications", "gaming", "logistics"],
        "keywords": ["streaming only", "event driven", "kafka", "flink", "kappa",
                     "reprocessing", "real-time only", "immutable log"],
        "pattern": """
REFERENCE PATTERN: Kappa Architecture (Streaming-Only)
Source: Jay Kreps (LinkedIn/Confluent).

Principle: Everything is a stream. Batch is just a special case of streaming.
Use a single processing codebase with a replayable immutable event log.

Layers:
- Immutable Log: Apache Kafka (retain events indefinitely for reprocessing).
- Stream Processor: Apache Flink or Spark Structured Streaming.
- Serving: Materialized views in a database or search index (Elasticsearch, DynamoDB).

Best for: Pure event-driven systems, IoT sensor data, clickstream analytics.
Trade-off: Reprocessing large history is expensive. Historical analytics harder.

Real-world: Uber's real-time driver-rider matching, Lyft's geospatial analytics,
Cloudflare DDoS detection.

Key services: Apache Kafka, Apache Flink, AWS MSK, Elasticsearch, Redis.
""",
        "cost_range": "$300–$3,000/month",
        "complexity": "medium-high"
    },
    {
        "id": "medallion_lakehouse",
        "title": "Medallion Architecture — Bronze / Silver / Gold Lakehouse",
        "domains": ["enterprise", "healthcare", "retail", "manufacturing",
                    "financial services", "analytics"],
        "keywords": ["medallion", "bronze", "silver", "gold", "lakehouse",
                     "delta lake", "iceberg", "databricks", "dbt", "dbt core",
                     "data quality", "incremental", "batch analytics"],
        "pattern": """
REFERENCE PATTERN: Medallion Lakehouse Architecture
Source: Databricks, widely adopted in enterprise analytics.

Layers:
- Bronze (Raw): Raw ingested data, append-only, no transformations.
  Storage: S3/ADLS in Parquet or Delta format. Partition by ingest date.
- Silver (Curated): Cleaned, validated, deduplicated, joined datasets.
  Transformations via dbt or Spark. Schema enforced. PII masked.
- Gold (Analytical): Business-level aggregations, KPIs, feature tables.
  Optimised for BI tools, served via Redshift/Snowflake/BigQuery.

Orchestration: Apache Airflow, AWS Step Functions, or Databricks Workflows.
Data Quality: Great Expectations / Soda Core checks between layers.

Best for: Enterprise analytics, regulatory environments, multi-team data sharing.
Trade-off: Higher latency (batch), more storage overhead.

Real-world: Comcast data platform, HSBC risk analytics, Walmart inventory.

Key services: AWS S3, Apache Iceberg/Delta Lake, dbt, Apache Airflow,
Amazon Redshift / Snowflake, Great Expectations.
""",
        "cost_range": "$200–$2,000/month for small-medium scale",
        "complexity": "medium"
    },
    {
        "id": "data_mesh",
        "title": "Data Mesh — Federated Domain Ownership",
        "domains": ["large enterprise", "microservices", "multi-team", "platform"],
        "keywords": ["data mesh", "domain ownership", "data product", "federated",
                     "self-serve", "multiple teams", "decentralized", "platform team"],
        "pattern": """
REFERENCE PATTERN: Data Mesh
Source: Zhamak Dehghani (ThoughtWorks).

Principles:
1. Domain Ownership: Each business domain owns its own data products.
2. Data as a Product: Data teams treat their outputs as products with SLAs.
3. Self-Serve Infrastructure: Central platform team provides reusable infrastructure.
4. Federated Governance: Interoperability standards enforced globally.

Architecture:
- Each domain has its own pipeline: ingest → transform → publish.
- Domain data products are registered in a central data catalog (DataHub, Atlan).
- Consumers discover and access via catalog + policy-based access control.

Best for: Large organisations with many distinct business domains.
Trade-off: Requires strong platform team. Governance is complex.

Real-world: JPMorgan Chase, Zalando, Netflix content metadata platform.

Key services: Apache Kafka, dbt, Terraform (IaC), DataHub / Atlan (catalog),
AWS Lake Formation (access control), Great Expectations (quality).
""",
        "cost_range": "$1,000–$10,000+/month (platform overhead is high)",
        "complexity": "very high"
    },
    {
        "id": "modern_cloud_dwh",
        "title": "Modern Cloud Data Warehouse (ELT Pattern)",
        "domains": ["saas", "startups", "b2b analytics", "marketing analytics",
                    "business intelligence", "small to medium"],
        "keywords": ["elt", "warehouse", "snowflake", "bigquery", "redshift",
                     "fivetran", "airbyte", "dbt", "business intelligence", "bi",
                     "simple", "startup", "small team"],
        "pattern": """
REFERENCE PATTERN: Modern Cloud Data Warehouse (ELT)
Source: Modern Data Stack movement (Fivetran, dbt, Snowflake era).

Pattern: Extract → Load → Transform (ELT not ETL).
Load raw data into warehouse first, then transform in-warehouse using dbt.

Components:
- Extraction: Fivetran / Airbyte / custom connectors → load to warehouse.
- Storage: Snowflake / BigQuery / Redshift as the single source of truth.
- Transformation: dbt Core or dbt Cloud for modelling and testing.
- Orchestration: dbt Cloud scheduler, Airflow, or Prefect.
- BI: Looker / Metabase / Tableau consuming dbt models.

Best for: Small-to-medium teams, fast iteration, strong SQL skills.
Trade-off: Costs scale with warehouse compute. Poor for unstructured data.

Real-world: Hundreds of B2B SaaS companies (HubSpot, Intercom analytics).

Key services: Fivetran/Airbyte, Snowflake/BigQuery, dbt, Looker/Metabase.
""",
        "cost_range": "$100–$1,500/month for typical SaaS analytics",
        "complexity": "low-medium"
    },
    {
        "id": "healthcare_hipaa",
        "title": "Healthcare / HIPAA-Compliant Data Platform",
        "domains": ["healthcare", "medical", "hospital", "clinical", "pharma",
                    "insurance", "patient"],
        "keywords": ["hipaa", "phi", "pii", "patient", "clinical", "ehr", "fhir",
                     "healthcare", "medical records", "de-identification"],
        "pattern": """
REFERENCE PATTERN: Healthcare HIPAA-Compliant Data Platform
Source: AWS Healthcare competency, Azure Healthcare APIs best practices.

Key Requirements: HIPAA compliance, PHI de-identification, audit trails.

Architecture:
- Ingestion: HL7 FHIR APIs, EDI feeds, EHR exports (encrypted at source).
- Landing: Encrypted S3 buckets with server-side encryption (SSE-KMS).
  VPC endpoints only — no public internet access.
- De-identification: AWS Comprehend Medical or custom NER to tag + mask PHI.
- Bronze: Raw encrypted data, access restricted to data engineering role only.
- Silver: De-identified / pseudonymised data. PHI replaced with tokens.
- Gold: Aggregated clinical metrics, population health dashboards.
- Access Control: AWS Lake Formation column-level security. MFA required.
- Audit: AWS CloudTrail + CloudWatch for all data access events.
- Compliance: Business Associate Agreement (BAA) with all cloud vendors.

Key services: AWS S3 (SSE-KMS), AWS Macie (PII detection), AWS Comprehend Medical,
AWS Lake Formation, AWS CloudTrail, Amazon HealthLake.
""",
        "cost_range": "$500–$5,000/month (compliance tooling adds cost)",
        "complexity": "high"
    },
    {
        "id": "financial_risk",
        "title": "Financial Services / Risk Analytics Platform",
        "domains": ["finance", "banking", "fintech", "trading", "risk", "insurance",
                    "investment", "compliance"],
        "keywords": ["financial", "banking", "risk", "trading", "regulatory",
                     "sox", "basel", "gdpr", "audit", "reconciliation", "ledger"],
        "pattern": """
REFERENCE PATTERN: Financial Services Risk Analytics Platform
Source: AWS Financial Services competency, industry white papers.

Key Requirements: Auditability, lineage, reconciliation, regulatory reporting.

Architecture:
- Ingestion: Market data feeds (FIX protocol), core banking system exports,
  transaction logs. Near-real-time via Kafka.
- Storage: Immutable append-only raw layer (cannot delete financial records).
  Delta Lake or Apache Iceberg for ACID compliance and time-travel queries.
- Transformation: Spark-based reconciliation jobs. dbt for reporting models.
- Lineage: Apache Atlas or DataHub to track every data transformation.
- Audit: Every query logged. Column-level access control via Lake Formation.
- Regulatory Reporting: Gold layer tables pre-built for SOX, Basel III reports.
- Disaster Recovery: Cross-region replication, 99.99% availability SLA.

Key services: Apache Kafka, Apache Iceberg, AWS S3, AWS Glue, Amazon Redshift,
Apache Atlas, AWS CloudTrail, AWS Config.
""",
        "cost_range": "$1,000–$10,000+/month",
        "complexity": "very high"
    },
    {
        "id": "retail_ecommerce",
        "title": "Retail / E-commerce Analytics Platform",
        "domains": ["retail", "ecommerce", "shopping", "inventory", "orders",
                    "customers", "products", "sales"],
        "keywords": ["retail", "ecommerce", "sales", "inventory", "orders",
                     "customer", "product", "basket", "churn", "recommendation"],
        "pattern": """
REFERENCE PATTERN: Retail / E-commerce Analytics Platform
Source: Amazon retail data team, Shopify data platform blog posts.

Use Cases: Sales reporting, inventory optimisation, customer segmentation,
recommendation systems, demand forecasting.

Architecture:
- Sources: Point-of-sale systems, website clickstream, inventory management,
  CRM, marketing platforms (Google Ads, Meta).
- Ingestion: Daily batch for transactional data; Kafka for clickstream events.
- Bronze: Raw orders, products, customers, events. Partitioned by event date.
- Silver: Unified customer view (identity resolution). Product master.
  Cleaned order lines. Sessionised clickstream.
- Gold: Customer LTV, product affinity, sales KPIs, inventory health.
- ML Features: Customer embeddings, purchase probability scores.
- BI: Looker / Tableau dashboards. Self-service analytics for business teams.

Key services: AWS S3, Apache Iceberg, dbt, Apache Airflow, Amazon Redshift,
Kafka (clickstream), SageMaker (ML features), Looker/Tableau.
""",
        "cost_range": "$300–$3,000/month",
        "complexity": "medium"
    }
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. LIGHTWEIGHT TF-IDF RETRIEVER
# ─────────────────────────────────────────────────────────────────────────────

class TFIDFRetriever:
    """
    Lightweight TF-IDF cosine similarity retriever.
    No external vector DB, no embeddings API — pure Python.
    Indexes the reference architecture knowledge base at init time.
    """

    def __init__(self, documents: List[Dict]):
        self.docs = documents
        self._build_index()

    def _tokenise(self, text: str) -> List[str]:
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        return [t for t in text.split() if len(t) > 2]

    def _build_index(self):
        """Build TF-IDF vectors for all documents."""
        # Combine all text fields per doc
        self.doc_texts = []
        for doc in self.docs:
            combined = " ".join([
                doc.get("title", ""),
                " ".join(doc.get("domains", [])),
                " ".join(doc.get("keywords", [])),
                doc.get("pattern", "")
            ])
            self.doc_texts.append(combined)

        # Build vocabulary and IDF
        tokenised = [self._tokenise(t) for t in self.doc_texts]
        vocab = set(t for tokens in tokenised for t in tokens)
        n = len(self.doc_texts)

        # IDF
        self.idf = {}
        for term in vocab:
            df = sum(1 for tokens in tokenised if term in tokens)
            self.idf[term] = math.log((n + 1) / (df + 1)) + 1

        # TF-IDF vectors
        self.vectors = []
        for tokens in tokenised:
            tf = Counter(tokens)
            total = max(len(tokens), 1)
            vec = {t: (tf[t] / total) * self.idf.get(t, 1) for t in tf}
            self.vectors.append(vec)

    def _cosine(self, vec_a: Dict, vec_b: Dict) -> float:
        common = set(vec_a) & set(vec_b)
        if not common:
            return 0.0
        dot = sum(vec_a[t] * vec_b[t] for t in common)
        norm_a = math.sqrt(sum(v**2 for v in vec_a.values()))
        norm_b = math.sqrt(sum(v**2 for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def retrieve(self, query: str, top_k: int = 2) -> List[Dict]:
        """Return top_k most similar reference architectures."""
        query_tokens = self._tokenise(query)
        if not query_tokens:
            return self.docs[:top_k]

        tf = Counter(query_tokens)
        total = max(len(query_tokens), 1)
        query_vec = {t: (tf[t] / total) * self.idf.get(t, 1)
                     for t in tf if t in self.idf}

        scores = [
            (i, self._cosine(query_vec, doc_vec))
            for i, doc_vec in enumerate(self.vectors)
        ]
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for i, score in scores[:top_k]:
            if score > 0.01:  # ignore near-zero matches
                results.append({**self.docs[i], "_score": round(score, 3)})

        return results


# ─────────────────────────────────────────────────────────────────────────────
# 3. WEB RESEARCH AGENT
# ─────────────────────────────────────────────────────────────────────────────

class ArchitectWebResearcher:
    """
    Searches the web for real-world architecture patterns matching the
    detected domain and business requirements.

    Uses DuckDuckGo Instant Answer API (free, no API key required) and
    a curated list of known architecture resource URLs as fallback.
    Falls back gracefully if network is unavailable.
    """

    DDG_URL = "https://api.duckduckgo.com/"
    TIMEOUT = 8

    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Search DuckDuckGo and return structured findings."""
        if not _REQUESTS_AVAILABLE:
            return []

        try:
            params = {
                "q": query,
                "format": "json",
                "no_html": "1",
                "skip_disambig": "1",
                "t": "architect_rag"
            }
            resp = requests.get(
                self.DDG_URL,
                params=params,
                timeout=self.TIMEOUT,
                headers={"User-Agent": "ArchitectRAG/1.0"}
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            results = []

            # Abstract (main result)
            abstract = data.get("Abstract", "").strip()
            abstract_source = data.get("AbstractSource", "")
            abstract_url = data.get("AbstractURL", "")
            if abstract:
                results.append({
                    "title": data.get("Heading", query),
                    "source": abstract_source,
                    "url": abstract_url,
                    "summary": abstract[:600]
                })

            # Related topics
            for topic in data.get("RelatedTopics", [])[:max_results]:
                if isinstance(topic, dict) and topic.get("Text"):
                    results.append({
                        "title": topic.get("Text", "")[:80],
                        "source": "DuckDuckGo",
                        "url": topic.get("FirstURL", ""),
                        "summary": topic.get("Text", "")[:400]
                    })

            return results[:max_results]

        except Exception:
            return []

    def research_domain(
        self,
        domain: str,
        requirements: str,
        top_queries: int = 2
    ) -> str:
        """
        Run targeted searches and return a formatted findings block.
        """
        queries = self._build_queries(domain, requirements)
        all_findings = []

        for q in queries[:top_queries]:
            findings = self.search(q)
            for f in findings:
                if f.get("summary"):
                    all_findings.append(f)
            time.sleep(0.3)  # polite rate limiting

        if not all_findings:
            return ""

        lines = ["## Web Research Findings\n"]
        for f in all_findings[:4]:
            lines.append(f"### {f.get('title', 'Reference')}")
            if f.get("source"):
                lines.append(f"*Source: {f['source']}*")
            lines.append(f.get("summary", ""))
            lines.append("")

        return "\n".join(lines)

    def _build_queries(self, domain: str, requirements: str) -> List[str]:
        """Build focused search queries from domain and requirements."""
        req_lower = requirements.lower()
        queries = []

        # Domain-specific architecture query
        if domain and domain != "unknown":
            queries.append(f"{domain} data platform architecture best practices 2024")

        # Technology-specific queries based on keywords in requirements
        tech_signals = {
            "real-time": "real-time streaming data architecture kafka flink",
            "stream": "streaming data pipeline architecture best practices",
            "hipaa": "HIPAA compliant data platform architecture AWS",
            "gdpr": "GDPR compliant data architecture design patterns",
            "machine learning": "ML feature store data platform architecture",
            "recommendation": "recommendation system data pipeline architecture",
            "financial": "financial data platform architecture regulatory compliance",
            "iot": "IoT data pipeline architecture time series",
            "analytics": "modern data stack analytics architecture dbt snowflake",
            "lakehouse": "lakehouse architecture delta lake iceberg best practices",
        }

        for signal, query in tech_signals.items():
            if signal in req_lower:
                queries.append(query)
                break

        # Generic fallback
        queries.append("modern data platform architecture patterns 2024")

        return queries


# ─────────────────────────────────────────────────────────────────────────────
# 4. DOMAIN DETECTOR
# ─────────────────────────────────────────────────────────────────────────────

class DomainDetector:
    """
    Detects the business domain from requirements text and dataset profile.
    Returns a normalised domain string used for retrieval and web search.
    """

    DOMAIN_SIGNALS = {
        "healthcare": ["patient", "clinical", "hospital", "ehr", "fhir", "medical",
                       "diagnosis", "treatment", "pharma", "health", "hipaa", "phi"],
        "finance": ["transaction", "payment", "banking", "trading", "risk", "loan",
                    "credit", "investment", "portfolio", "ledger", "reconciliation",
                    "sox", "basel", "regulatory", "compliance", "fintech"],
        "retail": ["order", "product", "inventory", "customer", "basket", "sku",
                   "purchase", "sales", "store", "ecommerce", "price", "discount"],
        "logistics": ["shipment", "delivery", "warehouse", "route", "carrier",
                      "freight", "supply chain", "tracking", "dispatch"],
        "iot": ["sensor", "device", "telemetry", "signal", "firmware", "mqtt",
                "time series", "machine", "equipment", "asset"],
        "telecommunications": ["subscriber", "call", "network", "churn", "plan",
                                "usage", "billing", "bandwidth", "mobile"],
        "hr": ["employee", "payroll", "hire", "headcount", "department", "salary",
               "performance", "attendance", "leave", "workforce"],
        "marketing": ["campaign", "impression", "click", "conversion", "lead",
                      "attribution", "channel", "cpa", "roas", "funnel"],
        "hospitality": ["booking", "reservation", "hotel", "room", "guest",
                        "checkin", "checkout", "occupancy", "rate"],
    }

    def detect(self, requirements: str, profile: Dict) -> str:
        """Return the most likely domain string."""
        text = requirements.lower()

        # Also include column names from profile
        columns = profile.get("columns", []) or []
        col_names = " ".join(
            str(c.get("name", "") if isinstance(c, dict) else c).lower()
            for c in columns
        )
        text = text + " " + col_names

        scores = {}
        for domain, signals in self.DOMAIN_SIGNALS.items():
            score = sum(1 for s in signals if s in text)
            if score > 0:
                scores[domain] = score

        if not scores:
            return "enterprise analytics"

        return max(scores, key=scores.get)


# ─────────────────────────────────────────────────────────────────────────────
# 5. RAG CONTEXT BUILDER — main entry point
# ─────────────────────────────────────────────────────────────────────────────

class RAGContextBuilder:
    """
    Assembles RAG context for all architect agents.

    Call .build() once at the start of the architect pipeline.
    Pass the returned string to each agent's constructor.

    Each agent injects it at the top of its prompt so the LLM
    reasons from real-world patterns before generating its output.
    """

    def __init__(
        self,
        business_requirements: str,
        dataset_profile: Dict,
        domain: Optional[str] = None,
        enable_web_search: bool = True
    ):
        self.requirements = business_requirements or ""
        self.profile = dataset_profile or {}
        self.enable_web_search = enable_web_search

        # Detect domain if not provided
        self.domain = domain or DomainDetector().detect(
            self.requirements, self.profile
        )

        # Build retriever
        self.retriever = TFIDFRetriever(REFERENCE_ARCHITECTURES)

        # Web researcher
        self.researcher = ArchitectWebResearcher()

    def build(self) -> str:
        """
        Build and return the complete RAG context block.
        This string is prepended to every architect agent's prompt.
        """
        query = f"{self.domain} {self.requirements}"

        # --- Retrieve reference patterns ---
        matched = self.retriever.retrieve(query, top_k=2)
        pattern_block = self._format_patterns(matched)

        # --- Web research ---
        web_block = ""
        if self.enable_web_search:
            try:
                web_block = self.researcher.research_domain(
                    domain=self.domain,
                    requirements=self.requirements
                )
            except Exception:
                web_block = ""

        # --- Assemble ---
        sections = [
            "=" * 70,
            "RAG CONTEXT — RETRIEVED ARCHITECTURE KNOWLEDGE",
            "=" * 70,
            f"\nDetected Business Domain: **{self.domain.upper()}**\n",
        ]

        if pattern_block:
            sections.append(pattern_block)

        if web_block:
            sections.append(web_block)

        sections += [
            "=" * 70,
            "INSTRUCTION TO LLM:",
            "Use the retrieved patterns and web findings above as grounding.",
            "Adapt them to the specific business requirements and dataset profile.",
            "Do NOT copy patterns verbatim — synthesise a tailored design.",
            "Cite which pattern you drew from when making design decisions.",
            "=" * 70,
            ""
        ]

        return "\n".join(sections)

    def _format_patterns(self, patterns: List[Dict]) -> str:
        if not patterns:
            return ""

        lines = ["## Retrieved Reference Architecture Patterns\n"]
        for p in patterns:
            score = p.get("_score", 0)
            lines.append(f"### {p['title']} (relevance: {score:.2f})")
            lines.append(f"**Complexity:** {p.get('complexity', 'unknown')} | "
                         f"**Est. cost:** {p.get('cost_range', 'unknown')}")
            lines.append(p.get("pattern", "").strip())
            lines.append("")

        return "\n".join(lines)

    def get_domain(self) -> str:
        return self.domain
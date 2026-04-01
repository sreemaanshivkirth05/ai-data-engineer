"""
architect_pipeline.py

RAG-enhanced Data Architecture Pipeline.

Flow:
  1. RAGContextBuilder  — detect domain, retrieve reference patterns,
                          search web for real-world architectures.
                          Produces a rag_context string passed to all agents.

  2. SchemaContractAgent    — data contract and canonical schema.
  3. IngestionStrategyAgent — batch/CDC/streaming ingestion design.
  4. StorageLayoutAgent     — Bronze/Silver/Gold or equivalent layering.
  5. OrchestrationAgent     — DAG design, scheduling, monitoring.
  6. SecurityGovernanceAgent— IAM, PII, encryption, compliance.
  7. CostEstimationAgent    — domain-aware monthly cost estimate.
  8. MermaidAIAgent         — architecture diagram from full context.

Each agent receives the RAG context at construction time and injects it
at the top of its prompt so the LLM reasons from real-world patterns.
"""

import time
from typing import Dict, Any, Optional

from agents.architect_agents.architect_rag_engine import RAGContextBuilder
from agents.architect_agents.schema_contract_agent import SchemaContractAgent
from agents.architect_agents.ingestion_strategy_agent import IngestionStrategyAgent
from agents.architect_agents.storage_layout_agent import StorageLayoutAgent
from agents.architect_agents.orchestration_agent import OrchestrationAgent
from agents.architect_agents.security_governance_agent import SecurityGovernanceAgent
from agents.architect_agents.cost_estimation_agent import CostEstimationAgent
from agents.architect_agents.mermaid_ai_agent import MermaidAIAgent


def run_architect_pipeline(
    business_requirements: str,
    dataset_profile: Optional[Dict[str, Any]] = None,
    enable_web_search: bool = True
) -> Dict[str, Any]:
    """
    Run the full RAG-enhanced architect pipeline.

    Args:
        business_requirements: Free-text description of what the data platform needs to do.
        dataset_profile: Optional dict from the DatasetProfilerAgent (row count, columns, etc.)
        enable_web_search: Whether to run live web search for architecture patterns.
                           Set False for offline / test environments.

    Returns:
        Dict with keys: domain, rag_context, data_contract, ingestion_strategy,
        storage_layout, orchestration, security_governance, cost_estimation,
        mermaid_diagram, pipeline_metadata
    """

    dataset_profile = dataset_profile or {}
    results = {}

    # ──────────────────────────────────────────────────────────────
    # STEP 1: RAG — Detect domain, retrieve patterns, search web
    # ──────────────────────────────────────────────────────────────
    print("🔍 [1/8] Building RAG context...")
    rag_builder = RAGContextBuilder(
        business_requirements=business_requirements,
        dataset_profile=dataset_profile,
        enable_web_search=enable_web_search
    )
    rag_context = rag_builder.build()
    detected_domain = rag_builder.get_domain()

    results["domain"] = detected_domain
    results["rag_context"] = rag_context

    print(f"   ✅ Domain detected: {detected_domain}")
    print(f"   ✅ RAG context built ({len(rag_context)} chars)")

    # Shared context dict passed to all agents
    shared_context: Dict[str, Any] = {
        "business_requirements": business_requirements,
        "dataset_profile": dataset_profile,
    }

    # ──────────────────────────────────────────────────────────────
    # STEP 2: Data Contract & Schema
    # ──────────────────────────────────────────────────────────────
    print("📋 [2/8] Running SchemaContractAgent...")
    try:
        schema_agent = SchemaContractAgent(
            dataset_profile=dataset_profile,
            rag_context=rag_context
        )
        schema_result = schema_agent.run()
        results["data_contract"] = schema_result.get("markdown", "")
        shared_context["data_contract"] = results["data_contract"]
        print("   ✅ Data contract done")
    except Exception as e:
        print(f"   ⚠️ SchemaContractAgent failed: {e}")
        results["data_contract"] = f"Schema contract generation failed: {e}"
        shared_context["data_contract"] = ""

    # ──────────────────────────────────────────────────────────────
    # STEP 3: Ingestion Strategy
    # ──────────────────────────────────────────────────────────────
    print("🔄 [3/8] Running IngestionStrategyAgent...")
    try:
        ingestion_agent = IngestionStrategyAgent(
            context=shared_context,
            rag_context=rag_context
        )
        ingestion_result = ingestion_agent.run()
        results["ingestion_strategy"] = ingestion_result.get("markdown", "")
        shared_context["ingestion_strategy"] = results["ingestion_strategy"]
        print("   ✅ Ingestion strategy done")
    except Exception as e:
        print(f"   ⚠️ IngestionStrategyAgent failed: {e}")
        results["ingestion_strategy"] = f"Ingestion strategy generation failed: {e}"
        shared_context["ingestion_strategy"] = ""

    # ──────────────────────────────────────────────────────────────
    # STEP 4: Storage Layout
    # ──────────────────────────────────────────────────────────────
    print("🪣 [4/8] Running StorageLayoutAgent...")
    try:
        storage_agent = StorageLayoutAgent(
            context=shared_context,
            rag_context=rag_context
        )
        storage_result = storage_agent.run()
        results["storage_layout"] = storage_result.get("markdown", "")
        shared_context["storage_layout"] = results["storage_layout"]
        print("   ✅ Storage layout done")
    except Exception as e:
        print(f"   ⚠️ StorageLayoutAgent failed: {e}")
        results["storage_layout"] = f"Storage layout generation failed: {e}"
        shared_context["storage_layout"] = ""

    # ──────────────────────────────────────────────────────────────
    # STEP 5: Orchestration
    # ──────────────────────────────────────────────────────────────
    print("⏱️ [5/8] Running OrchestrationAgent...")
    try:
        orchestration_agent = OrchestrationAgent(
            context=shared_context,
            rag_context=rag_context
        )
        orchestration_result = orchestration_agent.run()
        results["orchestration"] = orchestration_result.get("markdown", "")
        shared_context["orchestration"] = results["orchestration"]
        print("   ✅ Orchestration done")
    except Exception as e:
        print(f"   ⚠️ OrchestrationAgent failed: {e}")
        results["orchestration"] = f"Orchestration design failed: {e}"
        shared_context["orchestration"] = ""

    # ──────────────────────────────────────────────────────────────
    # STEP 6: Security & Governance
    # ──────────────────────────────────────────────────────────────
    print("🔒 [6/8] Running SecurityGovernanceAgent...")
    try:
        security_agent = SecurityGovernanceAgent(
            context=shared_context,
            rag_context=rag_context
        )
        security_result = security_agent.run()
        results["security_governance"] = security_result.get("markdown", "")
        shared_context["security_governance"] = results["security_governance"]
        print("   ✅ Security & governance done")
    except Exception as e:
        print(f"   ⚠️ SecurityGovernanceAgent failed: {e}")
        results["security_governance"] = f"Security governance design failed: {e}"
        shared_context["security_governance"] = ""

    # ──────────────────────────────────────────────────────────────
    # STEP 7: Cost Estimation
    # ──────────────────────────────────────────────────────────────
    print("💸 [7/8] Running CostEstimationAgent...")
    try:
        # Detect complexity from RAG context for more accurate cost estimation
        complexity = _detect_complexity_from_context(rag_context, shared_context)
        cost_agent = CostEstimationAgent(
            context=shared_context,
            rag_context=rag_context,
            detected_complexity=complexity
        )
        cost_result = cost_agent.run()
        results["cost_estimation"] = cost_result.get("markdown", "")
        results["cost_breakdown"] = cost_result.get("breakdown", {})
        results["total_monthly_cost"] = cost_result.get("total_monthly", 0)
        print(f"   ✅ Cost estimated: ${cost_result.get('total_monthly', 0):.2f}/month")
    except Exception as e:
        print(f"   ⚠️ CostEstimationAgent failed: {e}")
        results["cost_estimation"] = f"Cost estimation failed: {e}"

    # ──────────────────────────────────────────────────────────────
    # STEP 8: Mermaid Architecture Diagram
    # ──────────────────────────────────────────────────────────────
    print("📊 [8/8] Running MermaidAIAgent...")
    try:
        mermaid_agent = MermaidAIAgent(
            context=shared_context,
            rag_context=rag_context
        )
        mermaid_result = mermaid_agent.run()
        results["mermaid_diagram"] = mermaid_result.get("markdown", "")
        print("   ✅ Mermaid diagram done")
    except Exception as e:
        print(f"   ⚠️ MermaidAIAgent failed: {e}")
        results["mermaid_diagram"] = _fallback_mermaid(detected_domain)

    # ──────────────────────────────────────────────────────────────
    # Metadata
    # ──────────────────────────────────────────────────────────────
    results["pipeline_metadata"] = {
        "domain": detected_domain,
        "rag_patterns_retrieved": rag_context.count("### "),
        "web_search_enabled": enable_web_search,
        "agents_run": 8,
        "status": "success"
    }

    print("\n🎉 Architect pipeline complete.")
    return results


def _detect_complexity_from_context(rag_context: str, shared_context: Dict) -> str:
    """
    Infer architecture complexity from RAG context and ingestion strategy text.
    Used by CostEstimationAgent for accurate cost multiplier selection.
    """
    text = (rag_context + " " + shared_context.get("ingestion_strategy", "")).lower()

    if any(k in text for k in ["very high", "data mesh", "sox", "hipaa", "pci", "regulatory"]):
        return "very high"
    if any(k in text for k in ["high complexity", "streaming", "cdc", "financial risk", "healthcare"]):
        return "high"
    if any(k in text for k in ["medium-high", "medallion", "lakehouse", "iceberg", "delta lake"]):
        return "medium-high"
    if any(k in text for k in ["medium complexity", "dbt", "airflow", "redshift", "snowflake"]):
        return "medium"
    return "low-medium"


def _fallback_mermaid(domain: str) -> str:
    """Return a generic fallback diagram if MermaidAIAgent fails."""
    return f"""flowchart LR
    subgraph Sources
        S1[Business Systems]
        S2[External APIs]
        S3[Files / Uploads]
    end
    subgraph Ingestion
        I1[Batch / CDC / Streaming]
        I2[Schema Validation]
    end
    subgraph Storage
        B[Bronze - Raw]
        Si[Silver - Curated]
        G[Gold - Analytical]
    end
    subgraph Serving
        DW[Data Warehouse]
        BI[BI / Analytics]
    end
    subgraph Ops
        OR[Orchestration]
        MO[Monitoring]
        SEC[Security]
    end
    S1 --> I1
    S2 --> I1
    S3 --> I1
    I1 --> I2 --> B --> Si --> G --> DW --> BI
    OR -.-> I1
    MO -.-> Storage
    SEC -.-> Storage"""
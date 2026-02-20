---
title: Architecture Boundaries
description: The ingest/core layer split — why separating data loading from pipeline logic keeps TerraFlow deterministic and auditable.
icon: material/border-all
tags:
  - Architecture
  - Reference
---

# Architecture Boundaries

TerraFlow splits the pipeline into two primary layers:

```mermaid
flowchart TD
    subgraph Ingest["Ingest Layer"]
        A[File System]
        B[Cloud Storage]
        C[APIs]
        A & B & C --> D[Data Loaders]
    end
    
    D --> E[Validated Data]
    
    subgraph Core["Core Layer"]
        E --> F[Configuration Validation]
        F --> G[ROI Clipping]
        G --> H[Climate Aggregation]
        H --> I[Suitability Scoring]
        I --> J[Artifact Generation]
    end
    
    J --> K[results.csv]
    J --> L[fingerprint.json]
    J --> M[results.html]
    
    style Ingest fill:#00b0ff,stroke:#0091ea,color:#fff
    style Core fill:#2d8a55,stroke:#1e5c3a,color:#fff
    style E fill:#40a86e,stroke:#2d6a4f,color:#fff
```

## Ingest layer

Ingest-layer details will be finalized later.

## Core layer

The core layer:

- Validates configuration.
- Clips raster data to the ROI.
- Aggregates climate metrics.
- Computes suitability scores and labels.
- Writes run artifacts.

The core layer should not contain any file system discovery or remote fetch logic; it relies on ingest to
provide all data.

## Why the boundary matters

Keeping ingestion and core computation separate ensures that:

!!! tip "Deterministic & Testable"
    Pipeline logic remains deterministic and testable without filesystem dependencies.

!!! tip "Extensible Data Sources"
    Future data sources (e.g., cloud buckets) can be added without rewriting scoring logic.

!!! tip "Audit-Friendly"
    The system remains audit-friendly for reproducible research with clear data provenance.

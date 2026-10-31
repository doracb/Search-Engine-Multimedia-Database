# E-Commerce Hybrid Visual-Textual Search Engine

## Overview
This project implements an advanced hybrid search engine for a fashion e-commerce catalog consisting of ~20,000 products. It bridges the gap between natural language text searches and visual neural similarity, providing a robust architecture that balances performance, cost, and search relevance (P@10). 

By combining classical full-text search with modern AI embeddings (OpenAI's CLIP), the system can accurately retrieve products even for complex user queries like "floral summer dress" or "men's watch with a metal strap".

## Tech Stack
*   **Databases & Storage:** PostgreSQL, pgvector, Qdrant, Garage (S3 Object Storage)
*   **Machine Learning / AI:** CLIP (Contrastive Language-Image Pre-training), PCA (Principal Component Analysis)
*   **Data Processing:** Python, Pandas, Jupyter, NumPy
*   **Search Algorithms:** HNSW (Hierarchical Navigable Small World), IVF (Inverted File Index), RRF (Reciprocal Rank Fusion)

## Architecture & Key Technical Decisions

Through extensive benchmarking and iterative development, several core architectural decisions were made to optimize system performance:

*   **Storage Optimization:** Transitioned from storing raw binary images in PostgreSQL (`BYTEA`) to an external S3-compatible Object Storage (Garage)[cite: 3]. This decision maintained fast read latency (under 3ms) while preventing extreme database bloat and catastrophic backup/restore times at scale.
*   **Dimensionality Reduction:** Applied PCA to reduce vector dimensionality down to 32 dimensions, drastically lowering memory footprint (by ~74%) and query latency while preserving the Mean Average Precision (mAP).
*   **Neural vs. Classical Descriptors:** Benchmarked classical computer vision descriptors (HSV for color, LBP for texture) against semantic neural embeddings (CLIP). CLIP demonstrated superior semantic understanding of the products, though classical descriptors were noted to capture fine texture details better in specific edge cases.
*   **Hybrid Search Pipeline:** Implemented Reciprocal Rank Fusion (RRF) to merge the unbounded scoring of PostgreSQL's `ts_rank_cd` with the bounded cosine similarity of vector embeddings. This hybrid approach mitigated the weaknesses of pure text search (which fails when brand names are missing) and pure vector search.

## Performance Benchmarks: `pgvector` vs `Qdrant`

A comprehensive load test was conducted to evaluate vector database engines at the current catalog scale (20k items):
*   **pgvector** proved highly efficient for this scale, delivering a `p50` latency of ~0.48ms per query because it eliminated network overhead and executed within the same ACID transaction block as the metadata.
*   **Qdrant** averaged ~44ms latency per query, primarily due to HTTP/REST network overhead and JSON serialization, though it remains the recommended architecture for horizontal scaling at the 10+ million product mark.
*   **Pre-filtering Optimization:** Implemented `iterative_scan` in pgvector to prevent catastrophic recall drops when applying highly restrictive business filters (e.g., filtering out 99% of the catalog based on category).

## Cloud Cost Modeling
Conducted a projected monthly cloud infrastructure cost analysis comparing the baseline catalog with a 100x scale-up (4.4M images). The model highlighted that while database instance RAM dominates early costs, outbound data transfer (egress) becomes the primary financial bottleneck (~97% of total cost) at scale, dictating the necessity for CDN caching layers.

## Local Setup (Docker)

The entire infrastructure runs locally via Docker Compose, orchestrating PostgreSQL (pgvector), Qdrant, Garage (Object Storage), and JupyterLab.

**1. Prerequisites**
* Docker Desktop & WSL2 (Windows) or native Docker (Linux/macOS)
* Minimum 8GB RAM and 15GB free disk space
* [Fashion Product Images (Small) dataset](https://www.kaggle.com/datasets/paramaggarwal/fashion-product-images-small) from Kaggle

**2. Environment Initialization**
Clone the repository and place the Kaggle dataset (`styles.csv` and the `images/` folder) inside the `date/` directory.

Generate the S3/Garage credentials and the `.env` file:
```bash
bash comun/pregateste-garage.sh
```

3. Launch the Services
Build the custom Jupyter image and start all containers:
```bash
docker compose --profile db --profile vect --profile lab --profile garage up -d --build
```

4. Service Access Points

- JupyterLab (Python Pipelines): http://localhost:8890/lab?token=bdm

- Qdrant Dashboard: http://localhost:6333/dashboard

- PostgreSQL: localhost:5432 (DB: bdm, User: bdm, Password: bdm)

To stop the environment without losing data:
```bash
docker compose --profile db --profile vect --profile lab --profile garage stop
```
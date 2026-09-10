# RAG Evaluation

`dataset.jsonl` contains 30 synthetic Demo questions: 24 answerable questions and 6 negative questions. The documents are synthetic and do not represent any official China Mobile business rule.

Run the offline benchmark with:

```bash
python -m evals.rag.run_retrieval_eval
```

The runner reports actual Dense, Sparse, Hybrid and Hybrid + Reranker Recall@5/MRR values from the local deterministic fixture. These are engineering-gate measurements for the Demo dataset only, not production metrics.

Latest local run:

```text
Dense                   Recall@5 1.000  MRR 0.792
Sparse                  Recall@5 1.000  MRR 0.938
Hybrid                  Recall@5 1.000  MRR 0.854
Hybrid + Reranker       Recall@5 1.000  MRR 0.854
No-Evidence Abstention                    1.000
Citation Coverage                         1.000
```

# RAG Evaluation

`dataset.jsonl` contains 30 synthetic Demo questions: 24 answerable questions and 6 negative questions. The documents are synthetic and do not represent any official China Mobile business rule.

Run the offline benchmark with:

```bash
python -m evals.rag.run_retrieval_eval
```

The runner reports actual Dense, Sparse, Hybrid and Hybrid + Reranker Recall@5/MRR values from the local deterministic fixture. These are engineering-gate measurements for the Demo dataset only, not production metrics.

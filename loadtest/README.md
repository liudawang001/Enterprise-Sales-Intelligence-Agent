# Phase 8 Load Test

Run against the stub-provider production-like stack:

```bash
locust -f loadtest/locustfile.py --headless -u 10 -r 2 -t 2m --host http://127.0.0.1:8080 --csv loadtest/results/run
```

Set `LOADTEST_BEARER_TOKEN` for JWT mode and `LOADTEST_TASK_ID` for lead and SSE fixtures. Record request count, error rate, throughput, p50/p95/p99, host CPU, and memory. This repository does not commit invented performance figures.

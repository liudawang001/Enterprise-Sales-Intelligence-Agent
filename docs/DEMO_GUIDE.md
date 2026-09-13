# v1.0 Demo Guide

Use deterministic synthetic data only; this demo is not real enterprise intelligence.

1. Start API and frontend locally and open `/workspace`.
2. Submit: “帮我找上海松江 3 家集团 V 网潜客，制造业优先”.
3. Answer the clarification prompt if shown; show task/version and research progress.
4. Inspect lead evidence, score breakdown and source lineage.
5. Change the region or business requirement and show the mutation scope (`DISCOVERY_REQUIRED` or `FULL_REPLAN`).
6. Open the historical snapshot and export the selected fields; compare rank, enterprise id, name, score and verification status with the table.

The API golden workflow and Excel consistency checks passed using synthetic fixtures. The browser session loaded the workspace and submitted the first request, but the follow-up browser action was interrupted by the agent-browser usage limit; full browser replay is therefore recorded as PARTIAL, not PASS.


# Cross-Cloud Conversational Analytics — Google Cloud Leadership Pitch (Argolis)

Google Cloud (GCP) themed executive brief and **5-slide leadership funding pitch** grounded on the **Argolis** deployment (`Analytics Agent` on Vertex AI Agent Engine + `Cross Cloud Analyst Agent` in Gemini Enterprise + Cloud Run MCP bridges + `66.0M`-row BigQuery `argolis.ccca` warehouse).

## Run Locally on Port `8999`

Bind strictly to `127.0.0.1`:

```bash
python3 -m http.server 8999 --bind 127.0.0.1 --directory ./doc
```

Open `http://127.0.0.1:8999/` in your browser.

## What's Inside

1. **Executive Brief (5 Focused Sections)**:
   - **Why Fund This**: 2-week time-to-value vs. 6+ months for ETL, `66.0M` rows proven in Argolis, and `3x` Google Cloud consumption pull-through (Gemini Enterprise + Vertex AI Agent Engine + BigQuery).
   - **Live Multi-Hop Agent Flow (`< Prev` / `Next >`)**: Interactive 4-stage visual topology (`Business User ↔ Analytics Agent ↔ Cloud Run MCP ↔ AWS PostgreSQL, AWS MySQL & GCP BigQuery`) across 3 cross-cloud scenarios.
   - **Scale & Trust**: Bifurcated routing (`Google MCP Toolbox` for `<50` keys on AWS Read Replicas + `Managed BigQuery MCP` / Federation / Omni for `50M+` rows) and CISO/DBA/FinOps guardrails.
   - **Where We Win**: Post-M&A Day-1 visibility, Banking fraud/dispute triage, Retail & residency-locked data, plus Datastream CDC guardrails.
   - **90-Day Funding Plan**: Concrete 30/60/90-day productization and lighthouse customer pilot milestones.
2. **5-Slide Pitch Deck (`01 / 05` to `05 / 05`)**:
   - Executive slide stage with clickable slide tabs, `< Prev Slide` / `Next Slide >` controls, keyboard arrow navigation, and an interactive `< Prev` / `Next >` cross-cloud flow embedded directly on **Slide 02 / 05**.

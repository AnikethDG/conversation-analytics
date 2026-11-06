# Cross-Cloud Conversational Analytics — Capabilities Doc & Executive Deck

Interactive HTML/CSS/JS capabilities documentation and 10-slide executive presentation grounded on the live **`ani-labs` (`projects/5473845300`)** deployment (`Analytics Agent` on Vertex AI Agent Engine + `Cross Cloud Analyst Agent` in Gemini Enterprise + Cloud Run MCP bridges + 66.0M-row BigQuery `ccca` dataset).

## Run Locally on Port `8999`

Bind strictly to `127.0.0.1`:

```bash
python3 -m http.server 8999 --bind 127.0.0.1 --directory ./doc
```

Open `http://127.0.0.1:8999/` in your browser.

## Key Interactive Capabilities

1. **Dual-Mode Switcher (Top Bar)**:
   - **Capabilities Doc**: 8-section interactive technical & strategic capabilities portal with scroll-spy navigation.
   - **Executive Deck (10 Slides)**: Full-screen presentation stage with `←` / `→` keyboard navigation and toggleable **Presenter Talk Track**.
2. **Live `ani-labs` Resource Inventory (Section 02)**: Filterable capabilities matrix + verified deployment manifest across Vertex AI Agent Engine (`4942427912155430912`), Gemini Enterprise (`ani-labs-ge`), Cloud Run (`us-west1`), and BigQuery (`ani-labs.ccca`).
3. **Interactive Cross-Cloud Reasoning & SQL Trace Explorer (Section 03)**: Step-by-step query decomposition, polyglot SQL inspection, and read-only safety boundary traces with masked PII.
4. **Hybrid Data Estate & Schema Graph (Section 04)**: Interactive explorer across BigQuery `ccca` (`50,000,055` risk profiles + `16,000,006` app events), AWS PostgreSQL `finance_db`, and AWS MySQL `engagement_db`.
5. **Bifurcated Architecture Switcher & Scale Simulator (Section 05)**: Compare `v1 Live Baseline` vs. `v2 Enterprise Bifurcated Scale` (`MCP Toolbox` + `Managed BigQuery MCP` + `EXTERNAL_QUERY` / `BigQuery Omni`) and simulate token/accuracy trade-offs up to 50M rows.
6. **Split-Gravity Industry Playbooks & Fit Guardrails (Section 07)**: Interactive selector covering the 4 winning enterprise scenarios plus Datastream CDC and single-cloud guardrails.

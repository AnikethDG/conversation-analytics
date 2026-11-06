# Cross-Cloud Conversational Analytics — Interactive Capabilities & Architecture Portal

Interactive HTML/CSS/JavaScript web documentation and 10-slide executive presentation showcasing **Zero-Copy Cross-Cloud Conversational Analytics** across AWS operational databases (`PostgreSQL`, `MySQL`) and Google Cloud `BigQuery` (`66.0M+` rows) via Vertex AI Agent Engine (`google-adk`), Gemini Enterprise, and Model Context Protocol (MCP).

## Repository Structure

- [`doc/`](./doc) — Interactive **Capabilities Documentation** (8 sections) + **10-Slide Executive Deck** (`index.html`, `styles.css`, `app.js`, `README.md`).

## Quick Start

```bash
python3 -m http.server 8999 --bind 127.0.0.1 --directory ./doc
```

Then visit `http://127.0.0.1:8999/`.

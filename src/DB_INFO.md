# Hybrid Cloud Database Schema & Sample Prompts

This directory implements a **Cross-Cloud Conversational Analytics** bridge using Model Context Protocol (MCP) on Google Cloud Run to connect **AWS** operational databases (`PostgreSQL`, `MySQL`) with **Google Cloud BigQuery** (`ccca`).

The universal integration key linking records across all three systems is `email` (PostgreSQL) ↔ `customer_email` (MySQL & BigQuery).

## AWS Operational Data Tier

### PostgreSQL (`finance_db`) — Core Banking
* **`customers`**: `id` (SERIAL PK), `name` (VARCHAR), `email` (VARCHAR — *Join Key*)
* **`accounts`**: `id` (SERIAL PK), `customer_id` (INT FK → `customers.id`), `type` (`checking` | `savings` | `credit`), `balance` (DECIMAL)
* **`transactions`**: `id` (SERIAL PK), `account_id` (INT FK → `accounts.id`), `amount` (DECIMAL), `date` (TIMESTAMP)

### MySQL (`engagement_db`) — CRM & Customer Support
* **`support_tickets`**: `id` (INT PK), `customer_email` (VARCHAR — *Join Key*), `issue` (TEXT), `status` (`Open` | `Closed` | `In Progress`)
* **`campaign_responses`**: `id` (INT PK), `customer_email` (VARCHAR — *Join Key*), `campaign_name` (VARCHAR), `response` (`Interested` | `Ignored` | `Unsubscribed` | `Clicked`)

## Google Cloud Warehouse Tier

### BigQuery (`ccca`) — Behavioral Telemetry & ML Risk
* **`app_events`**: `event_id` (STRING), `customer_email` (STRING — *Join Key*), `event_type` (STRING), `device_os` (STRING), `timestamp` (TIMESTAMP), `payload` (STRING)
* **`customer_risk_profiles`**: `customer_email` (STRING — *Join Key*), `churn_risk_score` (FLOAT64), `fraud_risk_score` (FLOAT64), `last_calculated` (TIMESTAMP)

---

## Sample Cross-Cloud Prompts

1. **Single-Customer 360 Triage**:
   > *"Look up the email address for 'James Smith' in PostgreSQL. Using that email, check if they have open support tickets in MySQL and retrieve their fraud & churn risk scores in BigQuery."*
2. **Cross-Cloud Aggregate Reconciliation**:
   > *"From BigQuery, calculate the average fraud risk score. From PostgreSQL, sum all checking account balances. From MySQL, count all 'Open' support tickets."*
3. **Warehouse-First Cohort Pruning + Batched AWS Lookup**:
   > *"Find the top 3 customers in BigQuery with `fraud_risk_score > 0.9`. Batch their emails to check their live account balances in PostgreSQL and recent campaign responses in MySQL."*

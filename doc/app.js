/* ==========================================================================
   Cross-Cloud Conversational Analytics — Interactive Capabilities Controller
   Security Note: Pure safe DOM APIs (textContent, createElement, replaceChildren)
   ========================================================================== */

(function () {
  'use strict';

  /* ------------------------------------------------------------------------
     1. Cross-Cloud Reasoning & SQL Trace Data (PII Masked)
     ------------------------------------------------------------------------ */
  const TRACES = [
    {
      prompt:
        '“Look up high-priority checking customer Noah M. (n***n@example-bank.com) in Postgres, check if he has open support tickets in MySQL, and pull his latest churn risk score from BigQuery.”',
      steps: [
        {
          stepLabel: 'Step 1 · AWS PostgreSQL (db-query-api)',
          badgeText: 'TCP 5432 · finance_db',
          badgeClass: 'badge-blue',
          sql: "SELECT c.id, a.type, a.balance\nFROM customers c\nJOIN accounts a ON c.id = a.customer_id\nWHERE c.email = 'n***n@example-bank.com'\nLIMIT 5;"
        },
        {
          stepLabel: 'Step 2 · AWS MySQL (db-query-api-mysql)',
          badgeText: 'TCP 3306 · engagement_db',
          badgeClass: 'badge-slate',
          sql: "SELECT id, issue, status\nFROM support_tickets\nWHERE customer_email = 'n***n@example-bank.com'\n  AND status = 'Open'\nLIMIT 5;"
        },
        {
          stepLabel: 'Step 3 · GCP BigQuery (ani-labs.ccca · 50M rows)',
          badgeText: 'GoogleSQL · ccca',
          badgeClass: 'badge-teal',
          sql: "SELECT churn_risk_score, fraud_risk_score, last_calculated\nFROM `ani-labs.ccca.customer_risk_profiles`\nWHERE customer_email = 'n***n@example-bank.com'\nLIMIT 1;"
        }
      ],
      answer:
        'Customer n***n@example-bank.com holds an active Checking balance of $24,850.00 in AWS finance_db, has 1 Open support ticket (#4109: “Wire transfer pending verification”) in AWS engagement_db, and carries an elevated BigQuery churn_risk_score of 0.87. Recommended action: route ticket #4109 to VIP retention desk.',
      hops: 'Tool Calls: 3 (PG + MySQL + BQ)',
      bytes: 'Cross-Cloud Payload: 1.4 KB (Zero Raw Table Copy)',
      latency: 'Typical Latency: ~3.4 s'
    },
    {
      prompt:
        '“Find up to 3 customers in BigQuery with a fraud risk score above 0.92. Check AWS Postgres to see if they hold credit accounts, and check AWS MySQL for recent campaign clicks.”',
      steps: [
        {
          stepLabel: 'Step 1 · High-Selectivity Prune in BigQuery (50,000,055 rows)',
          badgeText: 'Smallest Cohort First',
          badgeClass: 'badge-teal',
          sql: "SELECT customer_email, fraud_risk_score\nFROM `ani-labs.ccca.customer_risk_profiles`\nWHERE fraud_risk_score > 0.92\nORDER BY fraud_risk_score DESC\nLIMIT 3;"
        },
        {
          stepLabel: 'Step 2 · Batched IN (...) Lookup on AWS PostgreSQL',
          badgeText: 'Zero N+1 Loops',
          badgeClass: 'badge-blue',
          sql: "SELECT c.email, a.type, a.balance\nFROM customers c\nJOIN accounts a ON c.id = a.customer_id\nWHERE c.email IN ('e***a@example-bank.com', 'm***k@example-bank.com', 'r***s@example-bank.com')\n  AND a.type = 'credit';"
        },
        {
          stepLabel: 'Step 3 · Batched CRM Engagement Check on AWS MySQL',
          badgeText: 'Batched Key Filter',
          badgeClass: 'badge-slate',
          sql: "SELECT customer_email, campaign_name, response\nFROM campaign_responses\nWHERE customer_email IN ('e***a@example-bank.com', 'm***k@example-bank.com', 'r***s@example-bank.com');"
        }
      ],
      answer:
        'Identified 3 high-fraud-risk profiles (>0.92) in BigQuery ccca: two hold active AWS credit lines (e***a@example-bank.com: $14,200; m***k@example-bank.com: $8,900), and both clicked the “Credit-Limit-Boost” promo within 48h. Flagged for step-up authentication.',
      hops: 'Tool Calls: 3 (Selective Prune → Batched IN)',
      bytes: 'Cross-Cloud Payload: 2.1 KB',
      latency: 'Typical Latency: ~3.9 s'
    },
    {
      prompt:
        '“Check BigQuery for today’s transfer_initiated event count, compare against total settled transaction volume in AWS Postgres, and report total Open support tickets in MySQL.”',
      steps: [
        {
          stepLabel: 'Step 1 · Pushdown Count on BigQuery app_events (16,000,006 rows)',
          badgeText: 'Warehouse Aggregation',
          badgeClass: 'badge-teal',
          sql: "SELECT COUNT(*) AS initiated_transfers\nFROM `ani-labs.ccca.app_events`\nWHERE event_type = 'transfer_initiated'\n  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR);"
        },
        {
          stepLabel: 'Step 2 · Pushdown Sum on AWS PostgreSQL transactions',
          badgeText: 'SQL SUM Pushdown',
          badgeClass: 'badge-blue',
          sql: "SELECT COUNT(*) AS settled_tx_cnt, COALESCE(SUM(amount), 0) AS settled_volume\nFROM transactions\nWHERE date >= CURRENT_DATE;"
        },
        {
          stepLabel: 'Step 3 · Backlog Count on AWS MySQL support_tickets',
          badgeText: 'SQL COUNT Pushdown',
          badgeClass: 'badge-slate',
          sql: "SELECT COUNT(*) AS open_tickets\nFROM support_tickets\nWHERE status = 'Open';"
        }
      ],
      answer:
        'In the last 24h, BigQuery recorded 18,420 transfer_initiated app events while AWS PostgreSQL settled 17,905 ledger transactions ($6.42M volume)—a 2.8% funnel drop-off coinciding with 42 Open MySQL support tickets.',
      hops: 'Tool Calls: 3 Aggregate Queries',
      bytes: 'Cross-Cloud Payload: 0.4 KB (3 Scalar Summaries)',
      latency: 'Typical Latency: ~2.8 s'
    },
    {
      prompt:
        '“Find checking customers who hit an iOS app_crash in the last hour and immediately credit $10.00 to their AWS Postgres account balance.”',
      steps: [
        {
          stepLabel: 'Step 1 · Analytical Diagnosis Allowed (Read-Only SELECT)',
          badgeText: 'Permitted Read',
          badgeClass: 'badge-emerald',
          sql: "SELECT DISTINCT customer_email, COUNT(*) AS crash_cnt\nFROM `ani-labs.ccca.app_events`\nWHERE event_type = 'app_crash' AND device_os = 'iOS'\n  AND timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)\nGROUP BY customer_email LIMIT 5;"
        },
        {
          stepLabel: 'Step 2 · Mutation Request Blocked by Read-Only Policy',
          badgeText: 'Write Blocked',
          badgeClass: 'badge-rose',
          sql: "-- BLOCKED: UPDATE accounts SET balance = balance + 10.00 ...\n-- Policy: Analytics Agent enforces strict read-only SELECT scope.\n-- Mutations require dedicated HITL-approved transactional APIs."
        }
      ],
      answer:
        'I identified the impacted iOS cohort experiencing app_crash events in the past hour (4 checking customers affected), which you can export for remediation. However, I am authorized strictly for read-only analytical queries and cannot execute UPDATE/INSERT balance modifications directly against finance_db.',
      hops: 'Tool Calls: 1 Executed · 1 Mutation Refused',
      bytes: 'Cross-Cloud Payload: 0.6 KB',
      latency: 'Typical Latency: ~2.1 s (Zero Ledger Risk)'
    }
  ];

  /* ------------------------------------------------------------------------
     2. Hybrid Data Estate Schemas (Verified against ani-labs + DB_INFO.md)
     ------------------------------------------------------------------------ */
  const SCHEMAS = {
    bq: [
      {
        name: 'ccca.customer_risk_profiles',
        meta: '50,000,055 rows · 2.49 GB',
        badgeClass: 'badge-teal',
        cols: [
          ['customer_email (Join Key)', 'STRING'],
          ['churn_risk_score', 'FLOAT'],
          ['fraud_risk_score', 'FLOAT'],
          ['last_calculated', 'TIMESTAMP']
        ]
      },
      {
        name: 'ccca.app_events',
        meta: '16,000,006 rows · 3.92 GB',
        badgeClass: 'badge-teal',
        cols: [
          ['event_id (PK)', 'STRING'],
          ['customer_email (Join Key)', 'STRING'],
          ['event_type', 'STRING'],
          ['device_os', 'STRING'],
          ['timestamp', 'TIMESTAMP'],
          ['payload', 'STRING']
        ]
      }
    ],
    pg: [
      {
        name: 'finance_db.customers',
        meta: 'AWS PostgreSQL · Core Identity',
        badgeClass: 'badge-blue',
        cols: [
          ['id (PK)', 'SERIAL'],
          ['name (Masked in UI)', 'VARCHAR'],
          ['email (Universal Key)', 'VARCHAR']
        ]
      },
      {
        name: 'finance_db.accounts',
        meta: 'AWS PostgreSQL · Balances',
        badgeClass: 'badge-blue',
        cols: [
          ['id (PK)', 'SERIAL'],
          ['customer_id (FK)', 'INT'],
          ['type (checking/savings/credit)', 'VARCHAR'],
          ['balance', 'DECIMAL']
        ]
      },
      {
        name: 'finance_db.transactions',
        meta: 'AWS PostgreSQL · Ledger',
        badgeClass: 'badge-blue',
        cols: [
          ['id (PK)', 'SERIAL'],
          ['account_id (FK)', 'INT'],
          ['amount', 'DECIMAL'],
          ['date', 'TIMESTAMP']
        ]
      }
    ],
    my: [
      {
        name: 'engagement_db.support_tickets',
        meta: 'AWS MySQL · Service Desk',
        badgeClass: 'badge-slate',
        cols: [
          ['id (PK)', 'INT AUTO_INC'],
          ['customer_email (Join Key)', 'VARCHAR'],
          ['issue', 'TEXT'],
          ['status (Open/Closed/In Progress)', 'VARCHAR']
        ]
      },
      {
        name: 'engagement_db.campaign_responses',
        meta: 'AWS MySQL · Marketing CRM',
        badgeClass: 'badge-slate',
        cols: [
          ['id (PK)', 'INT AUTO_INC'],
          ['customer_email (Join Key)', 'VARCHAR'],
          ['campaign_name', 'VARCHAR'],
          ['response', 'TEXT']
        ]
      }
    ]
  };

  /* ------------------------------------------------------------------------
     3. Dual-Path Architecture Node Specifications (v1 Live vs. v2 Target)
     ------------------------------------------------------------------------ */
  const ARCH_CONFIG = {
    v1: {
      zoneTop: { text: 'In-Context Memory Join (LIMIT 5)', cls: 'badge-amber' },
      zoneMid: { text: '3 Custom Python Cloud Run Services', cls: 'badge-slate' },
      zoneBot: { text: 'Direct AWS EC2 TCP 5432 / 3306', cls: 'badge-blue' },
      connTop: '▼ Stateless JSON-RPC POST /sse (Raw SQL Strings) ▼',
      connBot: '▼ Cross-Cloud TCP per Request (Unpooled Driver) ▼',
      nodes: {
        agent: {
          title: 'Analytics Agent (ani-labs)',
          sub: 'ADK + GE · LIMIT 5 Memory Join',
          inspectorTitle: 'Analytics Agent (Live v1 Orchestrator)',
          badge: 'Live in ani-labs',
          badgeCls: 'badge-teal',
          role: 'Deployed on Vertex AI Agent Engine (4942427912155430912) and Gemini Enterprise (ani-labs-ge), orchestrating tool calls across Postgres, MySQL, and BigQuery.',
          upgrade: 'v1 caps cross-database cohorts at LIMIT 5 in AGENT_PROMPT.md to protect token windows. v2 upgrades this to cardinality-based pushdown routing.',
          snippet:
            '# AGENT_PROMPT.md (Live v1 Baseline)\n1. Query smallest initial dataset first.\n2. ALWAYS append LIMIT 5 to initial customer fetch.\n3. Batch downstream lookup via WHERE email IN (...).'
        },
        security: {
          title: 'Service-Level Credentials',
          sub: 'Shared DB Env Vars · Read-Only Check',
          inspectorTitle: 'v1 Auth & SQL Safety Boundary',
          badge: 'Prototype Scope',
          badgeCls: 'badge-amber',
          role: 'Enforces query.lower().startswith("select") at the Python handler layer and authenticates to AWS databases via service environment variables.',
          upgrade: 'v2 upgrades to Cloud Run IAM + MCP Toolbox authRequired OIDC propagation, parameterized SQL statements ($1), and Model Armor screening.',
          snippet:
            '# mcp-server-postgres/main.py\nif not query.strip().lower().startswith("select"):\n    return [TextContent(type="text",\n      text="Error: Only SELECT queries are permitted.")]'
        },
        bridge: {
          title: 'db-query-api (PG & MySQL)',
          sub: 'Custom Starlette + asyncio.to_thread',
          inspectorTitle: 'Custom Python Cloud Run MCP Bridges',
          badge: 'Live us-west1',
          badgeCls: 'badge-blue',
          role: 'Solves Cloud Run stateless HTTP transport (StreamableHTTPServerTransport), intercepts /sse without 307 redirects, and offloads blocking psycopg2/pymysql I/O to worker threads.',
          upgrade: 'v2 replaces ~540 lines of custom Python plumbing with Google’s declarative 1P MCP Toolbox (genai-toolbox) for built-in connection pooling.',
          snippet:
            '# Cloud Run Stateless Transport (us-west1)\ntransport = StreamableHTTPServerTransport(\n    mcp_session_id=None,\n    is_json_response_enabled=True\n)\nresults = await asyncio.to_thread(_execute_query, sql)'
        },
        bq: {
          title: 'mcp-server-bigquery',
          sub: 'Python Wrapper over ani-labs.ccca',
          inspectorTitle: 'BigQuery Cloud Run Wrapper (ccca)',
          badge: '66.0M Rows Live',
          badgeCls: 'badge-teal',
          role: 'Exposes query_bigquery over ccca.app_events (16M rows) and ccca.customer_risk_profiles (50M rows) using Cloud Run service account ADC.',
          upgrade: 'v2 retires this container completely in favor of Google’s zero-infra Managed BigQuery MCP (bigquery.googleapis.com/mcp) + maximum_bytes_billed caps.',
          snippet:
            '# Live BigQuery Dataset in ani-labs\n# ccca.customer_risk_profiles -> 50,000,055 rows (2.49 GB)\n# ccca.app_events             -> 16,000,006 rows (3.92 GB)'
        },
        aws: {
          title: 'AWS EC2 Postgres & MySQL',
          sub: 'finance_db + engagement_db',
          inspectorTitle: 'AWS Operational Databases',
          badge: 'Zero Bulk ETL',
          badgeCls: 'badge-slate',
          role: 'Hosts authoritative transactional banking balances (finance_db) and live customer support / campaign records (engagement_db) in AWS.',
          upgrade: 'v2 routes agent traffic over HA VPN exclusively to dedicated Read Replicas with statement_timeout = 5s and adds BigQuery Omni for S3 lakes.',
          snippet:
            '-- Universal Cross-Cloud Entity Key\nAWS Postgres: customers.email\nAWS MySQL:    support_tickets.customer_email\nGCP BigQuery: ccca.customer_risk_profiles.customer_email'
        }
      }
    },
    v2: {
      zoneTop: { text: 'Cardinality-Aware Router', cls: 'badge-emerald' },
      zoneMid: { text: 'Zero Custom Connector Code', cls: 'badge-teal' },
      zoneBot: { text: 'Zero Primary OLTP Risk', cls: 'badge-blue' },
      connTop: '▼ OIDC Authenticated Tool Calls · Lazy Dataplex Schema Lookup ▼',
      connBot: '▼ HA VPN / Cloud Interconnect · BQ EXTERNAL_QUERY & Omni Pushdown ▼',
      nodes: {
        agent: {
          title: 'Analytics Agent (ADK + GE)',
          sub: 'Routes Entity (<50) vs. OLAP (50M+)',
          inspectorTitle: 'Analytics Agent — Cardinality Router',
          badge: '1P Target Pattern',
          badgeCls: 'badge-emerald',
          role: 'Dynamically separates operational single-customer lookups (<50 keys) from population-wide analytical aggregations across the 50M-row customer_risk_profiles table.',
          upgrade: 'Eliminates silent LIMIT 5 sampling distortion on executive KPIs while keeping token usage flat via ADK sub-agent scratchpad isolation.',
          snippet:
            "-- Path B: Population Join Pushed Down to BigQuery Slots\nSELECT r.risk_tier, COUNT(*) AS users, SUM(aws.balance) AS exposure\nFROM `ani-labs.ccca.customer_risk_profiles` r\nJOIN EXTERNAL_QUERY('ani-labs.us-west1.aws_pg_ro',\n  'SELECT email, balance FROM customer_balances_v') aws\nON r.customer_email = aws.email\nWHERE r.churn_risk_score > 0.80\nGROUP BY 1;"
        },
        security: {
          title: 'End-User OIDC + Model Armor',
          sub: 'Per-User RLS + Prompt Injection Shield',
          inspectorTitle: 'Zero-Trust Identity & Prompt Defense',
          badge: 'CISO Ready',
          badgeCls: 'badge-emerald',
          role: 'Verifies caller OIDC identity on every tool call, enforcing BigQuery SESSION_USER() Row Access Policies and screening untrusted ticket text with Model Armor.',
          upgrade: 'Eliminates shared database user privilege escalation and neutralizes indirect SQL injection from free-text CRM fields.',
          snippet:
            '-- BigQuery Row-Level Security Policy\nCREATE ROW ACCESS POLICY regional_analyst_filter\nON `ani-labs.ccca.customer_risk_profiles`\nGRANT TO ("domain:example-bank.com")\nFILTER USING (region_owner = SESSION_USER());'
        },
        bridge: {
          title: 'MCP Toolbox (genai-toolbox)',
          sub: 'Pooled · Parameterized SQL (ANY($1))',
          inspectorTitle: '1P MCP Toolbox for Databases',
          badge: 'Fast Path A (<50 Keys)',
          badgeCls: 'badge-teal',
          role: 'Single declarative tools.yaml binary managing warm cross-cloud connection pools, typed SQL parameter binding, OIDC verification, and OpenTelemetry traces.',
          upgrade: 'Delivers 3–5x lower P95 tool latency than per-request TCP handshakes and blocks multi-statement SQL injection by construction.',
          snippet:
            'tools:\n  get_customer_accounts_by_emails:\n    kind: postgres-sql\n    source: aws-finance-replica\n    authRequired: [google-oidc]\n    statement: |\n      SELECT c.email, a.type, a.balance\n      FROM customers c JOIN accounts a ON c.id = a.customer_id\n      WHERE c.email = ANY($1::text[]) LIMIT 50;'
        },
        bq: {
          title: 'Managed BQ MCP + GDA API',
          sub: 'bigquery.googleapis.com/mcp + LookML',
          inspectorTitle: 'Managed BigQuery MCP & Conversational Analytics API',
          badge: 'Analytical Path B',
          badgeCls: 'badge-blue',
          role: 'Combines Google’s serverless bigquery.googleapis.com/mcp endpoint with Conversational Analytics API (geminidataanalytics) backed by governed LookML metrics.',
          upgrade: 'Deletes mcp-server-bigquery container maintenance, guarantees consistent KPI definitions across executives, and enforces maximum_bytes_billed.',
          snippet:
            '# FinOps & Governance Guardrail\njob_config = bigquery.QueryJobConfig(\n    dry_run=False,\n    maximum_bytes_billed=1_073_741_824, # 1 GB Circuit Breaker\n    labels={"datacloud": "analytics_agent"}\n)'
        },
        aws: {
          title: 'AWS Read Replicas & S3 Iceberg',
          sub: '5s Timeout + Local BigQuery Omni Compute',
          inspectorTitle: 'DBA-Protected AWS Read Replicas & Omni Lakes',
          badge: 'DBA Approved',
          badgeCls: 'badge-emerald',
          role: 'Isolates operational point-lookups onto dedicated AWS Read Replicas over HA VPN while executing large S3/Iceberg analytical scans locally inside AWS via BigQuery Omni.',
          upgrade: 'Zero CPU/lock risk on primary OLTP banking databases and zero raw table egress fees on multi-terabyte S3 data lakes.',
          snippet:
            "-- PostgreSQL Replica Session Guardrails\nALTER ROLE mcp_readonly_agent SET default_transaction_read_only = on;\nALTER ROLE mcp_readonly_agent SET statement_timeout = '5s';"
        }
      }
    }
  };

  /* ------------------------------------------------------------------------
     4. Industry Scenarios & Architectural Guardrails
     ------------------------------------------------------------------------ */
  const SCENARIOS = {
    mna: {
      title: 'Scenario 01: Post-M&A “Split-Brain” Enterprises',
      badge: 'Tier-1 Split-Gravity Fit',
      badgeCls: 'badge-emerald',
      industries:
        'Regional & Tier-1 Banks post-acquisition, Insurance carriers, Telecom operators, Healthcare networks. Buyer: CDO / VP of Enterprise Data & AI.',
      anchor:
        'Acquiring parent already standardized risk models, telemetry, and executive intelligence on BigQuery + Gemini Enterprise; acquired subsidiary sits on AWS RDS/S3 with an 18–36 month consolidation queue.',
      trigger:
        'Leadership needs immediate cross-entity churn exposure, VIP retention, and cross-sell visibility this quarter without waiting two years for core banking ETL re-platforming.',
      pattern:
        'BigQuery Omni over subsidiary AWS S3/Iceberg lakes (local AWS compute, zero raw table egress) + MCP Toolbox parameterized lookups on AWS read replicas for individual customer drill-downs.',
      pitch:
        '“Don’t let an 18-month post-merger database consolidation hold your AI roadmap hostage. Keep acquired ledgers in AWS where they run today, keep enterprise risk models in BigQuery, and deploy Gemini Enterprise as one governed intelligence plane in weeks—analyzing S3 lakes in-place via BigQuery Omni and drilling into live account state via zero-trust MCP Toolbox.”'
    },
    ccai: {
      title: 'Scenario 02: CCAI & Live Support Customer-360',
      badge: 'Sub-2s Operational Fit',
      badgeCls: 'badge-emerald',
      industries:
        'Retail banking, Airlines, E-Commerce marketplaces, Subscription Telecom. Buyer: VP of Customer Experience / Contact Center AI Lead.',
      anchor:
        'Google Cloud Contact Center AI (CCAI) + BigQuery customer lifetime value (LTV), clickstream crash logs, and churn propensity models.',
      trigger:
        'When a VIP caller hits an app crash or disputed wire, human and virtual agents need live AWS order/ledger status fused with BigQuery churn scores while the caller is on the phone.',
      pattern:
        'Fast Path A: Vertex AI Agent Engine (Analytics Agent) invoking MCP Toolbox indexed primary-key lookups (WHERE email = $1) on AWS Read Replicas paired with BigQuery ccca score retrieval.',
      pitch:
        '“Equip every support specialist and CCAI agent with instant Cross-Cloud Customer-360: fuse 2 years of BigQuery behavioral telemetry and churn propensity with live, up-to-the-second AWS ledger and ticket state in one prompt—zero batch lag, zero primary DB risk.”'
    },
    ga4: {
      title: 'Scenario 03: GA4 / Google Ads (BigQuery) + AWS Checkout Attribution',
      badge: 'High-Velocity Growth Fit',
      badgeCls: 'badge-emerald',
      industries:
        'Digital-native E-Commerce, Direct-to-Consumer (D2C), Mobile Gaming, Streaming & Subscription Media. Buyer: CMO / VP of Growth Analytics.',
      anchor:
        'Google Analytics 4 (GA4) raw event exports and Google Ads attribution tables land natively in BigQuery (app_events), while checkout/billing microservices run on AWS RDS/Aurora.',
      trigger:
        'Growth teams struggle to connect upper-funnel ad spend and mobile crash events in BigQuery with net realized subscription revenue, refunds, and chargebacks in AWS.',
      pattern:
        'Analytical Path B: BigQuery EXTERNAL_QUERY / Omni cohort aggregation + Conversational Analytics API backed by governed ROAS and Net-LTV semantic definitions.',
      pitch:
        '“Your acquisition funnel already lives natively in BigQuery while subscription billing runs on AWS. Ask true net-ROAS, refund-adjusted LTV, and checkout-drop-off questions in plain English—without maintaining fragile nightly CSV bridges.”'
    },
    sovereign: {
      title: 'Scenario 04: Ring-Fenced PII & Data Sovereignty Enclaves',
      badge: 'Compliance Unblocker',
      badgeCls: 'badge-emerald',
      industries:
        'Capital Markets, Wealth Management, Healthcare Providers, Multinational EU/APAC Enterprises. Buyer: CISO / Chief Privacy & Data Governance Officer.',
      anchor:
        'Centralized enterprise AI agents and anonymized ML feature stores on Google Cloud; strict regulatory or contractual clauses prohibiting bulk PII table replication out of regional AWS accounts.',
      trigger:
        'Compliance teams block AI pilots that require copying full customer master tables across cloud boundaries.',
      pattern:
        'BigQuery Omni in-region S3 computation + MCP Toolbox with strict column projection, PII masking, and per-user OIDC Row-Level Security.',
      pitch:
        '“Satisfy CISO data-minimization mandates without stalling AI innovation: raw regulated tables never leave their regional AWS boundary, while BigQuery Omni and OIDC-governed MCP tools return only authorized, minimized insights.”'
    },
    guardrail_cdc: {
      title: 'Guardrail 01: High-Concurrency Executive BI Dashboards',
      badge: 'Use Datastream CDC Instead',
      badgeCls: 'badge-amber',
      industries:
        'Any enterprise refreshing wallboard BI dashboards 500–10,000+ times per day across thousands of concurrent viewers.',
      anchor:
        'Architectural Economics Rule: Live cross-cloud federation pays WAN latency and AWS egress on every uncached scan.',
      trigger:
        'A team proposes pointing high-QPS Looker/BI dashboards directly through live MCP or federated OLTP queries.',
      pattern:
        'Use Google Cloud Datastream (serverless CDC from AWS RDS PostgreSQL/MySQL directly into BigQuery) + native Conversational Analytics API.',
      pitch:
        'Architectural Guidance: When the exact same cross-cloud join runs hundreds of times daily for BI dashboards, continuous serverless CDC via Google Cloud Datastream into BigQuery is 10x cheaper and 20x faster than zero-copy live operational querying.'
    },
    guardrail_aws: {
      title: 'Guardrail 02: 100% AWS Estate with Zero Google Cloud Anchor',
      badge: 'Disqualify / Land Anchor First',
      badgeCls: 'badge-rose',
      industries:
        'Single-cloud organizations where 100% of operational databases, warehouses, and BI tools reside in AWS with no BigQuery, GA4, CCAI, or Workspace footprint.',
      anchor:
        'Data Gravity Physics: Paying cross-cloud WAN latency and AWS egress ($0.09/GB) without a GCP data or AI anchor creates unnecessary friction.',
      trigger:
        'Prospect asks solely to query AWS RDS tables with no GCP datasets, ML models, or Gemini Enterprise workspace in scope.',
      pattern:
        'Land an asymmetric GCP anchor first (Gemini Enterprise + BigQuery ML / GA4 / CCAI), or migrate analytical warehousing to BigQuery before scaling cross-cloud agentic workflows.',
      pitch:
        'Strategic Guidance: Cross-Cloud Conversational Analytics shines when unifying Split-Gravity estates. Always anchor on a high-value Google Cloud capability (BigQuery ML, GA4, Looker, CCAI, or Gemini Enterprise) rather than pitching cross-cloud SQL over a single-cloud non-GCP estate.'
    }
  };

  /* ------------------------------------------------------------------------
     5. Slide Presenter Talk Tracks (10 Slides)
     ------------------------------------------------------------------------ */
  const SPEAKER_NOTES = [
    'Slide 01: Anchor on business velocity. Customers want Gemini Enterprise and BigQuery AI today, but operational ledgers and CRM systems often sit on AWS. Zero-copy cross-cloud analytics eliminates the 9-month ETL bottleneck.',
    'Slide 02: Ground the audience in live reality—not slideware. Point out that in project ani-labs, Analytics Agent (Vertex AI Agent Engine ADK) and Cross Cloud Analyst Agent (Gemini Enterprise) are live right now alongside 66M rows in BigQuery ccca.',
    'Slide 03: Highlight how the six capabilities work together: polyglot SQL synthesis, selective cohort pruning (IN batching without N+1 loops), non-blocking Cloud Run async workers, and workload identity + OpenTelemetry.',
    'Slide 04: Walk through the Noah M. (n***n@example-bank.com) escalation trace: 3 isolated databases across 2 clouds resolved in ~3.4 seconds moving just 1.4 KB over the wire—fusing live operational state with 50M-row ML risk scores.',
    'Slide 05: Proactively address scale and context windows! Explain why v1 used LIMIT 5 for demo safety, and how our v2 Bifurcated Architecture routes <50-key lookups to MCP Toolbox and 50M-row joins to BigQuery EXTERNAL_QUERY & Omni.',
    'Slide 06: Show 100% alignment with Google Cloud’s 1P roadmap: Managed BigQuery MCP (bigquery.googleapis.com/mcp), MCP Toolbox (genai-toolbox), Dataplex lazy schema discovery, and Looker semantic metrics.',
    'Slide 07: Speak directly to the CISO, Production DBA, and FinOps lead in the room: per-user OIDC Row-Level Security, parameterized SQL immune to ticket prompt injection, AWS Read Replicas with 5s timeouts, and BigQuery byte circuit breakers.',
    'Slide 08: Focus commercial energy on the 4 Split-Gravity industry plays where Google Cloud already holds an asymmetric anchor: Post-M&A banks/telcos, CCAI live support, GA4/Ads + AWS checkout, and sovereign PII enclaves.',
    'Slide 09: Earn deep technical trust by stating clearly when NOT to use live federation: use Datastream CDC for high-QPS repetitive BI dashboards, and avoid 100% single-cloud non-GCP estates.',
    'Slide 10: Close with the clear evolution path from our live ani-labs baseline to the Phase 1/2 1P Reference Kit—and invite stakeholders to test live traces and the cardinality simulator in Doc Mode.'
  ];

  /* ------------------------------------------------------------------------
     State & Initialization
     ------------------------------------------------------------------------ */
  let archVersion = 'v2';
  let selectedNode = 'agent';
  let simStrategy = 'v2';
  let currentSlide = 0;
  let notesVisible = true;

  const ROW_STEPS = [5, 250, 5000, 50000, 5000000, 50000000];
  const TABLE_STEPS = [7, 50, 250, 1000, 2500];

  /* ------------------------------------------------------------------------
     Mode Switcher (Capabilities Doc <-> Executive Deck)
     ------------------------------------------------------------------------ */
  const btnModeDoc = document.getElementById('btn-mode-doc');
  const btnModeDeck = document.getElementById('btn-mode-deck');
  const btnReturnDoc = document.getElementById('btn-return-doc');

  function setViewMode(mode) {
    document.body.setAttribute('data-view-mode', mode);
    const isDoc = mode === 'doc';
    btnModeDoc.classList.toggle('is-active', isDoc);
    btnModeDeck.classList.toggle('is-active', !isDoc);
    btnModeDoc.setAttribute('aria-selected', String(isDoc));
    btnModeDeck.setAttribute('aria-selected', String(!isDoc));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  btnModeDoc.addEventListener('click', function () {
    setViewMode('doc');
  });
  btnModeDeck.addEventListener('click', function () {
    setViewMode('deck');
  });
  btnReturnDoc.addEventListener('click', function () {
    setViewMode('doc');
  });

  /* ------------------------------------------------------------------------
     Scroll Progress & Sticky TOC Scroll-Spy
     ------------------------------------------------------------------------ */
  const progressFill = document.getElementById('reading-progress-fill');
  const sectionMap = [
    ['sec-overview', 'toc-link-overview'],
    ['sec-capabilities', 'toc-link-capabilities'],
    ['sec-traces', 'toc-link-traces'],
    ['sec-schema', 'toc-link-schema'],
    ['sec-architecture', 'toc-link-architecture'],
    ['sec-governance', 'toc-link-governance'],
    ['sec-usecases', 'toc-link-usecases'],
    ['sec-roadmap', 'toc-link-roadmap']
  ];

  function handleScroll() {
    const docEl = document.documentElement;
    const maxScroll = docEl.scrollHeight - docEl.clientHeight;
    const pct = maxScroll > 0 ? Math.min(100, Math.max(0, (window.scrollY / maxScroll) * 100)) : 0;
    progressFill.style.width = pct.toFixed(1) + '%';

    if (document.body.getAttribute('data-view-mode') !== 'doc') {
      return;
    }

    let activeLinkId = sectionMap[0][1];
    const threshold = window.scrollY + 140;
    for (let i = 0; i < sectionMap.length; i++) {
      const sec = document.getElementById(sectionMap[i][0]);
      if (sec && sec.offsetTop <= threshold) {
        activeLinkId = sectionMap[i][1];
      }
    }

    for (let i = 0; i < sectionMap.length; i++) {
      const link = document.getElementById(sectionMap[i][1]);
      if (link) {
        link.classList.toggle('is-active', sectionMap[i][1] === activeLinkId);
      }
    }
  }

  window.addEventListener('scroll', handleScroll, { passive: true });

  /* ------------------------------------------------------------------------
     Section 02: Capabilities Domain Filter
     ------------------------------------------------------------------------ */
  const capFilterBtns = document.querySelectorAll('[data-cap-filter]');
  const capCards = document.querySelectorAll('#cap-cards-grid .cap-card');

  capFilterBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const filter = btn.getAttribute('data-cap-filter');
      capFilterBtns.forEach(function (b) {
        b.classList.toggle('is-active', b === btn);
      });
      capCards.forEach(function (card) {
        const cat = card.getAttribute('data-cap-cat');
        const show = filter === 'all' || cat === filter;
        card.classList.toggle('is-hidden', !show);
      });
    });
  });

  /* ------------------------------------------------------------------------
     Section 03: Interactive Reasoning & SQL Trace Explorer
     ------------------------------------------------------------------------ */
  const traceBtns = document.querySelectorAll('[data-trace]');
  const traceQueryText = document.getElementById('trace-query-text');
  const traceStepsContainer = document.getElementById('trace-steps-container');
  const traceAnswerOutput = document.getElementById('trace-answer-output');
  const traceMetricHops = document.getElementById('trace-metric-hops');
  const traceMetricBytes = document.getElementById('trace-metric-bytes');
  const traceMetricLatency = document.getElementById('trace-metric-latency');

  function renderTrace(idx) {
    const item = TRACES[idx] || TRACES[0];
    traceQueryText.textContent = item.prompt;
    traceAnswerOutput.textContent = item.answer;
    traceMetricHops.textContent = item.hops;
    traceMetricBytes.textContent = item.bytes;
    traceMetricLatency.textContent = item.latency;

    const nodes = item.steps.map(function (st) {
      const wrap = document.createElement('div');
      wrap.className = 'trace-step-item';

      const head = document.createElement('div');
      head.className = 'trace-step-head';

      const title = document.createElement('span');
      title.className = 'trace-step-title';
      title.textContent = st.stepLabel;

      const badge = document.createElement('span');
      badge.className = 'badge ' + st.badgeClass;
      badge.textContent = st.badgeText;

      head.appendChild(title);
      head.appendChild(badge);

      const pre = document.createElement('pre');
      pre.className = 'trace-step-sql';
      pre.textContent = st.sql;

      wrap.appendChild(head);
      wrap.appendChild(pre);
      return wrap;
    });

    traceStepsContainer.replaceChildren.apply(traceStepsContainer, nodes);
  }

  traceBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const idx = Number(btn.getAttribute('data-trace')) || 0;
      traceBtns.forEach(function (b) {
        b.classList.toggle('is-selected', b === btn);
      });
      renderTrace(idx);
    });
  });

  renderTrace(0);

  /* ------------------------------------------------------------------------
     Section 04: Hybrid Data Estate & Schema Explorer
     ------------------------------------------------------------------------ */
  const estateBtns = document.querySelectorAll('[data-estate]');
  const schemaContainer = document.getElementById('schema-cards-container');

  function renderSchemas(tierKey) {
    const tables = SCHEMAS[tierKey] || SCHEMAS.bq;
    const cards = tables.map(function (tbl) {
      const card = document.createElement('div');
      card.className = 'schema-card';

      const head = document.createElement('div');
      head.className = 'schema-card-head';

      const nameEl = document.createElement('span');
      nameEl.className = 'schema-table-name';
      nameEl.textContent = tbl.name;

      const badgeEl = document.createElement('span');
      badgeEl.className = 'badge ' + tbl.badgeClass;
      badgeEl.textContent = tbl.meta;

      head.appendChild(nameEl);
      head.appendChild(badgeEl);

      const ul = document.createElement('ul');
      ul.className = 'schema-col-list';

      tbl.cols.forEach(function (colPair) {
        const li = document.createElement('li');
        li.className = 'schema-col-item';

        const colName = document.createElement('span');
        colName.textContent = colPair[0];

        const colType = document.createElement('span');
        colType.className = 'schema-col-type';
        colType.textContent = colPair[1];

        li.appendChild(colName);
        li.appendChild(colType);
        ul.appendChild(li);
      });

      card.appendChild(head);
      card.appendChild(ul);
      return card;
    });

    schemaContainer.replaceChildren.apply(schemaContainer, cards);
  }

  estateBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const key = btn.getAttribute('data-estate');
      estateBtns.forEach(function (b) {
        b.classList.toggle('is-selected', b === btn);
      });
      renderSchemas(key);
    });
  });

  renderSchemas('bq');

  /* ------------------------------------------------------------------------
     Section 05: Dual-Path Architecture Switcher & Node Inspector
     ------------------------------------------------------------------------ */
  const btnArchV1 = document.getElementById('btn-arch-v1');
  const btnArchV2 = document.getElementById('btn-arch-v2');
  const archNodeBtns = document.querySelectorAll('.arch-node-btn[data-node]');

  const zoneBadgeTop = document.getElementById('zone-badge-top');
  const zoneBadgeMid = document.getElementById('zone-badge-mid');
  const zoneBadgeBot = document.getElementById('zone-badge-bot');
  const connTopLabel = document.getElementById('connector-top-label');
  const connBotLabel = document.getElementById('connector-bottom-label');

  const inspectorTitle = document.getElementById('inspector-title');
  const inspectorBadge = document.getElementById('inspector-badge');
  const inspectorRole = document.getElementById('inspector-role');
  const inspectorUpgrade = document.getElementById('inspector-upgrade');
  const inspectorSnippet = document.getElementById('inspector-snippet');

  function setBadge(el, text, cls) {
    el.className = 'badge ' + cls;
    el.textContent = text;
  }

  function renderArchitecture() {
    const cfg = ARCH_CONFIG[archVersion];
    btnArchV1.classList.toggle('is-active', archVersion === 'v1');
    btnArchV2.classList.toggle('is-active', archVersion === 'v2');

    setBadge(zoneBadgeTop, cfg.zoneTop.text, cfg.zoneTop.cls);
    setBadge(zoneBadgeMid, cfg.zoneMid.text, cfg.zoneMid.cls);
    setBadge(zoneBadgeBot, cfg.zoneBot.text, cfg.zoneBot.cls);
    connTopLabel.textContent = cfg.connTop;
    connBotLabel.textContent = cfg.connBot;

    ['agent', 'security', 'bridge', 'bq', 'aws'].forEach(function (key) {
      const n = cfg.nodes[key];
      const tEl = document.getElementById('node-' + key + '-title');
      const sEl = document.getElementById('node-' + key + '-sub');
      if (tEl) tEl.textContent = n.title;
      if (sEl) sEl.textContent = n.sub;
    });

    const activeSpec = cfg.nodes[selectedNode] || cfg.nodes.agent;
    inspectorTitle.textContent = activeSpec.inspectorTitle;
    setBadge(inspectorBadge, activeSpec.badge, activeSpec.badgeCls);
    inspectorRole.textContent = activeSpec.role;
    inspectorUpgrade.textContent = activeSpec.upgrade;
    inspectorSnippet.textContent = activeSpec.snippet;
  }

  btnArchV1.addEventListener('click', function () {
    archVersion = 'v1';
    renderArchitecture();
  });

  btnArchV2.addEventListener('click', function () {
    archVersion = 'v2';
    renderArchitecture();
  });

  archNodeBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      selectedNode = btn.getAttribute('data-node') || 'agent';
      archNodeBtns.forEach(function (b) {
        b.classList.toggle('is-selected', b === btn);
      });
      renderArchitecture();
    });
  });

  renderArchitecture();

  /* ------------------------------------------------------------------------
     Section 05B: Scale & Context-Window Simulator
     ------------------------------------------------------------------------ */
  const simBtnCapped = document.getElementById('sim-mode-v1-capped');
  const simBtnUncapped = document.getElementById('sim-mode-v1-uncapped');
  const simBtnV2 = document.getElementById('sim-mode-v2');
  const sliderRows = document.getElementById('slider-rows');
  const sliderTables = document.getElementById('slider-tables');

  const valRows = document.getElementById('val-rows');
  const valTables = document.getElementById('val-tables');
  const kpiTokens = document.getElementById('kpi-tokens');
  const kpiTokensSub = document.getElementById('kpi-tokens-sub');
  const kpiAccuracy = document.getElementById('kpi-accuracy');
  const kpiAccuracySub = document.getElementById('kpi-accuracy-sub');
  const kpiLatency = document.getElementById('kpi-latency');
  const kpiLatencySub = document.getElementById('kpi-latency-sub');
  const kpiStatus = document.getElementById('kpi-status');
  const kpiStatusSub = document.getElementById('kpi-status-sub');
  const simDiagnosisText = document.getElementById('sim-diagnosis-text');

  function formatNumber(n) {
    return n.toLocaleString('en-US');
  }

  function updateSimulator() {
    const rows = ROW_STEPS[Number(sliderRows.value)] || 50000;
    const tables = TABLE_STEPS[Number(sliderTables.value)] || 250;

    valRows.textContent = formatNumber(rows) + ' rows';
    valTables.textContent = formatNumber(tables) + ' tables';

    simBtnCapped.classList.toggle('is-active', simStrategy === 'v1-capped');
    simBtnUncapped.classList.toggle('is-active', simStrategy === 'v1-uncapped');
    simBtnV2.classList.toggle('is-active', simStrategy === 'v2');

    if (simStrategy === 'v1-capped') {
      const schemaTokens = tables * 135;
      const rowTokens = 5 * 85 * 2;
      const totalTokens = 1400 + schemaTokens + rowTokens;
      const samplePct = rows <= 5 ? 100 : (5 / rows) * 100;

      kpiTokens.textContent = formatNumber(totalTokens);
      kpiTokensSub.textContent = tables > 50 ? 'Static schema bloat in tool desc' : 'Capped at 5 rows in prompt';
      kpiAccuracy.textContent = rows <= 5 ? '100% Exact' : (samplePct < 0.01 ? '<0.01% Sample' : samplePct.toFixed(2) + '% Sample');
      kpiAccuracySub.textContent = rows <= 5 ? 'Fits inside LIMIT 5 cap' : formatNumber(rows - 5) + ' matching rows omitted';
      kpiLatency.textContent = rows <= 5 ? '3.4 s' : '4.6 s';
      kpiLatencySub.textContent = 'Unpooled cross-cloud TCP hops';
      kpiStatus.textContent = rows <= 5 && tables <= 50 ? 'Entity Fit' : 'Sampling Drift';
      kpiStatusSub.textContent = rows <= 5 ? 'Safe for single-user triage' : 'Aggregate math distorted by LIMIT 5';
      simDiagnosisText.textContent =
        rows <= 5
          ? 'At 5 matched rows, the v1 LIMIT 5 baseline returns exact entity details—ideal for targeted Customer-360 lookups.'
          : 'At ' + formatNumber(rows) + ' matched rows, enforcing LIMIT 5 protects the context window but drops ' + formatNumber(rows - 5) + ' records—demonstrating why population analytics must route to Path B SQL pushdown.';
    } else if (simStrategy === 'v1-uncapped') {
      const schemaTokens = tables * 135;
      const rawRowTokens = rows * 95;
      const totalTokens = 1400 + schemaTokens + rawRowTokens;
      const overflow = totalTokens > 1000000;

      kpiTokens.textContent = overflow ? '>1,000,000 (Overflow)' : formatNumber(totalTokens);
      kpiTokensSub.textContent = 'Raw rows serialized into LLM memory';
      kpiAccuracy.textContent = overflow ? 'Fails (400 Error)' : rows > 250 ? 'Degraded (Lost-in-Middle)' : '96% Approx';
      kpiAccuracySub.textContent = overflow ? 'Exceeds 1M token context limit' : 'LLM arithmetic over raw text rows';
      kpiLatency.textContent = overflow ? 'Timeout' : (3.5 + Math.min(45, rows * 0.004)).toFixed(1) + ' s';
      kpiLatencySub.textContent = 'Massive WAN & token serialization';
      kpiStatus.textContent = overflow ? 'Context Overflow' : 'High Token Cost';
      kpiStatusSub.textContent = 'Anti-pattern for relational joins';
      simDiagnosisText.textContent = overflow
        ? 'Streaming ' + formatNumber(rows) + ' raw rows into LLM working memory exceeds even a 1M-token window—proving why relational joins belong in database engines, not prompt tokens.'
        : 'Removing LIMIT 5 inflates prompt tokens to ' + formatNumber(totalTokens) + ' and forces the LLM to perform error-prone mental arithmetic over raw dictionaries.';
    } else {
      const lazySchemaTokens = Math.min(tables, 4) * 140 + 450;
      const summaryTokens = rows <= 50 ? rows * 38 : 650;
      const totalTokens = 1600 + lazySchemaTokens + summaryTokens;
      const routeMode = rows <= 50 ? 'Path A (MCP Toolbox)' : 'Path B (BQ Pushdown / Omni)';

      kpiTokens.textContent = formatNumber(totalTokens);
      kpiTokensSub.textContent = 'Lazy Dataplex schema + compact result';
      kpiAccuracy.textContent = '100% Exact';
      kpiAccuracySub.textContent = rows <= 50 ? 'Parameterized ANY($1) batch' : 'Full ' + formatNumber(rows) + ' rows joined in BQ slots';
      kpiLatency.textContent = rows <= 50 ? '1.8 s' : rows >= 5000000 ? '4.8 s' : '3.1 s';
      kpiLatencySub.textContent = routeMode;
      kpiStatus.textContent = 'Production Fit';
      kpiStatusSub.textContent = 'Bounded tokens at any scale';
      simDiagnosisText.textContent =
        rows <= 50
          ? 'v2 Fast Path A routes this ' + formatNumber(rows) + '-entity lookup through pooled MCP Toolbox (ANY($1)) with Dataplex lazy schema loading—completing in ~1.8s at ' + formatNumber(totalTokens) + ' tokens.'
          : 'v2 Analytical Path B pushes the ' + formatNumber(rows) + '-row join down to BigQuery EXTERNAL_QUERY / BigQuery Omni slots and returns a compact summary table—100% exact accuracy using just ' + formatNumber(totalTokens) + ' tokens.';
    }
  }

  simBtnCapped.addEventListener('click', function () {
    simStrategy = 'v1-capped';
    updateSimulator();
  });
  simBtnUncapped.addEventListener('click', function () {
    simStrategy = 'v1-uncapped';
    updateSimulator();
  });
  simBtnV2.addEventListener('click', function () {
    simStrategy = 'v2';
    updateSimulator();
  });
  sliderRows.addEventListener('input', updateSimulator);
  sliderTables.addEventListener('input', updateSimulator);

  updateSimulator();

  /* ------------------------------------------------------------------------
     Section 07: Industry Scenarios & Fit Guardrail Explorer
     ------------------------------------------------------------------------ */
  const scenBtns = document.querySelectorAll('.scenario-tab-btn[data-scen]');
  const scenTitle = document.getElementById('scen-title');
  const scenBadge = document.getElementById('scen-badge');
  const scenIndustries = document.getElementById('scen-industries');
  const scenAnchor = document.getElementById('scen-anchor');
  const scenTrigger = document.getElementById('scen-trigger');
  const scenPattern = document.getElementById('scen-pattern');
  const scenPitch = document.getElementById('scen-pitch');

  function renderScenario(key) {
    const s = SCENARIOS[key] || SCENARIOS.mna;
    scenTitle.textContent = s.title;
    setBadge(scenBadge, s.badge, s.badgeCls);
    scenIndustries.textContent = s.industries;
    scenAnchor.textContent = s.anchor;
    scenTrigger.textContent = s.trigger;
    scenPattern.textContent = s.pattern;
    scenPitch.textContent = s.pitch;
  }

  scenBtns.forEach(function (btn) {
    btn.addEventListener('click', function () {
      const key = btn.getAttribute('data-scen');
      scenBtns.forEach(function (b) {
        b.classList.toggle('is-selected', b === btn);
      });
      renderScenario(key);
    });
  });

  /* ------------------------------------------------------------------------
     Section 08: Capability Maturity Meter
     ------------------------------------------------------------------------ */
  const checkBoxes = [];
  for (let i = 1; i <= 8; i++) {
    const el = document.getElementById('chk-' + i);
    if (el) checkBoxes.push(el);
  }
  const maturityPctLabel = document.getElementById('maturity-pct-label');
  const maturityMeterFill = document.getElementById('maturity-meter-fill');
  const maturityStatusSub = document.getElementById('maturity-status-sub');

  function updateMaturity() {
    const total = checkBoxes.length || 8;
    const done = checkBoxes.filter(function (c) {
      return c.checked;
    }).length;
    const pct = Math.round((done / total) * 100);
    maturityPctLabel.textContent = pct + '%';
    maturityMeterFill.style.width = pct + '%';
    maturityStatusSub.textContent = done + ' of ' + total + ' v1→v2 milestones active';
  }

  checkBoxes.forEach(function (chk) {
    chk.addEventListener('change', updateMaturity);
  });
  updateMaturity();

  /* ------------------------------------------------------------------------
     Mode 2: 10-Slide Executive Presentation Controller
     ------------------------------------------------------------------------ */
  const slides = document.querySelectorAll('.slide-frame[data-slide-index]');
  const btnPrevSlide = document.getElementById('btn-prev-slide');
  const btnNextSlide = document.getElementById('btn-next-slide');
  const slideCounterText = document.getElementById('slide-counter-text');
  const btnToggleNotes = document.getElementById('btn-toggle-notes');
  const speakerNotesBox = document.getElementById('speaker-notes-box');
  const speakerNotesContent = document.getElementById('speaker-notes-content');

  function pad2(n) {
    return n < 10 ? '0' + n : String(n);
  }

  function renderSlide() {
    const total = slides.length;
    slides.forEach(function (sl, idx) {
      sl.classList.toggle('is-active', idx === currentSlide);
    });
    btnPrevSlide.disabled = currentSlide === 0;
    btnNextSlide.disabled = currentSlide >= total - 1;
    slideCounterText.textContent = pad2(currentSlide + 1) + ' / ' + pad2(total);
    speakerNotesContent.textContent = SPEAKER_NOTES[currentSlide] || '';
  }

  btnPrevSlide.addEventListener('click', function () {
    if (currentSlide > 0) {
      currentSlide -= 1;
      renderSlide();
    }
  });

  btnNextSlide.addEventListener('click', function () {
    if (currentSlide < slides.length - 1) {
      currentSlide += 1;
      renderSlide();
    }
  });

  btnToggleNotes.addEventListener('click', function () {
    notesVisible = !notesVisible;
    speakerNotesBox.classList.toggle('is-visible', notesVisible);
    btnToggleNotes.textContent = notesVisible ? 'Hide Talk Track' : 'Show Talk Track';
  });

  document.addEventListener('keydown', function (ev) {
    if (document.body.getAttribute('data-view-mode') !== 'deck') {
      return;
    }
    if (ev.key === 'ArrowRight' && currentSlide < slides.length - 1) {
      currentSlide += 1;
      renderSlide();
    } else if (ev.key === 'ArrowLeft' && currentSlide > 0) {
      currentSlide -= 1;
      renderSlide();
    }
  });

  renderSlide();
})();

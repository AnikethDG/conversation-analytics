'use strict';

/**
 * Google Cloud — Cross-Cloud Conversational Analytics (Argolis)
 * Leadership Funding Pitch & Interactive Multi-Hop Flow Controller
 * Security: Uses strictly safe DOM APIs (textContent, createElement, replaceChildren).
 */
document.addEventListener('DOMContentLoaded', () => {
  /* ==========================================================================
     1. MULTI-HOP INTERACTION EXAMPLES (EXECUTIVE BRIEF SECTION 02)
     ========================================================================== */
  const SCENARIOS = [
    {
      userQuestion:
        'Customer n***n@example-bank.com reported an unrecognized $4,850 wire and asked for a fee waiver. Check their live AWS Postgres accounts, AWS MySQL support tickets, and GCP BigQuery fraud risk.',
      finalAnswer:
        'Recommendation — Keep Wire Hold & Waive $35 Fee: AWS PostgreSQL shows VIP_PLATINUM balance $184,220.50 with a $4,850.00 wire in PENDING_DISPUTE. AWS MySQL confirms open P1 ticket TCK-88412. GCP BigQuery (argolis.ccca) flags 0.91 fraud probability plus a new-device MFA failure 4 minutes before the wire.',
      steps: [
        {
          title: 'User asks a cross-cloud question in Gemini Enterprise',
          nodes: { user: 'blue', agent: 'blue', mcp: '', pg: false, mysql: false, bq: false },
          arrows: { c1: ['Prompt →', 'active'], c2: ['MCP ⇄', ''], c3: ['SQL ⇄', ''] },
          route: 'Active Hop: User → Analytics Agent (GCP Argolis)',
          latency: '18 ms',
          desc: 'Business analyst asks one natural-language question in Gemini Enterprise. Analytics Agent on Vertex AI Agent Engine plans three read-only lookups keyed on customer_email.',
          keyResult: 'Plan: Query AWS PostgreSQL + AWS MySQL + GCP BigQuery in parallel',
          codeTitle: 'ADK Agent Decomposition Plan',
          code: '1. db-query-api        -> AWS PostgreSQL (finance_db)\n2. db-query-api-mysql  -> AWS MySQL (engagement_db)\n3. mcp-server-bigquery -> GCP BigQuery (argolis.ccca)'
        },
        {
          title: 'Analytics Agent calls Cloud Run MCP Server over mTLS',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: false, mysql: false, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['MCP Call →', 'active'], c3: ['SQL ⇄', ''] },
          route: 'Active Hop: Analytics Agent → Cloud Run MCP',
          latency: '14 ms',
          desc: 'Using zero-key SPIFFE workload identity, Analytics Agent invokes standardized Model Context Protocol (MCP) tools hosted on Google Cloud Run.',
          keyResult: 'Security: Cloud Run IAM + Read-Only SELECT Allowlist Verified',
          codeTitle: 'MCP JSON-RPC Request (POST /mcp)',
          code: '{\n  "method": "tools/call",\n  "params": { "name": "query_postgres_db", "email": "n***n@example-bank.com" }\n}'
        },
        {
          title: 'MCP queries AWS PostgreSQL (finance_db) for live ledger state',
          nodes: { user: '', agent: '', mcp: 'blue', pg: true, mysql: false, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['MCP', ''], c3: ['PG SQL ⇄', 'active'] },
          route: 'Active Hop: Cloud Run MCP ⇄ AWS PostgreSQL',
          latency: '42 ms',
          desc: 'The Postgres MCP bridge queries the AWS RDS Read Replica over HA VPN—fetching real-time checking balances and wire status without copying tables.',
          keyResult: 'AWS Postgres Returned: VIP_PLATINUM · $184,220.50 · $4,850 PENDING_DISPUTE',
          codeTitle: 'AWS PostgreSQL Read-Only SQL',
          code: "SELECT c.tier, a.balance, t.amount, t.status\nFROM customers c JOIN accounts a USING (customer_id)\nJOIN transactions t USING (account_id)\nWHERE c.email = 'n***n@example-bank.com';"
        },
        {
          title: 'MCP queries AWS MySQL (engagement_db) for open P1 tickets',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: false, mysql: true, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['MCP Call →', 'active'], c3: ['MySQL ⇄', 'active'] },
          route: 'Active Hop: Cloud Run MCP ⇄ AWS MySQL',
          latency: '39 ms',
          desc: 'Next, the MySQL MCP bridge checks customer support escalations and retention offer eligibility inside AWS RDS MySQL.',
          keyResult: 'AWS MySQL Returned: Ticket TCK-88412 (P1_URGENT) · Fee Waiver Eligible',
          codeTitle: 'AWS MySQL Read-Only SQL',
          code: "SELECT ticket_id, priority, status, subject\nFROM support_tickets\nWHERE customer_email = 'n***n@example-bank.com'\nORDER BY opened_at DESC LIMIT 3;"
        },
        {
          title: 'MCP scans 66M-row GCP BigQuery warehouse (argolis.ccca)',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: false, mysql: false, bq: true },
          arrows: { c1: ['Prompt', ''], c2: ['MCP Call →', 'active'], c3: ['GoogleSQL ⇄', 'active'] },
          route: 'Active Hop: BigQuery MCP ⇄ GCP BigQuery (66M Rows)',
          latency: '610 ms',
          desc: 'The BigQuery MCP server joins 50M risk profiles with 16M mobile app events directly inside BigQuery compute slots in Argolis.',
          keyResult: 'GCP BigQuery Returned: Fraud Score 0.91 · New-Device MFA Failure',
          codeTitle: 'GCP BigQuery GoogleSQL (argolis.ccca)',
          code: "SELECT r.fraud_probability, r.credit_score, e.event_type\nFROM `argolis.ccca.customer_risk_profiles` r\nJOIN `argolis.ccca.app_events` e USING (customer_email)\nWHERE r.customer_email = 'n***n@example-bank.com';"
        },
        {
          title: 'Analytics Agent delivers unified cross-cloud answer to User',
          nodes: { user: 'green', agent: 'green', mcp: '', pg: true, mysql: true, bq: true },
          arrows: { c1: ['← Answer', 'active'], c2: ['Done', ''], c3: ['3 DBs Read', ''] },
          route: 'Complete: Analytics Agent → Business User',
          latency: '1.12 s Total',
          desc: 'Analytics Agent combines live evidence from AWS Postgres, AWS MySQL, and GCP BigQuery into one grounded business recommendation.',
          keyResult: 'Outcome: 3 Databases Queried Across 2 Clouds · Zero Data Moved',
          codeTitle: 'OpenTelemetry Audit Summary (Argolis)',
          code: 'Total Latency : 1.12s  |  Rows Sent to LLM : 3\nEngines Hit   : AWS PostgreSQL + AWS MySQL + GCP BigQuery\nData Copied   : 0 bytes (100% in-place execution)'
        }
      ]
    },
    {
      userQuestion:
        'Find the top 3 accounts in BigQuery with fraud probability > 0.92 and credit score > 780, then pull their live checking balances from AWS Postgres and open ticket counts from AWS MySQL.',
      finalAnswer:
        'Priority Cohort Identified ($612,400 Total Exposure): BigQuery pruned 50M rows to 3 VIP accounts. Account k***4@example-bank.com has 0.96 fraud risk and $289,100 in AWS Postgres with 0 MySQL tickets—flagging immediate proactive fraud outreach.',
      steps: [
        {
          title: 'User asks for a 50M-row cohort filter + live AWS balances',
          nodes: { user: 'blue', agent: 'blue', mcp: '', pg: false, mysql: false, bq: false },
          arrows: { c1: ['Prompt →', 'active'], c2: ['MCP ⇄', ''], c3: ['SQL ⇄', ''] },
          route: 'Active Hop: User → Analytics Agent',
          latency: '16 ms',
          desc: 'Analytics Agent chooses a warehouse-first plan: prune 50M rows inside BigQuery first, then send one batched lookup to AWS.',
          keyResult: 'Strategy: Push 50M-Row Filter to BigQuery -> Batch 3 Keys to AWS',
          codeTitle: 'Cardinality Router Decision',
          code: 'Step 1: BigQuery filter + ORDER BY + LIMIT 3 (in-warehouse)\nStep 2: Batched WHERE email IN (...) on AWS Postgres & MySQL'
        },
        {
          title: 'BigQuery MCP prunes 50,000,055 risk profiles to top 3 accounts',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: false, mysql: false, bq: true },
          arrows: { c1: ['Prompt', ''], c2: ['MCP Call →', 'active'], c3: ['GoogleSQL ⇄', 'active'] },
          route: 'Active Hop: BigQuery MCP ⇄ GCP BigQuery',
          latency: '740 ms',
          desc: 'BigQuery scans columnar risk profiles in argolis.ccca and returns only the top 3 masked emails to the agent.',
          keyResult: 'GCP BigQuery Returned: 3 High-Risk VIP Keys (from 50.0M rows)',
          codeTitle: 'BigQuery Pushdown SQL',
          code: 'SELECT customer_email, credit_score, fraud_probability\nFROM `argolis.ccca.customer_risk_profiles`\nWHERE fraud_probability > 0.92 AND credit_score > 780\nORDER BY fraud_probability DESC LIMIT 3;'
        },
        {
          title: 'Postgres MCP runs a single batched IN (...) query on AWS RDS',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: true, mysql: false, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['Batch MCP →', 'active'], c3: ['PG SQL ⇄', 'active'] },
          route: 'Active Hop: Cloud Run MCP ⇄ AWS PostgreSQL',
          latency: '46 ms',
          desc: 'All 3 emails are batched into one read-only SQL query against AWS PostgreSQL finance_db—avoiding N+1 connection spikes.',
          keyResult: 'AWS Postgres Returned: $612,400 Combined Live Deposit Exposure',
          codeTitle: 'Batched AWS PostgreSQL Query',
          code: "SELECT c.email, SUM(a.balance) AS live_balance\nFROM customers c JOIN accounts a USING (customer_id)\nWHERE c.email IN ('k***4@example-bank.com', 'a***1@...', 'm***9@...')\nGROUP BY c.email;"
        },
        {
          title: 'MySQL MCP checks open support tickets in AWS RDS MySQL',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: false, mysql: true, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['Batch MCP →', 'active'], c3: ['MySQL ⇄', 'active'] },
          route: 'Active Hop: Cloud Run MCP ⇄ AWS MySQL',
          latency: '41 ms',
          desc: 'A single grouped query against AWS MySQL reveals which at-risk accounts have active fraud tickets vs. zero contact.',
          keyResult: 'AWS MySQL Returned: k***4@example-bank.com ($289K) has 0 Tickets!',
          codeTitle: 'Batched AWS MySQL Query',
          code: "SELECT customer_email, COUNT(*) AS open_tickets\nFROM support_tickets\nWHERE status != 'CLOSED' AND customer_email IN (...)\nGROUP BY customer_email;"
        },
        {
          title: 'Analytics Agent delivers ranked exposure summary to User',
          nodes: { user: 'green', agent: 'green', mcp: '', pg: true, mysql: true, bq: true },
          arrows: { c1: ['← Answer', 'active'], c2: ['Done', ''], c3: ['3 DBs Read', ''] },
          route: 'Complete: Analytics Agent → Business User',
          latency: '1.28 s Total',
          desc: 'The analyst gets a ranked action list highlighting the uncontacted $289K VIP account—using <1.5 KB of LLM context.',
          keyResult: '50M Rows Scanned in BigQuery · Only 3 Summary Rows Sent to Gemini',
          codeTitle: 'Prioritized Cohort Output',
          code: '1. k***4@example-bank.com | Risk 0.96 | $289,100 | 0 Tickets [URGENT]\n2. a***1@example-bank.com | Risk 0.94 | $198,500 | 1 Ticket\n3. m***9@example-bank.com | Risk 0.93 | $124,800 | 1 Ticket'
        }
      ]
    },
    {
      userQuestion:
        'Compare today’s completed checkouts in GCP BigQuery against settled USD totals in AWS Postgres, and update stuck PENDING_SETTLEMENT rows in AWS to SETTLED.',
      finalAnswer:
        'Variance Reconciled ($4,850.00 Across 8 Rows) — Write Mutation Blocked: BigQuery recorded $318,900.00 in checkouts vs. $314,050.00 settled and $4,850.00 pending in AWS Postgres. Per read-only MCP governance, UPDATE statements are blocked; route batch STL-1106 to Finance Ops.',
      steps: [
        {
          title: 'User requests cross-cloud reconciliation + an AWS UPDATE',
          nodes: { user: 'blue', agent: 'blue', mcp: '', pg: false, mysql: false, bq: false },
          arrows: { c1: ['Prompt →', 'active'], c2: ['MCP ⇄', ''], c3: ['SQL ⇄', ''] },
          route: 'Active Hop: User → Analytics Agent',
          latency: '17 ms',
          desc: 'The user combines a valid analytical comparison across BigQuery and AWS Postgres with a write request (UPDATE status).',
          keyResult: 'Policy Check: Analytical Reads Allowed · Database Writes Forbidden',
          codeTitle: 'Intent Classification',
          code: 'Read 1 : GCP BigQuery app_events aggregation  -> ALLOW\nRead 2 : AWS Postgres transactions breakdown  -> ALLOW\nWrite  : UPDATE AWS Postgres transactions     -> BLOCK'
        },
        {
          title: 'BigQuery MCP aggregates today’s checkouts across 16M events',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: false, mysql: false, bq: true },
          arrows: { c1: ['Prompt', ''], c2: ['MCP Call →', 'active'], c3: ['GoogleSQL ⇄', 'active'] },
          route: 'Active Hop: BigQuery MCP ⇄ GCP BigQuery',
          latency: '520 ms',
          desc: 'BigQuery aggregates today’s completed mobile checkout events inside argolis.ccca.app_events using partition pruning.',
          keyResult: 'GCP BigQuery Returned: 1,420 Checkouts · $318,900.00 Total',
          codeTitle: 'BigQuery Aggregation SQL',
          code: "SELECT COUNT(*) AS checkouts, SUM(cart_usd) AS total_usd\nFROM `argolis.ccca.app_events`\nWHERE event_type = 'CHECKOUT_COMPLETED'\n  AND DATE(event_ts) = CURRENT_DATE();"
        },
        {
          title: 'Postgres MCP aggregates settlement ledger in AWS finance_db',
          nodes: { user: '', agent: 'blue', mcp: 'blue', pg: true, mysql: false, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['MCP Call →', 'active'], c3: ['PG SQL ⇄', 'active'] },
          route: 'Active Hop: Cloud Run MCP ⇄ AWS PostgreSQL',
          latency: '48 ms',
          desc: 'The Postgres MCP bridge groups today’s ledger rows by status in AWS RDS PostgreSQL, pinpointing the exact $4,850 delta.',
          keyResult: 'AWS Postgres Returned: $314,050 Settled · $4,850 Pending (8 rows)',
          codeTitle: 'AWS PostgreSQL Reconciliation SQL',
          code: 'SELECT status, COUNT(*) AS tx_cnt, SUM(amount) AS usd\nFROM transactions\nWHERE created_at >= CURRENT_DATE\nGROUP BY status;'
        },
        {
          title: 'Read-Only MCP Guardrail blocks the requested UPDATE mutation',
          nodes: { user: '', agent: 'blue', mcp: 'red', pg: false, mysql: false, bq: false },
          arrows: { c1: ['Prompt', ''], c2: ['BLOCKED ✕', 'blocked'], c3: ['Protected', ''] },
          route: 'Guardrail Active: DML Mutation Rejected',
          latency: '0 ms DB Load',
          desc: 'Three independent layers (ADK policy, MCP SQL verb validator, and PostgreSQL read-only role) guarantee zero writes ever reach AWS.',
          keyResult: 'CISO & DBA Guarantee: 0 Mutations Possible Against Production OLTP',
          codeTitle: 'Three-Layer Read-Only Defense',
          code: '-- Blocked before reaching AWS RDS:\nLayer 1: ADK Read-Only System Policy\nLayer 2: MCP Allowlist (SELECT / WITH only)\nLayer 3: PostgreSQL default_transaction_read_only = on'
        },
        {
          title: 'Agent reports exact $4,850 variance & safe Finance Ops step',
          nodes: { user: 'green', agent: 'green', mcp: '', pg: true, mysql: false, bq: true },
          arrows: { c1: ['← Safe Reply', 'active'], c2: ['Done', ''], c3: ['Protected', ''] },
          route: 'Complete: Analytics Agent → Business User',
          latency: '0.96 s Total',
          desc: 'The user gets the exact $4,850 reconciliation answer immediately while production AWS databases remain 100% read-only.',
          keyResult: 'Exact $4,850 Delta Isolated · Production Ledger Safely Protected',
          codeTitle: 'Reconciliation Summary',
          code: 'BigQuery Checkouts : $318,900.00 (1,420 events)\nAWS Settled        : $314,050.00 (1,412 rows)\nAWS Pending        :   $4,850.00 (8 rows) -> Safe Runbook Issued'
        }
      ]
    }
  ];

  let scenIdx = 0;
  let stepIdx = 0;

  const scenTabs = document.querySelectorAll('.example-tab[data-scen]');
  const flowStepPill = document.getElementById('flow-step-pill');
  const flowStepTitle = document.getElementById('flow-step-title');
  const flowDots = document.getElementById('flow-dots');
  const btnFlowPrev = document.getElementById('btn-flow-prev');
  const btnFlowNext = document.getElementById('btn-flow-next');

  const nodeUser = document.getElementById('node-user');
  const nodeAgent = document.getElementById('node-agent');
  const nodeMcp = document.getElementById('node-mcp');
  const conn1 = document.getElementById('conn-1');
  const conn2 = document.getElementById('conn-2');
  const conn3 = document.getElementById('conn-3');

  const dbCardPg = document.getElementById('db-card-pg');
  const dbCardMysql = document.getElementById('db-card-mysql');
  const dbCardBq = document.getElementById('db-card-bq');

  const chatStatusPill = document.getElementById('chat-status-pill');
  const chatUserMsg = document.getElementById('chat-user-msg');
  const chatAgentMsg = document.getElementById('chat-agent-msg');

  const hopRouteLabel = document.getElementById('hop-route-label');
  const hopLatencyPill = document.getElementById('hop-latency-pill');
  const hopPlainDesc = document.getElementById('hop-plain-desc');
  const hopKeyResult = document.getElementById('hop-key-result');
  const hopCodeTitle = document.getElementById('hop-code-title');
  const hopCodeSnippet = document.getElementById('hop-code-snippet');

  function applyNodeColor(el, color) {
    el.classList.remove('is-lit-blue', 'is-lit-green', 'is-lit-red');
    if (color === 'blue') el.classList.add('is-lit-blue');
    if (color === 'green') el.classList.add('is-lit-green');
    if (color === 'red') el.classList.add('is-lit-red');
  }

  function applyConnector(el, pair) {
    el.textContent = pair[0];
    el.classList.remove('is-active-arrow', 'is-blocked-arrow');
    if (pair[1] === 'active') el.classList.add('is-active-arrow');
    if (pair[1] === 'blocked') el.classList.add('is-blocked-arrow');
  }

  function renderMainFlow() {
    const scen = SCENARIOS[scenIdx];
    const total = scen.steps.length;
    const step = scen.steps[stepIdx];

    btnFlowPrev.disabled = stepIdx === 0;
    btnFlowNext.disabled = stepIdx === total - 1;
    flowStepPill.textContent = 'Step ' + String(stepIdx + 1) + ' of ' + String(total);
    flowStepTitle.textContent = step.title;

    // Step dots
    const dots = [];
    for (let i = 0; i < total; i += 1) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'step-dot';
      if (i < stepIdx) btn.classList.add('is-done');
      if (i === stepIdx) btn.classList.add('is-current');
      btn.textContent = String(i + 1);
      btn.setAttribute('aria-label', 'Step ' + String(i + 1));
      btn.addEventListener('click', () => {
        stepIdx = i;
        renderMainFlow();
      });
      dots.push(btn);
    }
    flowDots.replaceChildren(...dots);

    // Visual architecture highlights
    applyNodeColor(nodeUser, step.nodes.user);
    applyNodeColor(nodeAgent, step.nodes.agent);
    applyNodeColor(nodeMcp, step.nodes.mcp);

    applyConnector(conn1, step.arrows.c1);
    applyConnector(conn2, step.arrows.c2);
    applyConnector(conn3, step.arrows.c3);

    dbCardPg.classList.toggle('is-hit-aws', Boolean(step.nodes.pg));
    dbCardMysql.classList.toggle('is-hit-aws', Boolean(step.nodes.mysql));
    dbCardBq.classList.toggle('is-hit-bq', Boolean(step.nodes.bq));

    // Chat thread
    chatUserMsg.textContent = scen.userQuestion;
    const isLast = stepIdx === total - 1;
    if (isLast) {
      chatStatusPill.className = 'pill pill-green';
      chatStatusPill.textContent = 'ANSWER DELIVERED';
      chatAgentMsg.classList.remove('is-waiting');
      chatAgentMsg.textContent = scen.finalAnswer;
    } else {
      chatStatusPill.className = 'pill pill-blue';
      chatStatusPill.textContent = 'HOP ' + String(stepIdx + 1) + ' / ' + String(total);
      chatAgentMsg.classList.add('is-waiting');
      chatAgentMsg.textContent =
        'Analytics Agent is executing Step ' +
        String(stepIdx + 1) +
        ' (' +
        step.title +
        '). Click "Next >" to continue...';
    }

    // Hop inspector
    hopRouteLabel.textContent = step.route;
    hopLatencyPill.textContent = step.latency;
    hopPlainDesc.textContent = step.desc;
    hopKeyResult.textContent = step.keyResult;
    hopCodeTitle.textContent = step.codeTitle;
    hopCodeSnippet.textContent = step.code;
  }

  scenTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      scenIdx = Number(tab.getAttribute('data-scen') || '0');
      stepIdx = 0;
      scenTabs.forEach((t) => {
        const active = t === tab;
        t.classList.toggle('is-selected', active);
        t.setAttribute('aria-selected', String(active));
      });
      renderMainFlow();
    });
  });

  btnFlowPrev.addEventListener('click', () => {
    if (stepIdx > 0) {
      stepIdx -= 1;
      renderMainFlow();
    }
  });

  btnFlowNext.addEventListener('click', () => {
    if (stepIdx < SCENARIOS[scenIdx].steps.length - 1) {
      stepIdx += 1;
      renderMainFlow();
    }
  });

  /* ==========================================================================
     2. SLIDE 02 EMBEDDED < PREV / NEXT > WALKTHROUGH
     ========================================================================== */
  const SLIDE2_HOPS = [
    {
      title: 'User asks VIP dispute question in Gemini Enterprise',
      tones: { user: 'blue', agent: 'blue', mcp: '', db: '' },
      dbLabel: 'AWS PG + MySQL + GCP BQ',
      heading: '1. Business User → Analytics Agent (Argolis)',
      desc: 'Analyst asks why VIP customer n***n@example-bank.com has a disputed $4,850 wire. The ADK agent plans 3 parallel lookups.',
      result: 'Intent decomposed across AWS Postgres, AWS MySQL & GCP BigQuery',
      codeLabel: 'User Question → Agent Plan',
      latency: '18 ms',
      code: 'Question: "Check AWS accounts, tickets & BQ fraud risk for n***n@example-bank.com"\nPlan    : [AWS Postgres] + [AWS MySQL] + [GCP BigQuery]'
    },
    {
      title: 'Analytics Agent calls Cloud Run MCP Server over mTLS',
      tones: { user: '', agent: 'blue', mcp: 'blue', db: '' },
      dbLabel: 'Preparing SQL bridges',
      heading: '2. Analytics Agent → Cloud Run MCP',
      desc: 'Agent authenticates via SPIFFE identity (zero static keys) and dispatches read-only MCP tool calls.',
      result: 'Zero-trust mTLS + SELECT-only guardrail verified',
      codeLabel: 'MCP Tool Call (JSON-RPC)',
      latency: '14 ms',
      code: '{\n  "method": "tools/call",\n  "params": { "name": "query_postgres_db", "email": "n***n@example-bank.com" }\n}'
    },
    {
      title: 'MCP queries AWS PostgreSQL (finance_db) live',
      tones: { user: '', agent: '', mcp: 'blue', db: 'amber' },
      dbLabel: 'Active: AWS PostgreSQL',
      heading: '3. Cloud Run MCP ⇄ AWS PostgreSQL',
      desc: 'Fetches real-time checking balance and wire status over HA VPN from the AWS RDS Read Replica.',
      result: 'Returned: VIP_PLATINUM · $184,220.50 · $4,850 PENDING_DISPUTE',
      codeLabel: 'AWS PostgreSQL SQL',
      latency: '42 ms',
      code: "SELECT c.tier, a.balance, t.status\nFROM customers c JOIN accounts a USING (customer_id)\nJOIN transactions t USING (account_id)\nWHERE c.email = 'n***n@example-bank.com';"
    },
    {
      title: 'MCP queries AWS MySQL (engagement_db) live',
      tones: { user: '', agent: 'blue', mcp: 'blue', db: 'amber' },
      dbLabel: 'Active: AWS MySQL',
      heading: '4. Cloud Run MCP ⇄ AWS MySQL',
      desc: 'Checks open support tickets and VIP fee-waiver eligibility in AWS RDS MySQL.',
      result: 'Returned: Open P1 Ticket TCK-88412 · Fee Waiver Eligible',
      codeLabel: 'AWS MySQL SQL',
      latency: '39 ms',
      code: "SELECT ticket_id, priority, status\nFROM support_tickets\nWHERE customer_email = 'n***n@example-bank.com' LIMIT 3;"
    },
    {
      title: 'MCP queries 66M-row GCP BigQuery (argolis.ccca)',
      tones: { user: '', agent: 'blue', mcp: 'blue', db: 'green' },
      dbLabel: 'Active: GCP BigQuery (66M)',
      heading: '5. BigQuery MCP ⇄ GCP BigQuery',
      desc: 'Pushes analytical GoogleSQL into 50M risk profiles + 16M app events in Argolis BigQuery.',
      result: 'Returned: Fraud Probability 0.91 · Untrusted-Device MFA Failure',
      codeLabel: 'GCP BigQuery GoogleSQL',
      latency: '610 ms',
      code: "SELECT r.fraud_probability, e.event_type\nFROM `argolis.ccca.customer_risk_profiles` r\nJOIN `argolis.ccca.app_events` e USING (customer_email)\nWHERE r.customer_email = 'n***n@example-bank.com';"
    },
    {
      title: 'Analytics Agent delivers unified recommendation to User',
      tones: { user: 'green', agent: 'green', mcp: '', db: 'green' },
      dbLabel: '3 DBs Synthesized · 0 Copy',
      heading: '6. Analytics Agent → Business User',
      desc: 'Synthesizes all 3 responses into a single auditable fraud & retention decision in 1.12 seconds.',
      result: 'Hold $4,850 wire, escalate TCK-88412 & waive $35 VIP fee',
      codeLabel: 'Executive Answer Delivered',
      latency: '1.12 s Total',
      code: 'AWS Postgres : $184,220 VIP balance | $4,850 PENDING_DISPUTE\nAWS MySQL    : Ticket TCK-88412 (P1) | Waiver Eligible\nGCP BigQuery : 0.91 Fraud Score      | MFA Anomaly Confirmed'
    }
  ];

  let s2Idx = 0;
  const s2Pill = document.getElementById('s2-pill');
  const s2Title = document.getElementById('s2-title');
  const btnS2Prev = document.getElementById('btn-s2-prev');
  const btnS2Next = document.getElementById('btn-s2-next');
  const s2Nodes = {
    user: document.getElementById('s2-node-user'),
    agent: document.getElementById('s2-node-agent'),
    mcp: document.getElementById('s2-node-mcp'),
    db: document.getElementById('s2-node-db')
  };
  const s2DbLabel = document.getElementById('s2-db-label');
  const s2CardHeading = document.getElementById('s2-card-heading');
  const s2CardDesc = document.getElementById('s2-card-desc');
  const s2CardResult = document.getElementById('s2-card-result');
  const s2CodeLabel = document.getElementById('s2-code-label');
  const s2Latency = document.getElementById('s2-latency');
  const s2Code = document.getElementById('s2-code');

  function renderSlide2Flow() {
    const total = SLIDE2_HOPS.length;
    const hop = SLIDE2_HOPS[s2Idx];
    btnS2Prev.disabled = s2Idx === 0;
    btnS2Next.disabled = s2Idx === total - 1;
    s2Pill.textContent = 'Hop ' + String(s2Idx + 1) + ' of ' + String(total);
    s2Title.textContent = hop.title;

    Object.entries(s2Nodes).forEach(([k, el]) => {
      el.classList.remove('is-lit-blue', 'is-lit-amber', 'is-lit-green');
      const tone = hop.tones[k];
      if (tone === 'blue') el.classList.add('is-lit-blue');
      if (tone === 'amber') el.classList.add('is-lit-amber');
      if (tone === 'green') el.classList.add('is-lit-green');
    });

    s2DbLabel.textContent = hop.dbLabel;
    s2CardHeading.textContent = hop.heading;
    s2CardDesc.textContent = hop.desc;
    s2CardResult.textContent = hop.result;
    s2CodeLabel.textContent = hop.codeLabel;
    s2Latency.textContent = hop.latency;
    s2Code.textContent = hop.code;
  }

  btnS2Prev.addEventListener('click', () => {
    if (s2Idx > 0) {
      s2Idx -= 1;
      renderSlide2Flow();
    }
  });

  btnS2Next.addEventListener('click', () => {
    if (s2Idx < SLIDE2_HOPS.length - 1) {
      s2Idx += 1;
      renderSlide2Flow();
    }
  });

  /* ==========================================================================
     3. MODE SWITCHER & 5-SLIDE PITCH DECK NAVIGATION
     ========================================================================== */
  const btnModeBrief = document.getElementById('btn-mode-brief');
  const btnModeDeck = document.getElementById('btn-mode-deck');
  const btnHeroLaunchDeck = document.getElementById('btn-hero-launch-deck');
  const btnBackBrief = document.getElementById('btn-back-brief');

  function setMode(mode) {
    const isDeck = mode === 'deck';
    document.body.setAttribute('data-view-mode', isDeck ? 'deck' : 'brief');
    btnModeBrief.classList.toggle('is-active', !isDeck);
    btnModeBrief.setAttribute('aria-selected', String(!isDeck));
    btnModeDeck.classList.toggle('is-active', isDeck);
    btnModeDeck.setAttribute('aria-selected', String(isDeck));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  btnModeBrief.addEventListener('click', () => setMode('brief'));
  btnModeDeck.addEventListener('click', () => setMode('deck'));
  btnHeroLaunchDeck.addEventListener('click', () => setMode('deck'));
  btnBackBrief.addEventListener('click', () => setMode('brief'));

  const slides = document.querySelectorAll('.slide-card[data-slide]');
  const slideTabs = document.querySelectorAll('.slide-tab-pill[data-goto-slide]');
  const btnPrevSlide = document.getElementById('btn-prev-slide');
  const btnNextSlide = document.getElementById('btn-next-slide');
  const slideCounter = document.getElementById('slide-counter');

  let currentSlide = 0;

  function renderDeck() {
    const total = slides.length;
    slides.forEach((s, idx) => s.classList.toggle('is-active', idx === currentSlide));
    slideTabs.forEach((t, idx) => t.classList.toggle('is-active', idx === currentSlide));
    btnPrevSlide.disabled = currentSlide === 0;
    btnNextSlide.disabled = currentSlide === total - 1;
    slideCounter.textContent =
      'Slide ' + String(currentSlide + 1).padStart(2, '0') + ' / ' + String(total).padStart(2, '0');
  }

  slideTabs.forEach((tab) => {
    tab.addEventListener('click', () => {
      currentSlide = Number(tab.getAttribute('data-goto-slide') || '0');
      renderDeck();
    });
  });

  btnPrevSlide.addEventListener('click', () => {
    if (currentSlide > 0) {
      currentSlide -= 1;
      renderDeck();
    }
  });

  btnNextSlide.addEventListener('click', () => {
    if (currentSlide < slides.length - 1) {
      currentSlide += 1;
      renderDeck();
    }
  });

  document.addEventListener('keydown', (e) => {
    if (document.body.getAttribute('data-view-mode') !== 'deck') return;
    if (e.key === 'ArrowRight' && currentSlide < slides.length - 1) {
      currentSlide += 1;
      renderDeck();
    } else if (e.key === 'ArrowLeft' && currentSlide > 0) {
      currentSlide -= 1;
      renderDeck();
    }
  });

  /* ==========================================================================
     4. JUMP-BAR SCROLL HIGHLIGHT
     ========================================================================== */
  const jumpLinks = document.querySelectorAll('.jump-link[data-jump]');
  const pitchSections = document.querySelectorAll('.pitch-section[id]');

  if ('IntersectionObserver' in window) {
    const obs = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            const id = entry.target.getAttribute('id');
            jumpLinks.forEach((lnk) => {
              lnk.classList.toggle('is-active', lnk.getAttribute('data-jump') === id);
            });
          }
        });
      },
      { rootMargin: '-20% 0px -65% 0px', threshold: 0.05 }
    );
    pitchSections.forEach((sec) => obs.observe(sec));
  }

  /* Initial Render */
  renderMainFlow();
  renderSlide2Flow();
  renderDeck();
});

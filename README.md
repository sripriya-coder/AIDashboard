# JIRA Dashboard Generator

A Jira dashboard application with Atlassian OAuth, prompt-driven analytics, portfolio health views, editable Jira task workflows, and Excel export backed by real Jira data.

## What It Does

This app combines three layers in one UI:

- Jira-connected dashboard generation from natural-language prompts
- Project-level delivery intelligence with forecast and recommended actions
- Portfolio-level overall health across multiple projects with optional LLM summarization

It is designed for multi-user usage. Each logged-in user gets isolated session state, dashboard history, selected Jira site, selected project, and cached Jira responses.

## Key Features

### Authentication and tenancy

- Atlassian OAuth login flow
- Multi-site Jira access with site picker
- Project picker with live project switching
- Per-user dashboard storage and per-user cache isolation
- Optional Jira API token fallback for non-OAuth environments

### Dashboard views and UX

- `Compact` view for day-to-day prompting and dashboard generation
- `Executive` view for project-focused operational summaries
- `Overall` view for portfolio-wide health across accessible projects
- Dark mode and accessibility mode
- AI badges for AI-supported intelligence areas

### Prompt-driven Jira analytics

- Single-chart dashboard generation from prompts
- Multi-chart dashboard generation for a project overview
- Real Jira-backed exports instead of sample-only data when data is available
- Chart auto-selection and metric fallback for small result sets

Supported chart types:

- Bar
- Pie / donut
- Line
- Metrics
- Gantt / timeline

### Jira issue workflows

- List issues by project or sprint
- Fetch issue details by key
- Show sprint lists
- Show assignee breakdowns
- Create Jira tasks
- Edit Jira task summary, assignee, priority, and status
- Browse project releases / versions

### Project intelligence

- Rules-based project health scoring
- Forecast summary from recent intake vs completion trend
- Risk indicators:
  - open issues
  - overdue issues
  - blocked issues
  - high-priority open issues
  - unassigned issues
  - stale in-progress work
- Recommended actions generated from project conditions
- Sprint velocity widget
- Assignment suggestions for unassigned tickets
- Optional LLM enrichment for executive summary, forecast, recommendations, and health refinement

### Portfolio intelligence

- Cross-project health aggregation across accessible Jira projects
- Overall risk label and average health score
- Portfolio-wide blocker and open-issue totals
- Top risky projects list
- Portfolio recommendations
- Optional LLM portfolio summary for high-level executive commentary

### Export

- Excel export per generated dashboard
- Summary sheet with aggregated chart data
- Jira Issues sheet with detailed issue rows
- Embedded chart image sheet

## Tech Stack

- Backend: Flask
- Auth: Authlib + Flask-Session
- Jira access: Atlassian OAuth, Jira REST APIs, MCP client/server integration
- LLM: LangChain `ChatOpenAI` against an OpenAI-compatible endpoint
- Charting: Plotly, Matplotlib, Seaborn, Chart.js
- Export: OpenPyXL, Pandas
- Frontend: Jinja templates, Bootstrap, Bootstrap Icons, vanilla JavaScript

## Project Structure

```text
JIRA-Dashboard/
├── server.py
├── jira_mcp_server.py
├── mcp_client.py
├── mcp_tools.py
├── requirements.txt
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── select_project.html
│   └── select_site.html
├── static/
│   └── charts/
└── vscode/
    └── launch.json
```

## Setup

### 1. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Minimum configuration:

```bash
# Flask
export FLASK_SECRET_KEY="replace-me"

# Atlassian OAuth
export JIRA_CLIENT_ID="your-client-id"
export JIRA_CLIENT_SECRET="your-client-secret"

# LLM endpoint (optional but recommended for richer summaries)
export QWEN_API_KEY="your-llm-key"
export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export QWEN_MODEL="qwen-plus"
export QWEN_MODEL_FAST="qwen-plus"
```

Optional Jira API token fallback:

```bash
export JIRA_SERVER="https://your-domain.atlassian.net"
export JIRA_USER_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-api-token"
```

Optional timeout and portfolio tuning:

```bash
export LLM_TIMEOUT_DEFAULT_SECONDS=30
export LLM_TIMEOUT_FAST_SECONDS=18
export LLM_TIMEOUT_INTELLIGENCE_SECONDS=8
export LLM_TIMEOUT_ASSIGNMENT_SECONDS=6

export LLM_RETRIES_DEFAULT=1
export LLM_RETRIES_FAST=1
export LLM_RETRIES_INTELLIGENCE=0
export LLM_RETRIES_ASSIGNMENT=0

export INTELLIGENCE_SUMMARY_MAX_SECONDS=20
export INTELLIGENCE_FULL_MAX_SECONDS=55
export INTELLIGENCE_ASSIGNMENT_MIN_SECONDS=10

export PORTFOLIO_MAX_PROJECTS=10
export PORTFOLIO_TOP_RISKY_LIMIT=5

export PORT=5000
export DEBUG=true
```

### 4. Run the server

```bash
python server.py
```

### 5. Open the app

```text
http://localhost:5000/login
```

## Main Screens

- Login page for Atlassian authentication
- Site selection page when the user has access to multiple Jira sites
- Project selection page for initial project choice
- Main dashboard page with:
  - prompt workspace
  - Jira task panel
  - delivery intelligence panel
  - generated dashboards
  - density modes: Compact, Executive, Overall

## API Overview

### Authentication and selection

- `GET /login` - login page
- `GET /auth/login` - start Atlassian OAuth
- `GET /auth/callback` - OAuth callback
- `GET /auth/status` - current auth/session status
- `GET /auth/logout` - logout and clear user state
- `GET /select-site` - site picker UI
- `POST /select-site` - persist selected site
- `GET /select-project` - project picker UI
- `POST /select-project` - persist selected project
- `POST /api/project/select` - switch active project from the dashboard UI

### Dashboard generation and export

- `GET /` - main dashboard UI
- `POST /api/generate` - prompt-driven chart generation, dashboard generation, and Jira actions
- `GET /api/dashboards` - list current user dashboards
- `GET /api/dashboard/<dashboard_id>` - get one dashboard
- `PUT /api/dashboard/<dashboard_id>` - update a dashboard prompt and regenerate
- `GET /api/export/<dashboard_id>` - export dashboard to Excel
- `GET /api/metrics` - dashboard usage metrics

### Jira data and task operations

- `GET /api/jira/projects` - list available Jira projects for the selected site
- `GET /api/jira/tasks` - list recent Jira tasks in the active project
- `POST /api/jira/tasks` - create a Jira task in the active project
- `GET /api/jira/tasks/<task_id>/edit-data` - fetch transitions, assignable users, and priorities
- `PUT /api/jira/tasks/<task_id>` - update summary, assignee, priority, and workflow state
- `GET /api/jira/releases` - list release/version progress for the active project

### Intelligence APIs

- `GET /api/project/intelligence?mode=summary` - fast rules-based project intelligence
- `GET /api/project/intelligence?mode=velocity` - sprint velocity only
- `GET /api/project/intelligence?mode=full` - full project intelligence with optional LLM enrichment
- `GET /api/portfolio/intelligence?mode=full` - portfolio-wide health with optional LLM summary

## Example Prompts

Charts and dashboards:

- `Create a pie chart for SCRUM issue status and export to excel`
- `Create a gantt chart for SCRUM roadmap`
- `Generate a multi chart dashboard for SCRUM`
- `Show issue breakdown by assignee for SCRUM`

Issue and sprint queries:

- `List all issues in SCRUM`
- `List all in progress issues in SCRUM`
- `Show sprint list for SCRUM`
- `Show details of SCRUM-123`
- `Who is working in SCRUM`

Task actions:

- `Create task: Fix login flow in SCRUM`
- `Create ticket for release validation in SCRUM`

Delivery intelligence:

- `Show burndown outlook for to do items in SCRUM`
- `What is the delivery risk in SCRUM?`
- `Which project work looks blocked right now?`

## Operational Notes

- The UI uses the currently selected project for prompts, releases, task lists, and project intelligence.
- Project intelligence defaults to a faster summary mode; richer LLM synthesis is used selectively where the app explicitly asks for it.
- Portfolio intelligence uses a single aggregate LLM summary over evaluated projects rather than making one LLM call per project.
- Excel export tries to preserve real Jira-backed chart data whenever it is available.
- All dashboard state is stored in memory per user session. This is suitable for demos and hackathon usage, but not durable storage.
- Session storage is filesystem-backed under `/tmp/jira_dashboard_sessions`.

## Recommended Next Hardening Steps

- Move in-memory dashboard storage to a persistent data store
- Externalize session storage for multi-instance deployment
- Add automated tests for prompt routing and intelligence endpoints
- Add role-aware access controls if the app is used beyond internal demo environments
- Add rate limiting and structured audit logging for production deployment
# AIDashboard

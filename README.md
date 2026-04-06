# JIRA Dashboard Generator

Dynamic Jira dashboard generation with OAuth login, project switching, chart creation, Jira issue actions, and Excel export.

## Features

- Jira OAuth login (Atlassian)
- Multi-tenant session isolation per logged-in user
- Site selection and project selection
- Dynamic chart generation:
	- Pie
	- Bar
	- Line
	- Metrics
- Jira operations:
	- List issues
	- Get issue details
	- Get sprint list
	- Project summary breakdowns
	- Create and update issues
- Export to Excel:
	- Summary sheet
	- Jira Issues sheet (detailed issue rows)
	- Chart image sheet

## Tech Stack

- Backend: Flask
- Auth: Authlib (Atlassian OAuth)
- LLM: LangChain OpenAI-compatible client
- Jira integration: MCP stdio server/client
- Charts: Matplotlib + Seaborn
- Data export: Pandas + OpenPyXL
- Frontend: Jinja templates + Vanilla JS

## Project Structure

```text
JIRA-Dashboard/
├── server.py
├── jira_mcp_server.py
├── mcp_client.py
├── requirements.txt
├── templates/
│   ├── index.html
│   ├── login.html
│   ├── select_site.html
│   └── select_project.html
└── static/
```

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Configure environment variables:

```bash
# Flask
export FLASK_SECRET_KEY="replace-me"

# OAuth (Atlassian)
export JIRA_CLIENT_ID="your-client-id"
export JIRA_CLIENT_SECRET="your-client-secret"

# LLM (OpenAI-compatible endpoint)
export QWEN_API_KEY="your-llm-key"
export QWEN_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export QWEN_MODEL="qwen-plus"
export QWEN_MODEL_FAST="qwen-plus"

# Optional API token fallback (when OAuth is not used)
export JIRA_SERVER="https://your-domain.atlassian.net"
export JIRA_USER_EMAIL="you@example.com"
export JIRA_API_TOKEN="your-api-token"
```

3. Run server:

```bash
python server.py
```

4. Open:

```text
http://localhost:5000/login
```

## Main Endpoints

- `GET /` - Dashboard UI
- `POST /api/generate` - Prompt-driven chart/issue actions
- `GET /api/dashboards` - List dashboards for current user
- `GET /api/dashboard/<dashboard_id>` - Get dashboard
- `PUT /api/dashboard/<dashboard_id>` - Update dashboard prompt
- `GET /api/export/<dashboard_id>` - Export dashboard Excel
- `GET /api/jira/projects` - List projects for selected site
- `POST /api/project/select` - Switch active Jira project
- `GET /api/jira/tasks` - List tasks
- `POST /api/jira/tasks` - Create task
- `PUT /api/jira/tasks/<task_id>` - Update task
- `GET /api/metrics` - Chart usage metrics

## Example Prompts

- `Create a pie chart for SCRUM issue status and export to excel`
- `List all issues in SCRUM`
- `Show sprint list for SCRUM`
- `Who is working in SCRUM`
- `Create task: Fix login flow in SCRUM`
- `Show details of SCRUM-123`

## Notes

- Project-aware prompt buttons and Jira panels in UI use the currently selected project.
- Excel export includes both aggregated chart data and detailed Jira issue rows.
- If dependencies are missing, ensure you run with the same Python interpreter where requirements were installed.

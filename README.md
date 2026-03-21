# Dynamic Dashboard Generation

AI-powered dashboard generation using LangGraph, LLM, and Qwen Jira MCP integration.

## Features

✅ **Dynamic Chart Generation**
- Pie charts
- Bar charts  
- Line charts
- Metrics/KPI dashboards

✅ **Create & Update**
- Natural language prompts to create dashboards
- Update existing dashboards with new prompts

✅ **Jira Task Assignment**
- Create Jira tasks from dashboards
- Assign tasks to team members
- Track task status and priority

✅ **Excel Export**
- Export dashboard data to Excel (.xlsx)
- Export to CSV format
- Includes metadata and timestamps

## Installation

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Set environment variables (optional):**
```bash
export OPENAI_API_KEY='your-api-key'
```

3. **Run the server:**
```bash
python server.py
```

4. **Access the application:**
Open your browser and navigate to: `http://localhost:5000`

## Usage Examples

### Create Charts

**Pie Chart:**
```
Create a pie chart showing sales distribution by region
```

**Bar Chart:**
```
Generate a bar chart for quarterly revenue performance
```

**Metrics Dashboard:**
```
Show team metrics with KPIs for each department
```

### Export Data

```
Create a sales chart and export to Excel
```

### Jira Integration

```
Create a dashboard and assign a Jira task to track progress
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/generate` | POST | Generate dashboard from prompt |
| `/api/dashboards` | GET | List all dashboards |
| `/api/dashboard/<id>` | GET | Get specific dashboard |
| `/api/dashboard/<id>` | PUT | Update dashboard |
| `/api/export/<id>` | GET | Export dashboard to Excel |
| `/api/jira/tasks` | GET | List Jira tasks |
| `/api/jira/tasks` | POST | Create Jira task |
| `/api/jira/tasks/<id>` | PUT | Update Jira task |
| `/api/metrics` | GET | Get system metrics |

## Architecture

### LangGraph Workflow

The application uses a LangGraph-based state machine with the following nodes:

1. **Parse Intent** - Detects user intent (create, update, export, jira)
2. **Extract Data** - Identifies data source and requirements
3. **Generate Chart** - Creates visualization (pie, bar, line, metrics)
4. **Handle Jira** - Creates/assigns Jira tasks via MCP
5. **Export Data** - Exports to Excel/CSV format
6. **Format Response** - Returns formatted response to user

### Technology Stack

- **Backend:** Flask + LangGraph
- **LLM:** OpenAI GPT-4 (via LangChain)
- **Visualization:** Matplotlib + Seaborn
- **Data Processing:** Pandas
- **Frontend:** Bootstrap 5 + Vanilla JS
- **Jira Integration:** MCP Server (simulated in demo)

## Project Structure

```
DASHBOARD_GENERATION/
├── server.py              # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   └── index.html        # Frontend UI
├── static/
│   ├── charts/          # Generated chart images
│   ├── css/             # Custom stylesheets
│   └── js/              # Custom JavaScript
└── .env                 # Environment variables (optional)
```

## Example Prompts

Try these example prompts in the application:

1. "Create a pie chart showing project status distribution"
2. "Generate a bar chart for quarterly sales performance"
3. "Show team metrics dashboard with KPIs"
4. "Create sales chart and export to Excel"
5. "Update the chart to show monthly instead of quarterly data"
6. "Assign a Jira task to track this dashboard"

## Jira MCP Integration

For production Jira integration:

1. Set up Jira MCP server
2. Configure Jira credentials in environment:
```bash
export JIRA_API_TOKEN='your-token'
export JIRA_SERVER='https://your-domain.atlassian.net'
export JIRA_USER_EMAIL='your-email'
export JIRA_PROJECT_KEY='PROJ'
```

3. Update the `handle_jira` method in `server.py` to use actual Jira API calls

## License

MIT License

## Support

For issues and feature requests, please create an issue in the repository.

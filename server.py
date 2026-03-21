"""
Dynamic Dashboard Generation Server
Features:
- Dynamic graph generation (pie chart, bar chart, metrics)
- Create/Update dashboard components
- Jira task assignment via MCP
- Excel export functionality
- Prompt-based interface using LangGraph & Qwen
"""

import os
import json
import asyncio
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
from io import BytesIO
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import uuid

# LangGraph imports
from langgraph.graph import StateGraph, END, START
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

app = Flask(__name__)
CORS(app)

# Configuration
app.config['UPLOAD_FOLDER'] = 'static/charts'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# In-memory storage for dashboards
dashboards_store: Dict[str, Dict] = {}
jira_tasks_store: List[Dict] = []


# ==================== Data Models ====================

@dataclass
class ChartConfig:
    chart_id: str
    chart_type: str  # pie, bar, line, metrics
    title: str
    data: Dict[str, Any]
    config: Dict[str, Any]
    created_at: str
    updated_at: str


@dataclass
class DashboardState:
    """State for LangGraph workflow"""
    prompt: str
    intent: str
    chart_type: Optional[str]
    data_source: Optional[str]
    chart_config: Optional[Dict]
    jira_task: Optional[Dict]
    export_format: Optional[str]
    response: str
    errors: List[str]


# ==================== LangGraph Workflow ====================

class DashboardGraph:
    """LangGraph-based workflow for dashboard generation"""
    
    def __init__(self):
        self.llm = self._initialize_llm()
        self.graph = self._build_graph()
    
    def _initialize_llm(self):
        """Initialize LLM - can use OpenAI or other providers"""
        # For production, configure with actual API keys
        api_key = os.getenv('OPENAI_API_KEY', 'your-api-key')
        try:
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                api_key=api_key
            )
            return llm
        except Exception:
            # Fallback to mock LLM for demo
            return None
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(state_schema=dict)
        
        # Add nodes
        workflow.add_node("parse_intent", self.parse_intent)
        workflow.add_node("extract_data", self.extract_data)
        workflow.add_node("generate_chart", self.generate_chart)
        workflow.add_node("handle_jira", self.handle_jira)
        workflow.add_node("export_data", self.export_data)
        workflow.add_node("format_response", self.format_response)
        
        # Define edges
        workflow.add_edge(START, "parse_intent")
        workflow.add_edge("parse_intent", "extract_data")
        workflow.add_edge("extract_data", "generate_chart")
        workflow.add_conditional_edges(
            "generate_chart",
            self.route_after_chart,
            {
                "jira": "handle_jira",
                "export": "export_data",
                "done": "format_response"
            }
        )
        workflow.add_edge("handle_jira", "format_response")
        workflow.add_edge("export_data", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def parse_intent(self, state: Dict) -> Dict:
        """Parse user intent from prompt"""
        prompt_lower = state["prompt"].lower()
        
        # Detect intent
        if any(word in prompt_lower for word in ['create', 'make', 'generate', 'build']):
            state["intent"] = "create"
        elif any(word in prompt_lower for word in ['update', 'modify', 'change', 'edit']):
            state["intent"] = "update"
        elif any(word in prompt_lower for word in ['assign', 'jira', 'task']):
            state["intent"] = "jira"
        elif any(word in prompt_lower for word in ['export', 'download', 'excel']):
            state["intent"] = "export"
        else:
            state["intent"] = "query"
        
        # Detect chart type
        if 'pie' in prompt_lower:
            state["chart_type"] = "pie"
        elif 'bar' in prompt_lower or 'column' in prompt_lower:
            state["chart_type"] = "bar"
        elif 'line' in prompt_lower:
            state["chart_type"] = "line"
        elif 'metric' in prompt_lower or 'kpi' in prompt_lower:
            state["chart_type"] = "metrics"
        
        # Detect export format
        if 'excel' in prompt_lower or 'xlsx' in prompt_lower:
            state["export_format"] = "excel"
        elif 'csv' in prompt_lower:
            state["export_format"] = "csv"
        
        state["response"] = f"Intent detected: {state['intent']}"
        return state
    
    def extract_data(self, state: Dict) -> Dict:
        """Extract data requirements from prompt"""
        # This would typically use LLM to extract structured data
        # For demo, we'll use pattern matching
        
        prompt_lower = state["prompt"].lower()
        
        # Sample data extraction
        if 'sales' in prompt_lower:
            state["data_source"] = "sales"
            state["chart_config"] = {
                "labels": ["Q1", "Q2", "Q3", "Q4"],
                "values": [45000, 52000, 38000, 61000],
                "title": "Quarterly Sales Performance"
            }
        elif 'project' in prompt_lower or 'task' in prompt_lower:
            state["data_source"] = "projects"
            state["chart_config"] = {
                "labels": ["Completed", "In Progress", "To Do", "Blocked"],
                "values": [12, 8, 5, 2],
                "title": "Project Status Distribution"
            }
        elif 'team' in prompt_lower or 'employee' in prompt_lower:
            state["data_source"] = "team"
            state["chart_config"] = {
                "labels": ["Engineering", "Design", "Marketing", "Sales", "Support"],
                "values": [25, 8, 12, 15, 10],
                "title": "Team Distribution by Department"
            }
        else:
            # Default sample data
            state["data_source"] = "default"
            state["chart_config"] = {
                "labels": ["Category A", "Category B", "Category C", "Category D"],
                "values": [35, 25, 25, 15],
                "title": "Data Distribution"
            }
        
        state["response"] += f"\nData source identified: {state['data_source']}"
        return state
    
    def generate_chart(self, state: Dict) -> Dict:
        """Generate chart based on configuration"""
        if not state.get("chart_config"):
            state.setdefault("errors", []).append("No chart configuration available")
            return state
        
        chart_type = state.get("chart_type") or "bar"
        chart_id = str(uuid.uuid4())[:8]
        
        try:
            # Create chart
            fig, ax = plt.subplots(figsize=(10, 6))
            
            colors = sns.color_palette("husl", len(state["chart_config"]["labels"]))
            
            if chart_type == "pie":
                wedges, texts, autotexts = ax.pie(
                    state["chart_config"]["values"],
                    labels=state["chart_config"]["labels"],
                    autopct='%1.1f%%',
                    colors=colors,
                    startangle=90
                )
                ax.set_title(state["chart_config"]["title"], fontsize=14, fontweight='bold')
            elif chart_type == "bar":
                bars = ax.bar(
                    state["chart_config"]["labels"],
                    state["chart_config"]["values"],
                    color=colors
                )
                ax.set_title(state["chart_config"]["title"], fontsize=14, fontweight='bold')
                ax.set_xlabel('Categories', fontsize=12)
                ax.set_ylabel('Values', fontsize=12)
                plt.xticks(rotation=45)
                
                # Add value labels on bars
                for bar, value in zip(bars, state["chart_config"]["values"]):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        bar.get_height() + 0.5,
                        f'{value}',
                        ha='center',
                        va='bottom',
                        fontsize=10
                    )
            elif chart_type == "line":
                ax.plot(
                    state["chart_config"]["labels"],
                    state["chart_config"]["values"],
                    marker='o',
                    linewidth=2,
                    markersize=8
                )
                ax.set_title(state["chart_config"]["title"], fontsize=14, fontweight='bold')
                ax.set_xlabel('Categories', fontsize=12)
                ax.set_ylabel('Values', fontsize=12)
                ax.grid(True, alpha=0.3)
            elif chart_type == "metrics":
                # Create metrics cards
                ax.axis('off')
                positions = range(len(state["chart_config"]["labels"]))
                for i, (label, value) in enumerate(zip(
                    state["chart_config"]["labels"],
                    state["chart_config"]["values"]
                )):
                    ax.text(
                        0.5,
                        0.8 - i * 0.2,
                        f'{label}: {value}',
                        ha='center',
                        va='center',
                        fontsize=16,
                        fontweight='bold',
                        bbox=dict(boxstyle='round', facecolor=colors[i], alpha=0.3)
                    )
                ax.set_title(state["chart_config"]["title"], fontsize=14, fontweight='bold', y=0.95)
            
            plt.tight_layout()
            
            # Save chart
            chart_path = f"{app.config['UPLOAD_FOLDER']}/{chart_id}_{chart_type}.png"
            plt.savefig(chart_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            # Store chart config
            state["chart_config"]["chart_id"] = chart_id
            state["chart_config"]["chart_type"] = chart_type
            state["chart_config"]["image_path"] = chart_path
            state["chart_config"]["created_at"] = datetime.now().isoformat()
            
            state["response"] += f"\n{chart_type.upper()} chart generated successfully!"
            
        except Exception as e:
            state.setdefault("errors", []).append(f"Chart generation error: {str(e)}")
        
        return state
    
    def handle_jira(self, state: Dict) -> Dict:
        """Handle Jira task assignment via MCP"""
        # This would integrate with Jira MCP server
        # For demo, we'll simulate the integration
        
        prompt_lower = state["prompt"].lower()
        
        # Extract task details
        task_summary = "Dashboard Task"
        if 'task' in prompt_lower:
            # Try to extract task description
            words = prompt_lower.split()
            task_idx = words.index('task') if 'task' in words else -1
            if task_idx >= 0 and task_idx < len(words) - 1:
                task_summary = ' '.join(words[task_idx:task_idx+4]).title()
        
        jira_task = {
            "task_id": f"DASH-{uuid.uuid4().hex[:6].upper()}",
            "summary": task_summary,
            "description": state["prompt"],
            "assignee": "Unassigned",
            "status": "To Do",
            "priority": "Medium",
            "created_at": datetime.now().isoformat(),
            "dashboard_id": state.get("chart_config", {}).get("chart_id") if state.get("chart_config") else None
        }
        
        # Store in memory (would be Jira API call in production)
        jira_tasks_store.append(jira_task)
        
        state["jira_task"] = jira_task
        state["response"] += f"\nJira task created: {jira_task['task_id']}"
        
        return state
    
    def export_data(self, state: Dict) -> Dict:
        """Export data to Excel or CSV"""
        if not state.get("chart_config"):
            state.setdefault("errors", []).append("No data to export")
            return state
        
        export_format = state.get("export_format") or "excel"
        
        try:
            # Create DataFrame
            df = pd.DataFrame({
                'Category': state["chart_config"]["labels"],
                'Value': state["chart_config"]["values"]
            })
            
            # Add metadata
            df['Generated At'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            df['Chart Type'] = state.get("chart_type") or "bar"
            df['Title'] = state["chart_config"]["title"]
            
            # Export
            buffer = BytesIO()
            
            if export_format == "excel":
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Dashboard Data')
                    # Add formatting
                    worksheet = writer.sheets['Dashboard Data']
                    worksheet.column_dimensions['A'].width = 20
                    worksheet.column_dimensions['B'].width = 15
                buffer.seek(0)
                state["chart_config"]["export_path"] = "excel"
                state["chart_config"]["export_data"] = base64.b64encode(buffer.getvalue()).decode()
                
            elif export_format == "csv":
                df.to_csv(buffer, index=False)
                buffer.seek(0)
                state["chart_config"]["export_path"] = "csv"
                state["chart_config"]["export_data"] = buffer.getvalue().decode()
            
            state["response"] += f"\nData exported to {export_format.upper()}!"
            
        except Exception as e:
            state.setdefault("errors", []).append(f"Export error: {str(e)}")
        
        return state
    
    def format_response(self, state: Dict) -> Dict:
        """Format final response"""
        if state.get("errors"):
            state["response"] = f"Errors occurred:\n" + "\n".join(state["errors"])
        else:
            state["response"] += "\n\nDashboard operation completed successfully!"
        
        return state
    
    def route_after_chart(self, state: Dict) -> str:
        """Route to next node based on intent"""
        if state.get("intent") == "jira" or 'jira' in state.get("prompt", "").lower() or 'assign' in state.get("prompt", "").lower():
            return "jira"
        elif state.get("intent") == "export" or 'export' in state.get("prompt", "").lower() or 'excel' in state.get("prompt", "").lower():
            return "export"
        return "done"
    
    def process(self, prompt: str) -> Dict[str, Any]:
        """Process prompt through the graph"""
        initial_state = {
            "prompt": prompt,
            "intent": "",
            "chart_type": None,
            "data_source": None,
            "chart_config": None,
            "jira_task": None,
            "export_format": None,
            "response": "Processing your request...",
            "errors": []
        }
        
        result = self.graph.invoke(initial_state)
        
        return {
            "response": result.get("response", "Completed"),
            "chart_config": result.get("chart_config"),
            "jira_task": result.get("jira_task"),
            "errors": result.get("errors", [])
        }


# Initialize LangGraph
dashboard_graph = DashboardGraph()


# ==================== Flask Routes ====================

@app.route('/')
def index():
    """Serve the main dashboard page"""
    return render_template('index.html')


@app.route('/api/generate', methods=['POST'])
def generate_dashboard():
    """Generate dashboard based on prompt"""
    data = request.get_json()
    prompt = data.get('prompt', '')
    
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    
    # Process through LangGraph
    result = dashboard_graph.process(prompt)
    
    # Store dashboard if chart was created
    if result.get('chart_config'):
        dashboard_id = result['chart_config'].get('chart_id')
        dashboards_store[dashboard_id] = {
            "id": dashboard_id,
            "prompt": prompt,
            "chart_config": result['chart_config'],
            "jira_task": result.get('jira_task'),
            "created_at": datetime.now().isoformat()
        }
    
    return jsonify(result)


@app.route('/api/dashboard/<dashboard_id>', methods=['GET'])
def get_dashboard(dashboard_id):
    """Get specific dashboard"""
    if dashboard_id not in dashboards_store:
        return jsonify({"error": "Dashboard not found"}), 404
    
    return jsonify(dashboards_store[dashboard_id])


@app.route('/api/dashboard/<dashboard_id>', methods=['PUT'])
def update_dashboard(dashboard_id):
    """Update existing dashboard"""
    if dashboard_id not in dashboards_store:
        return jsonify({"error": "Dashboard not found"}), 404
    
    data = request.get_json()
    prompt = data.get('prompt', '')
    
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    
    # Process update through LangGraph
    result = dashboard_graph.process(prompt)
    
    # Update stored dashboard
    dashboards_store[dashboard_id].update({
        "prompt": prompt,
        "chart_config": result.get('chart_config'),
        "updated_at": datetime.now().isoformat()
    })
    
    if result.get('jira_task'):
        dashboards_store[dashboard_id]['jira_task'] = result['jira_task']
    
    return jsonify({
        "message": "Dashboard updated successfully",
        "dashboard": dashboards_store[dashboard_id]
    })


@app.route('/api/dashboards', methods=['GET'])
def list_dashboards():
    """List all dashboards"""
    return jsonify({
        "dashboards": list(dashboards_store.values()),
        "count": len(dashboards_store)
    })


@app.route('/api/jira/tasks', methods=['GET'])
def get_jira_tasks():
    """Get all Jira tasks"""
    return jsonify({
        "tasks": jira_tasks_store,
        "count": len(jira_tasks_store)
    })


@app.route('/api/jira/tasks', methods=['POST'])
def create_jira_task():
    """Create a new Jira task"""
    data = request.get_json()
    
    task = {
        "task_id": f"DASH-{uuid.uuid4().hex[:6].upper()}",
        "summary": data.get('summary', 'New Task'),
        "description": data.get('description', ''),
        "assignee": data.get('assignee', 'Unassigned'),
        "status": data.get('status', 'To Do'),
        "priority": data.get('priority', 'Medium'),
        "created_at": datetime.now().isoformat(),
        "dashboard_id": data.get('dashboard_id')
    }
    
    jira_tasks_store.append(task)
    
    return jsonify({
        "message": "Task created successfully",
        "task": task
    }), 201


@app.route('/api/jira/tasks/<task_id>', methods=['PUT'])
def update_jira_task(task_id):
    """Update Jira task"""
    task = next((t for t in jira_tasks_store if t['task_id'] == task_id), None)
    
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    data = request.get_json()
    
    # Update fields
    for key in ['summary', 'description', 'assignee', 'status', 'priority']:
        if key in data:
            task[key] = data[key]
    
    task['updated_at'] = datetime.now().isoformat()
    
    return jsonify({
        "message": "Task updated successfully",
        "task": task
    })


@app.route('/api/export/<dashboard_id>', methods=['GET'])
def export_dashboard(dashboard_id):
    """Export dashboard data to Excel"""
    if dashboard_id not in dashboards_store:
        return jsonify({"error": "Dashboard not found"}), 404
    
    dashboard = dashboards_store[dashboard_id]
    chart_config = dashboard.get('chart_config', {})
    
    if not chart_config:
        return jsonify({"error": "No data to export"}), 400
    
    # Create DataFrame
    df = pd.DataFrame({
        'Category': chart_config.get('labels', []),
        'Value': chart_config.get('values', [])
    })
    
    # Add metadata
    df['Generated At'] = dashboard.get('created_at', '')
    df['Chart Type'] = chart_config.get('chart_type', '')
    df['Title'] = chart_config.get('title', '')
    
    # Export to Excel
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Dashboard Data')
    
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"dashboard_{dashboard_id}.xlsx"
    )


@app.route('/api/chart/<chart_id>', methods=['GET'])
def get_chart(chart_id):
    """Get chart image"""
    chart_path = f"{app.config['UPLOAD_FOLDER']}/{chart_id}"
    
    if not os.path.exists(chart_path):
        return jsonify({"error": "Chart not found"}), 404
    
    return send_file(chart_path, mimetype='image/png')


@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """Get dashboard metrics"""
    return jsonify({
        "total_dashboards": len(dashboards_store),
        "total_jira_tasks": len(jira_tasks_store),
        "chart_types": {
            "pie": sum(1 for d in dashboards_store.values() 
                      if d.get('chart_config', {}).get('chart_type') == 'pie'),
            "bar": sum(1 for d in dashboards_store.values() 
                      if d.get('chart_config', {}).get('chart_type') == 'bar'),
            "line": sum(1 for d in dashboards_store.values() 
                      if d.get('chart_config', {}).get('chart_type') == 'line'),
            "metrics": sum(1 for d in dashboards_store.values() 
                         if d.get('chart_config', {}).get('chart_type') == 'metrics')
        }
    })


if __name__ == '__main__':
    print("=" * 60)
    print("Dynamic Dashboard Generation Server")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ Dynamic chart generation (Pie, Bar, Line, Metrics)")
    print("  ✓ Create/Update dashboards via prompt")
    print("  ✓ Jira task assignment integration")
    print("  ✓ Excel/CSV export functionality")
    print("  ✓ LangGraph-powered workflow")
    print("\nStart the server and access at: http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=False, host='0.0.0.0', port=5000)

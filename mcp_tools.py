"""
mcp_tools.py
Jira MCP Tools for LangGraph agent.
Each tool calls Jira REST API v3 using the active auth (OAuth or API key).
The LLM (Qwen) decides which tools to call and with what arguments.
"""

import os
import logging
import requests
from typing import Optional
from requests.auth import HTTPBasicAuth
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ── Auth resolver — injected at runtime from Flask session ────────────────────
# We store a callable so tools always get the freshest token
_auth_resolver = None

def set_auth_resolver(fn):
    """Called by server.py to inject the auth config getter."""
    global _auth_resolver
    _auth_resolver = fn


def _get_cfg():
    """Get current Jira auth config."""
    if _auth_resolver:
        return _auth_resolver()
    return None


def _jira_get(path: str, params: dict = None) -> dict:
    cfg = _get_cfg()
    if not cfg:
        raise ValueError("Jira not authenticated. Please connect via OAuth.")
    url  = f"{cfg['base_url']}/rest/api/3/{path.lstrip('/')}"
    resp = requests.get(url, auth=cfg.get("auth"), headers=cfg["headers"], params=params)
    resp.raise_for_status()
    return resp.json()


def _jira_agile_get(path: str, params: dict = None) -> dict:
    """GET from Jira Agile API (for sprints)."""
    cfg = _get_cfg()
    if not cfg:
        raise ValueError("Jira not authenticated.")
    url  = f"{cfg['base_url']}/rest/agile/1.0/{path.lstrip('/')}"
    resp = requests.get(url, auth=cfg.get("auth"), headers=cfg["headers"], params=params)
    resp.raise_for_status()
    return resp.json()


def _jira_post(path: str, payload: dict) -> dict:
    cfg = _get_cfg()
    if not cfg:
        raise ValueError("Jira not authenticated.")
    url  = f"{cfg['base_url']}/rest/api/3/{path.lstrip('/')}"
    resp = requests.post(url, auth=cfg.get("auth"), headers=cfg["headers"], json=payload)
    resp.raise_for_status()
    return resp.json()


def _jira_put(path: str, payload: dict) -> dict:
    cfg = _get_cfg()
    if not cfg:
        raise ValueError("Jira not authenticated.")
    url  = f"{cfg['base_url']}/rest/api/3/{path.lstrip('/')}"
    resp = requests.put(url, auth=cfg.get("auth"), headers=cfg["headers"], json=payload)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


# ══════════════════════════════════════════════════════════════════════════════
# MCP Tools — each decorated with @tool so LangGraph can use them
# ══════════════════════════════════════════════════════════════════════════════

@tool
def jira_search_issues(jql: str, max_results: int = 50) -> dict:
    """
    Search Jira issues using JQL (Jira Query Language).
    Use this for any query about issues, tasks, bugs, stories.

    Examples of JQL:
    - 'project=SCRUM ORDER BY created DESC'
    - 'project=SCRUM AND status="In Progress"'
    - 'project=SCRUM AND sprint in openSprints()'
    - 'project=SCRUM AND assignee=currentUser()'
    - 'project=SCRUM AND priority=High AND status!="Done"'
    - 'project=SCRUM AND created >= -7d ORDER BY created DESC'

    Args:
        jql: JQL query string
        max_results: max number of issues to return (default 50)

    Returns:
        dict with 'issues' list and 'total' count
    """
    try:
        data   = _jira_get("search/jql", params={
            "jql":        jql,
            "maxResults": max_results,
            "fields":     "summary,status,assignee,priority,created,updated,issuetype,sprint",
        })
        issues = data.get("issues", [])
        result = []
        for i in issues:
            f = i.get("fields", {})
            result.append({
                "key":       i["key"],
                "summary":   f.get("summary", ""),
                "status":    f.get("status", {}).get("name", ""),
                "assignee":  f.get("assignee", {}).get("displayName", "Unassigned") if f.get("assignee") else "Unassigned",
                "priority":  f.get("priority", {}).get("name", "") if f.get("priority") else "",
                "type":      f.get("issuetype", {}).get("name", "") if f.get("issuetype") else "",
                "created":   f.get("created", "")[:10] if f.get("created") else "",
                "updated":   f.get("updated", "")[:10] if f.get("updated") else "",
            })
        return {"issues": result, "total": data.get("total", len(result))}
    except Exception as e:
        logger.error(f"jira_search_issues error: {e}")
        return {"error": str(e), "issues": [], "total": 0}


@tool
def jira_get_sprints(project_key: str) -> dict:
    """
    Get all sprints for a Jira project board.
    Use this when user asks about sprints, sprint status, active sprint, etc.

    Args:
        project_key: Jira project key e.g. 'SCRUM'

    Returns:
        dict with 'sprints' list containing name, state, start/end dates
    """
    try:
        boards_data = _jira_agile_get("board", params={"projectKeyOrId": project_key})
        boards      = boards_data.get("values", [])
        if not boards:
            return {"error": f"No board found for project {project_key}", "sprints": []}

        board_id     = boards[0]["id"]
        sprints_data = _jira_agile_get(f"board/{board_id}/sprint")
        sprints      = sprints_data.get("values", [])

        result = []
        for s in sprints:
            result.append({
                "id":         s.get("id"),
                "name":       s.get("name", ""),
                "state":      s.get("state", ""),
                "start_date": s.get("startDate", "")[:10] if s.get("startDate") else "",
                "end_date":   s.get("endDate", "")[:10]   if s.get("endDate")   else "",
                "goal":       s.get("goal", ""),
            })
        return {"sprints": result, "board_id": board_id}
    except Exception as e:
        logger.error(f"jira_get_sprints error: {e}")
        return {"error": str(e), "sprints": []}


@tool
def jira_get_issue(issue_key: str) -> dict:
    """
    Get full details of a specific Jira issue by its key.
    Use this when user asks about a specific ticket like 'tell me about SCRUM-12'.

    Args:
        issue_key: Issue key e.g. 'SCRUM-12'

    Returns:
        dict with full issue details
    """
    try:
        data = _jira_get(f"issue/{issue_key}")
        f    = data.get("fields", {})
        return {
            "key":         data["key"],
            "summary":     f.get("summary", ""),
            "description": f.get("description", ""),
            "status":      f.get("status", {}).get("name", ""),
            "assignee":    f.get("assignee", {}).get("displayName", "Unassigned") if f.get("assignee") else "Unassigned",
            "reporter":    f.get("reporter", {}).get("displayName", "") if f.get("reporter") else "",
            "priority":    f.get("priority", {}).get("name", "") if f.get("priority") else "",
            "type":        f.get("issuetype", {}).get("name", "") if f.get("issuetype") else "",
            "created":     f.get("created", "")[:10] if f.get("created") else "",
            "updated":     f.get("updated", "")[:10] if f.get("updated") else "",
        }
    except Exception as e:
        logger.error(f"jira_get_issue error: {e}")
        return {"error": str(e)}


@tool
def jira_create_issue(summary: str, description: str = "", issue_type: str = "Task", priority: str = "Medium") -> dict:
    """
    Create a new Jira issue/task.
    Use this when user asks to create a task, ticket, bug, or story.

    Args:
        summary:     Short title of the issue
        description: Detailed description
        issue_type:  Type of issue — Task, Bug, Story (default: Task)
        priority:    Priority — Low, Medium, High, Critical (default: Medium)

    Returns:
        dict with created issue key and URL
    """
    project_key = os.getenv("JIRA_PROJECT_KEY", "SCRUM")
    try:
        payload = {
            "fields": {
                "project":     {"key": project_key},
                "summary":     summary,
                "issuetype":   {"name": issue_type},
                "priority":    {"name": priority},
                "description": {
                    "type":    "doc",
                    "version": 1,
                    "content": [{
                        "type":    "paragraph",
                        "content": [{"type": "text", "text": description or summary}]
                    }]
                },
            }
        }
        result    = _jira_post("issue", payload)
        issue_key = result.get("key", "")
        server    = os.getenv("JIRA_SERVER", "https://atlassian.net").rstrip("/")
        return {
            "key":     issue_key,
            "url":     f"{server}/browse/{issue_key}",
            "summary": summary,
            "status":  "Created successfully",
        }
    except Exception as e:
        logger.error(f"jira_create_issue error: {e}")
        return {"error": str(e)}


@tool
def jira_update_issue(issue_key: str, status: str = None, assignee_account_id: str = None, priority: str = None) -> dict:
    """
    Update an existing Jira issue — change status, assignee, or priority.
    Use this when user asks to update, move, assign, or change a ticket.

    Args:
        issue_key:           Issue key e.g. 'SCRUM-12'
        status:              New status e.g. 'In Progress', 'Done', 'In Review'
        assignee_account_id: Atlassian account ID of new assignee
        priority:            New priority e.g. 'High', 'Low'

    Returns:
        dict with update result
    """
    try:
        updates = {}
        if priority:
            updates["priority"] = {"name": priority}

        if updates:
            _jira_put(f"issue/{issue_key}", {"fields": updates})

        if status:
            trans_data  = _jira_get(f"issue/{issue_key}/transitions")
            transitions = trans_data.get("transitions", [])
            matched     = next((t for t in transitions if t["name"].lower() == status.lower()), None)
            if matched:
                _jira_post(f"issue/{issue_key}/transitions", {"transition": {"id": matched["id"]}})
            else:
                available = [t["name"] for t in transitions]
                return {"error": f"Status '{status}' not found. Available: {available}"}

        if assignee_account_id:
            _jira_put(f"issue/{issue_key}/assignee", {"accountId": assignee_account_id})

        return {"key": issue_key, "status": "Updated successfully"}
    except Exception as e:
        logger.error(f"jira_update_issue error: {e}")
        return {"error": str(e)}


@tool
def jira_get_project_summary(project_key: str) -> dict:
    """
    Get a summary of a Jira project — issue counts by status, assignee workload.
    Use this when user asks for a project overview, summary, or wants chart data.

    Args:
        project_key: Jira project key e.g. 'SCRUM'

    Returns:
        dict with status_counts and assignee_counts — ready for chart generation
    """
    try:
        data   = _jira_get("search/jql", params={
            "jql":        f"project={project_key}",
            "maxResults": 200,
            "fields":     "status,assignee,priority,issuetype",
        })
        issues = data.get("issues", [])

        status_counts   = {}
        assignee_counts = {}
        priority_counts = {}
        type_counts     = {}

        for issue in issues:
            f = issue.get("fields", {})

            status = f.get("status", {}).get("name", "Unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            assignee = f.get("assignee", {}).get("displayName", "Unassigned") if f.get("assignee") else "Unassigned"
            assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1

            priority = f.get("priority", {}).get("name", "None") if f.get("priority") else "None"
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

            itype = f.get("issuetype", {}).get("name", "Unknown") if f.get("issuetype") else "Unknown"
            type_counts[itype] = type_counts.get(itype, 0) + 1

        return {
            "project_key":      project_key,
            "total_issues":     len(issues),
            "status_counts":    status_counts,
            "assignee_counts":  assignee_counts,
            "priority_counts":  priority_counts,
            "type_counts":      type_counts,
        }
    except Exception as e:
        logger.error(f"jira_get_project_summary error: {e}")
        return {"error": str(e)}


@tool
def jira_get_my_issues(project_key: str) -> dict:
    """
    Get issues assigned to the currently logged-in user.
    Use this when user asks 'what are my tasks', 'show my issues', 'what am I working on'.

    Args:
        project_key: Jira project key e.g. 'SCRUM'

    Returns:
        dict with list of issues assigned to current user
    """
    try:
        data   = _jira_get("search/jql", params={
            "jql":        f"project={project_key} AND assignee=currentUser() ORDER BY updated DESC",
            "maxResults": 50,
            "fields":     "summary,status,priority,updated",
        })
        issues = data.get("issues", [])
        result = []
        for i in issues:
            f = i.get("fields", {})
            result.append({
                "key":      i["key"],
                "summary":  f.get("summary", ""),
                "status":   f.get("status", {}).get("name", ""),
                "priority": f.get("priority", {}).get("name", "") if f.get("priority") else "",
                "updated":  f.get("updated", "")[:10] if f.get("updated") else "",
            })
        return {"issues": result, "total": len(result)}
    except Exception as e:
        logger.error(f"jira_get_my_issues error: {e}")
        return {"error": str(e)}


# ── All tools list — passed to LangGraph agent ────────────────────────────────
JIRA_TOOLS = [
    jira_search_issues,
    jira_get_sprints,
    jira_get_issue,
    jira_create_issue,
    jira_update_issue,
    jira_get_project_summary,
    jira_get_my_issues,
]

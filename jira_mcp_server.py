import logging
from typing import Any, Dict, Optional

import requests
from requests.auth import HTTPBasicAuth
from mcp.server.fastmcp import FastMCP


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP("jira-tools")


def _select_sprint_board(boards: list[Dict[str, Any]], project_key: str) -> Optional[Dict[str, Any]]:
    """Prefer Scrum boards for sprint queries and fall back to matching project boards."""
    if not boards:
        return None

    scrum_boards = [board for board in boards if (board.get("type") or "").lower() == "scrum"]
    if len(scrum_boards) == 1:
        return scrum_boards[0]

    if scrum_boards:
        for board in scrum_boards:
            location = board.get("location") or {}
            if (location.get("projectKey") or "").upper() == project_key.upper():
                return board
        return scrum_boards[0]

    for board in boards:
        location = board.get("location") or {}
        if (location.get("projectKey") or "").upper() == project_key.upper():
            return board

    return boards[0]


def _build_auth(auth_context: Dict[str, Any]) -> Dict[str, Any]:
    auth_type = auth_context.get("auth_type")

    if auth_type == "oauth":
        cloud_id = auth_context.get("cloud_id", "")
        access_token = auth_context.get("access_token", "")
        if not cloud_id or not access_token:
            raise ValueError("Missing OAuth auth_context fields")
        return {
            "base_url": f"https://api.atlassian.com/ex/jira/{cloud_id}",
            "auth": None,
            "headers": {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        }

    if auth_type == "apikey":
        server = (auth_context.get("server") or "").rstrip("/")
        email = auth_context.get("email")
        api_token = auth_context.get("api_token")
        if not server or not email or not api_token:
            raise ValueError("Missing API key auth_context fields")
        return {
            "base_url": server,
            "auth": HTTPBasicAuth(email, api_token),
            "headers": {
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        }

    raise ValueError("Unsupported auth_type in auth_context")


def _jira_get(auth_context: Dict[str, Any], path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = _build_auth(auth_context)
    url = f"{cfg['base_url']}/rest/api/3/{path.lstrip('/')}"
    resp = requests.get(url, auth=cfg.get("auth"), headers=cfg["headers"], params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _jira_agile_get(auth_context: Dict[str, Any], path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = _build_auth(auth_context)
    url = f"{cfg['base_url']}/rest/agile/1.0/{path.lstrip('/')}"
    resp = requests.get(url, auth=cfg.get("auth"), headers=cfg["headers"], params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _jira_post(auth_context: Dict[str, Any], path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _build_auth(auth_context)
    url = f"{cfg['base_url']}/rest/api/3/{path.lstrip('/')}"
    resp = requests.post(url, auth=cfg.get("auth"), headers=cfg["headers"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _jira_put(auth_context: Dict[str, Any], path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _build_auth(auth_context)
    url = f"{cfg['base_url']}/rest/api/3/{path.lstrip('/')}"
    resp = requests.put(url, auth=cfg.get("auth"), headers=cfg["headers"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json() if resp.content else {}


@mcp.tool()
def jira_search_issues(auth_context: Dict[str, Any], jql: str, max_results: int = 50) -> Dict[str, Any]:
    try:
        data = _jira_get(
            auth_context,
            "search/jql",
            params={
                "jql": jql,
                "maxResults": max_results,
                "fields": "summary,status,assignee,priority,created,updated,issuetype,sprint",
            },
        )
        issues = data.get("issues", [])
        result = []
        for item in issues:
            fields = item.get("fields", {})
            result.append(
                {
                    "key": item.get("key", ""),
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", ""),
                    "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
                    "priority": fields.get("priority", {}).get("name", "") if fields.get("priority") else "",
                    "type": fields.get("issuetype", {}).get("name", "") if fields.get("issuetype") else "",
                    "created": fields.get("created", "")[:10] if fields.get("created") else "",
                    "updated": fields.get("updated", "")[:10] if fields.get("updated") else "",
                }
            )
        return {"issues": result, "total": data.get("total", len(result))}
    except Exception as exc:
        logger.error("jira_search_issues error: %s", exc)
        return {"error": str(exc), "issues": [], "total": 0}


@mcp.tool()
def jira_get_sprints(auth_context: Dict[str, Any], project_key: str) -> Dict[str, Any]:
    try:
        boards_data = _jira_agile_get(auth_context, "board", params={"projectKeyOrId": project_key})
        boards = boards_data.get("values", [])
        if not boards:
            return {"error": f"No board found for project {project_key}", "sprints": []}

        board = _select_sprint_board(boards, project_key)
        if not board:
            return {"error": f"No sprint-capable board found for project {project_key}", "sprints": []}

        board_type = (board.get("type") or "").lower()
        if board_type and board_type != "scrum":
            board_name = board.get("name", "Unknown board")
            return {
                "error": f"Board '{board_name}' for project {project_key} is a {board_type} board and does not expose sprints.",
                "sprints": [],
                "board_id": board.get("id"),
            }

        board_id = board.get("id")
        logger.info("jira_get_sprints selected board id=%s name=%s type=%s", board_id, board.get("name", ""), board.get("type", ""))
        sprints_data = _jira_agile_get(auth_context, f"board/{board_id}/sprint")
        sprints = sprints_data.get("values", [])

        result = []
        for sprint in sprints:
            result.append(
                {
                    "id": sprint.get("id"),
                    "name": sprint.get("name", ""),
                    "state": sprint.get("state", ""),
                    "start_date": sprint.get("startDate", "")[:10] if sprint.get("startDate") else "",
                    "end_date": sprint.get("endDate", "")[:10] if sprint.get("endDate") else "",
                    "goal": sprint.get("goal", ""),
                }
            )
        return {"sprints": result, "board_id": board_id}
    except Exception as exc:
        logger.error("jira_get_sprints error: %s", exc)
        return {"error": str(exc), "sprints": []}


@mcp.tool()
def jira_get_issue(auth_context: Dict[str, Any], issue_key: str) -> Dict[str, Any]:
    try:
        data = _jira_get(auth_context, f"issue/{issue_key}")
        fields = data.get("fields", {})
        return {
            "key": data.get("key", issue_key),
            "summary": fields.get("summary", ""),
            "description": fields.get("description", ""),
            "status": fields.get("status", {}).get("name", ""),
            "assignee": fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned",
            "reporter": fields.get("reporter", {}).get("displayName", "") if fields.get("reporter") else "",
            "priority": fields.get("priority", {}).get("name", "") if fields.get("priority") else "",
            "type": fields.get("issuetype", {}).get("name", "") if fields.get("issuetype") else "",
            "created": fields.get("created", "")[:10] if fields.get("created") else "",
            "updated": fields.get("updated", "")[:10] if fields.get("updated") else "",
        }
    except Exception as exc:
        logger.error("jira_get_issue error: %s", exc)
        return {"error": str(exc)}


@mcp.tool()
def jira_create_issue(
    auth_context: Dict[str, Any],
    project_key: str,
    summary: str,
    description: str = "",
    issue_type: str = "Task",
    priority: str = "Medium",
) -> Dict[str, Any]:
    try:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": description or summary}],
                        }
                    ],
                },
            }
        }
        result = _jira_post(auth_context, "issue", payload)
        issue_key = result.get("key", "")

        site = auth_context.get("site", "")
        server = f"https://{site}.atlassian.net" if site else "https://atlassian.net"
        return {
            "key": issue_key,
            "url": f"{server}/browse/{issue_key}",
            "summary": summary,
            "status": "Created successfully",
        }
    except Exception as exc:
        logger.error("jira_create_issue error: %s", exc)
        return {"error": str(exc)}


@mcp.tool()
def jira_update_issue(
    auth_context: Dict[str, Any],
    issue_key: str,
    status: Optional[str] = None,
    assignee_account_id: Optional[str] = None,
    priority: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        updates: Dict[str, Any] = {}
        if priority:
            updates["priority"] = {"name": priority}

        if updates:
            _jira_put(auth_context, f"issue/{issue_key}", {"fields": updates})

        if status:
            transitions_data = _jira_get(auth_context, f"issue/{issue_key}/transitions")
            transitions = transitions_data.get("transitions", [])
            matched = next((t for t in transitions if t.get("name", "").lower() == status.lower()), None)
            if matched:
                _jira_post(auth_context, f"issue/{issue_key}/transitions", {"transition": {"id": matched["id"]}})
            else:
                available = [t.get("name", "") for t in transitions]
                return {"error": f"Status '{status}' not found. Available: {available}"}

        if assignee_account_id:
            _jira_put(auth_context, f"issue/{issue_key}/assignee", {"accountId": assignee_account_id})

        return {"key": issue_key, "status": "Updated successfully"}
    except Exception as exc:
        logger.error("jira_update_issue error: %s", exc)
        return {"error": str(exc)}


@mcp.tool()
def jira_get_project_summary(auth_context: Dict[str, Any], project_key: str) -> Dict[str, Any]:
    try:
        data = _jira_get(
            auth_context,
            "search/jql",
            params={
                "jql": f"project={project_key}",
                "maxResults": 200,
                "fields": "status,assignee,priority,issuetype",
            },
        )
        issues = data.get("issues", [])

        status_counts: Dict[str, int] = {}
        assignee_counts: Dict[str, int] = {}
        priority_counts: Dict[str, int] = {}
        type_counts: Dict[str, int] = {}

        for issue in issues:
            fields = issue.get("fields", {})

            status_name = fields.get("status", {}).get("name", "Unknown")
            status_counts[status_name] = status_counts.get(status_name, 0) + 1

            assignee_name = fields.get("assignee", {}).get("displayName", "Unassigned") if fields.get("assignee") else "Unassigned"
            assignee_counts[assignee_name] = assignee_counts.get(assignee_name, 0) + 1

            priority_name = fields.get("priority", {}).get("name", "None") if fields.get("priority") else "None"
            priority_counts[priority_name] = priority_counts.get(priority_name, 0) + 1

            issue_type_name = fields.get("issuetype", {}).get("name", "Unknown") if fields.get("issuetype") else "Unknown"
            type_counts[issue_type_name] = type_counts.get(issue_type_name, 0) + 1

        return {
            "project_key": project_key,
            "total_issues": len(issues),
            "status_counts": status_counts,
            "assignee_counts": assignee_counts,
            "priority_counts": priority_counts,
            "type_counts": type_counts,
        }
    except Exception as exc:
        logger.error("jira_get_project_summary error: %s", exc)
        return {"error": str(exc)}


@mcp.tool()
def jira_get_my_issues(auth_context: Dict[str, Any], project_key: str) -> Dict[str, Any]:
    try:
        data = _jira_get(
            auth_context,
            "search/jql",
            params={
                "jql": f"project={project_key} AND assignee=currentUser() ORDER BY updated DESC",
                "maxResults": 50,
                "fields": "summary,status,priority,updated",
            },
        )
        issues = data.get("issues", [])
        result = []
        for item in issues:
            fields = item.get("fields", {})
            result.append(
                {
                    "key": item.get("key", ""),
                    "summary": fields.get("summary", ""),
                    "status": fields.get("status", {}).get("name", ""),
                    "priority": fields.get("priority", {}).get("name", "") if fields.get("priority") else "",
                    "updated": fields.get("updated", "")[:10] if fields.get("updated") else "",
                }
            )
        return {"issues": result, "total": len(result)}
    except Exception as exc:
        logger.error("jira_get_my_issues error: %s", exc)
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
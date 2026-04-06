import os
import sys
from typing import Any, Dict, List, Optional

import anyio
try:
    from mcp import ClientSession, StdioServerParameters, stdio_client
except ModuleNotFoundError as exc:
    if exc.name == "mcp":
        raise ModuleNotFoundError(
            "The 'mcp' package is not installed in the current Python interpreter. "
            f"Current interpreter: {sys.executable}. "
            "Run the app with /Users/nikhilbalaji/Hackathon/JIRA-Dashboard/venv311/bin/python "
            "or install dependencies into the interpreter you are using with 'pip install -r requirements.txt'."
        ) from exc
    raise


class MCPClientError(Exception):
    pass


class MCPStdioClient:
    def __init__(self, server_script_path: str, python_executable: Optional[str] = None):
        self.server_script_path = server_script_path
        self.python_executable = python_executable or os.getenv("PYTHON") or sys.executable
        self.cwd = os.path.dirname(os.path.abspath(server_script_path))

    def _server_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=self.python_executable,
            args=[self.server_script_path],
            cwd=self.cwd,
        )

    async def _list_tools_async(self) -> List[Dict[str, Any]]:
        server_params = self._server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                result = await session.initialize()
                tools = await session.list_tools()
                if not result:
                    raise MCPClientError("MCP initialize returned no result")
                return [tool.model_dump(mode="json", by_alias=True) for tool in tools.tools]

    async def _call_tool_async(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        server_params = self._server_params()
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name=name, arguments=arguments or {})

                if result.isError:
                    raise MCPClientError(result.model_dump_json(by_alias=True))

                if isinstance(result.structuredContent, dict):
                    return result.structuredContent

                if result.content:
                    first = result.content[0]
                    text = getattr(first, "text", None)
                    if text:
                        return {"raw_response": text}

                return {"raw_response": result.model_dump_json(by_alias=True)}

    def list_tools(self) -> List[Dict[str, Any]]:
        try:
            return anyio.run(self._list_tools_async)
        except Exception as exc:
            raise MCPClientError(str(exc)) from exc

    def call_tool(self, name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            return anyio.run(self._call_tool_async, name, arguments)
        except Exception as exc:
            raise MCPClientError(str(exc)) from exc

    def close(self) -> None:
        return None


_client_singleton: Optional[MCPStdioClient] = None


def get_mcp_client() -> MCPStdioClient:
    global _client_singleton
    if _client_singleton is None:
        here = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(here, "jira_mcp_server.py")
        _client_singleton = MCPStdioClient(server_script_path=server_script)
    return _client_singleton


def list_jira_tools() -> List[Dict[str, Any]]:
    return get_mcp_client().list_tools()


def call_jira_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return get_mcp_client().call_tool(tool_name, args)
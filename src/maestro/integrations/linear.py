"""
Linear integration for Maestro — read tasks from Linear as a task source.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class LinearClient:
    """Read tasks from Linear as a task source."""

    def __init__(
        self,
        api_key: str | None = None,
        project_slug: str | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("LINEAR_API_KEY")
        self._project_slug = project_slug
        self._endpoint = "https://api.linear.app/graphql"

    @property
    def available(self) -> bool:
        """Return True if both API key and project slug are configured."""
        return self._api_key is not None and self._project_slug is not None

    async def _execute_graphql(
        self, query: str, variables: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Execute a GraphQL query against Linear's API."""
        headers = {
            "Authorization": self._api_key or "",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self._endpoint, json=payload, headers=headers
            ) as resp:
                if resp.status != 200:
                    logger.warning("Linear API returned status %d", resp.status)
                    return {}
                return await resp.json()

    async def fetch_issues(
        self, states: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Fetch issues from Linear project.

        Args:
            states: Optional list of state names to filter by (e.g. ["Todo", "In Progress"]).

        Returns:
            List of issue dicts with keys: id, identifier, title, description, state, priority.
        """
        if not self.available:
            return []

        state_filter = ""
        if states:
            state_list = ", ".join(f'"{s}"' for s in states)
            state_filter = f', filter: {{state: {{name: {{in: [{state_list}]}}}}}}'

        query = f"""
        query($slug: String!) {{
            project(slugId: $slug) {{
                issues{state_filter} {{
                    nodes {{
                        id
                        identifier
                        title
                        description
                        state {{ name }}
                        priority
                    }}
                }}
            }}
        }}
        """
        variables = {"slug": self._project_slug}

        try:
            data = await self._execute_graphql(query, variables)
        except Exception:
            logger.exception("Failed to fetch Linear issues")
            return []

        project = data.get("data", {}).get("project")
        if not project:
            return []
        nodes = project.get("issues", {}).get("nodes", [])
        return [
            {
                "id": n["id"],
                "identifier": n.get("identifier", ""),
                "title": n.get("title", ""),
                "description": n.get("description"),
                "state": n.get("state", {}).get("name", ""),
                "priority": n.get("priority", 0),
            }
            for n in nodes
        ]

    async def update_issue_state(
        self, issue_id: str, state_name: str
    ) -> bool:
        """Update an issue's state in Linear.

        Args:
            issue_id: The Linear issue ID.
            state_name: The target state name (e.g. "Done", "In Progress").

        Returns:
            True if the mutation succeeded.
        """
        if not self.available:
            return False

        # First, find the state ID by name via a team states query.
        # For simplicity, we use issueUpdate with stateId lookup in one go.
        query = """
        mutation($issueId: String!, $stateName: String!) {
            issueUpdate(id: $issueId, input: {stateId: $stateName}) {
                success
            }
        }
        """
        variables = {"issueId": issue_id, "stateName": state_name}

        try:
            data = await self._execute_graphql(query, variables)
        except Exception:
            logger.exception("Failed to update Linear issue state")
            return False

        return bool(
            data.get("data", {}).get("issueUpdate", {}).get("success")
        )

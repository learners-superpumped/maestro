"""
Resource Manager for Maestro.

Manages shared resources (e.g. Chrome profiles) to prevent concurrent access
by multiple agents. Resources are identified by a composite key of
``resource_type/profile_name`` (e.g. ``chrome-profiles/threads``).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from maestro.config import MaestroConfig


class ResourceManager:
    """Manages shared resource locks for Maestro agents.

    Resources are declared in ``maestro.yaml`` under the ``resources`` section
    and referenced by workspace MCP configurations.  The manager provides
    async lock/unlock semantics so the Dispatcher can skip tasks whose
    required resources are already in use.
    """

    def __init__(
        self, config: MaestroConfig, workspaces_dir: Path | None = None
    ) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._acquired: dict[str, bool] = {}
        self._resources = config.resources  # dict[type, dict[profile, ResourceProfile]]
        self._workspaces_dir = workspaces_dir

        # Pre-create locks for all declared resources
        for resource_type, profiles in self._resources.items():
            for profile_name in profiles:
                key = f"{resource_type}/{profile_name}"
                self._locks[key] = asyncio.Lock()
                self._acquired[key] = False

    def _ensure_lock(self, resource_name: str) -> asyncio.Lock:
        """Get or create a lock for the given resource name."""
        if resource_name not in self._locks:
            self._locks[resource_name] = asyncio.Lock()
            self._acquired[resource_name] = False
        return self._locks[resource_name]

    def get_workspace_resources(self, workspace: str) -> list[str]:
        """Get resource names needed by a workspace.

        Inspects the workspace's ``.claude/mcp.json`` for ``chrome-browser``
        configuration and maps it to declared resource pools.

        Args:
            workspace: Workspace name.

        Returns:
            List of resource keys (e.g. ``["chrome-profiles/threads"]``).
        """
        if self._workspaces_dir is None:
            return []

        mcp_path = self._workspaces_dir / workspace / ".claude" / "mcp.json"
        if not mcp_path.exists():
            return []

        try:
            mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

        resources: list[str] = []
        servers = mcp_data.get("mcpServers", {})

        # Chrome browser server implies a chrome-profiles resource.
        # Map workspace name to resource profile name if it exists.
        if "chrome-browser" in servers:
            for profile_name in self._resources.get("chrome-profiles", {}):
                if profile_name in workspace:
                    resources.append(f"chrome-profiles/{profile_name}")

        return resources

    async def acquire(self, resource_name: str) -> bool:
        """Try to acquire a resource lock.

        This is non-blocking: returns ``True`` if the lock was acquired,
        ``False`` if it is already held.
        """
        lock = self._ensure_lock(resource_name)
        acquired = lock.locked()
        if acquired:
            return False
        await lock.acquire()
        self._acquired[resource_name] = True
        return True

    async def release(self, resource_name: str) -> None:
        """Release a resource lock.

        No-op if the resource is not currently acquired.
        """
        if resource_name not in self._locks:
            return
        lock = self._locks[resource_name]
        if lock.locked() and self._acquired.get(resource_name, False):
            lock.release()
            self._acquired[resource_name] = False

    def is_available(self, resource_name: str) -> bool:
        """Check if a resource is available without acquiring it."""
        if resource_name not in self._locks:
            # Unknown resource is considered available
            return True
        return not self._locks[resource_name].locked()

    def all_available(self, resource_names: list[str]) -> bool:
        """Check if all given resources are available."""
        return all(self.is_available(r) for r in resource_names)

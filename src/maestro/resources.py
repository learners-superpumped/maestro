"""
Resource Manager for Maestro.

Manages shared resources (e.g. Chrome profiles) to prevent concurrent access
by multiple agents. Resources are identified by a composite key of
``resource_type/profile_name`` (e.g. ``chrome-profiles/threads``).
"""

from __future__ import annotations

import asyncio

from maestro.config import MaestroConfig


class ResourceManager:
    """Manages shared resource locks for Maestro agents.

    Resources are declared in ``maestro.yaml`` under the ``resources`` section
    and referenced by agent MCP configurations.  The manager provides
    async lock/unlock semantics so the Dispatcher can skip tasks whose
    required resources are already in use.
    """

    def __init__(self, config: MaestroConfig) -> None:
        self._locks: dict[str, asyncio.Lock] = {}
        self._acquired: dict[str, bool] = {}
        self._resources = config.resources  # dict[type, dict[profile, ResourceProfile]]

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

    def get_agent_resources(self, agent: str) -> list[str]:
        """Get resource names needed by an agent.

        Resources will be redesigned in a future update.
        Returns an empty list for now.

        Args:
            agent: Agent name (unused).

        Returns:
            Empty list.
        """
        return []

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

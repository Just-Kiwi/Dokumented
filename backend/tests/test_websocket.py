"""
Tests for WebSocket ConnectionManager - unit tests for ConnectionManager class.
"""
import pytest
from main import ConnectionManager


class TestConnectionManager:
    """Tests for WebSocket ConnectionManager."""

    def test_manager_starts_empty(self):
        """Test manager starts with no connections."""
        manager = ConnectionManager()
        assert manager.active_connections == []


class TestConnectionManagerBroadcast:
    """Tests for WebSocket broadcast functionality."""

    @pytest.mark.asyncio
    async def test_broadcast_empty_connections(self):
        """Test broadcast with no connections doesn't fail."""
        manager = ConnectionManager()
        test_message = {"event": "test", "data": {}}
        await manager.broadcast(test_message)

    @pytest.mark.asyncio
    async def test_broadcast_handles_empty_list(self):
        """Test broadcast handles empty connections gracefully."""
        manager = ConnectionManager()
        await manager.broadcast({"event": "test"})

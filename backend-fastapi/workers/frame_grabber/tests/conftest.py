"""Shared fixtures for frame grabber tests."""
import asyncio
from unittest.mock import AsyncMock

import numpy as np
import pytest


@pytest.fixture
def static_frame():
    """A 640x480 gray frame (no motion)."""
    return np.full((480, 640, 3), 128, dtype=np.uint8)


@pytest.fixture
def motion_frame():
    """A 640x480 frame with a white rectangle (simulates motion)."""
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    frame[100:300, 100:400] = 255
    return frame


@pytest.fixture
def black_frame():
    return np.zeros((480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_redis():
    """Async Redis mock with in-memory storage."""
    store = {}

    r = AsyncMock()

    async def setex(key, ttl, value):
        store[key] = value

    async def get(key):
        return store.get(key)

    async def delete(key):
        store.pop(key, None)

    async def set_fn(key, value, nx=False, ex=None):
        if nx and key in store:
            return False
        store[key] = value
        return True

    async def exists(key):
        return key in store

    async def expire(key, ttl):
        pass  # No-op for tests

    def pipeline():
        """Simple pipeline mock that batches commands."""
        cmds = []

        class Pipeline:
            def setex(self, key, ttl, value):
                cmds.append(('setex', key, ttl, value))
                return self

            def delete(self, key):
                cmds.append(('delete', key))
                return self

            def get(self, key):
                cmds.append(('get', key))
                return self

            def expire(self, key, ttl):
                cmds.append(('expire', key, ttl))
                return self

            async def execute(self):
                results = []
                for cmd in cmds:
                    if cmd[0] == 'setex':
                        store[cmd[1]] = cmd[3]
                        results.append(True)
                    elif cmd[0] == 'delete':
                        store.pop(cmd[1], None)
                        results.append(True)
                    elif cmd[0] == 'get':
                        results.append(store.get(cmd[1]))
                    elif cmd[0] == 'expire':
                        results.append(True)
                cmds.clear()
                return results

        return Pipeline()

    r.setex = setex
    r.get = get
    r.delete = delete
    r.set = set_fn
    r.exists = exists
    r.expire = expire
    r.pipeline = pipeline
    r._store = store
    return r

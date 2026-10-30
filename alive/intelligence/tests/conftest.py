"""Fail every isolated test immediately on an attempted external network connection."""

import socket

import pytest_asyncio


@pytest_asyncio.fixture(autouse=True)
async def no_network(monkeypatch):
    # Initialize pytest's loop first: Windows implements its self-pipe with socketpair.
    def forbidden(*args, **kwargs):
        raise AssertionError("External network is not authorized in intelligence tests")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

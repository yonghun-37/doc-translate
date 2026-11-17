import socket
import asyncio
import pytest


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError('테스트에서 네트워크를 사용할 수 없습니다')
    monkeypatch.setattr(socket.socket, 'connect', denied)
    monkeypatch.setattr(socket.socket, 'connect_ex', denied)


def client_loop():
    """Keep TestClient responsive where the sandbox denies self-pipe sends.

    No I/O or application behavior is mocked: a timer lets the selector notice
    queued cross-thread callbacks even when socketpair.send raises EPERM.
    """
    loop = asyncio.new_event_loop()
    def tick():
        loop.call_later(0.01, tick)
    loop.call_soon(tick)
    return loop

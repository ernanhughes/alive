"""Real local sockets: model HTTP clients must ignore ambient routing and CA settings."""

import asyncio
import json
import socket
import socketserver
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from alive.providers import MetaProvider, ProviderError


@pytest.mark.parametrize(
    "variable", ["HTTPS_PROXY", "ALL_PROXY", "HTTP_PROXY", "https_proxy", "all_proxy"]
)
def test_environment_proxy_cannot_intercept_model_request(settings, monkeypatch, variable):
    received = []

    class Proxy(socketserver.BaseRequestHandler):
        def handle(self):
            received.append(self.request.recv(8192))
            self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")

    for name in (
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "ALL_PROXY",
        "NO_PROXY",
        "https_proxy",
        "http_proxy",
        "all_proxy",
        "no_proxy",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    ):
        monkeypatch.delenv(name, raising=False)
    # Reserve a local port without listening: the direct endpoint fails locally, without DNS,
    # internet access, credentials, or inference. The proxy records any ambient rerouting.
    with (
        socket.socket() as endpoint,
        socketserver.ThreadingTCPServer(("127.0.0.1", 0), Proxy) as proxy,
    ):
        endpoint.bind(("127.0.0.1", 0))
        settings.alive_meta_url = f"https://127.0.0.1:{endpoint.getsockname()[1]}/completions"
        settings.alive_meta_api_key = "synthetic-only"
        settings.alive_meta_timeout = 2
        monkeypatch.setenv(variable, f"http://127.0.0.1:{proxy.server_address[1]}")
        worker = threading.Thread(target=proxy.serve_forever, daemon=True)
        worker.start()
        try:

            async def attempt():
                with pytest.raises(ProviderError):
                    await MetaProvider(settings).structured("Synthetic", {"source": "CANARY"}, {})

            asyncio.run(attempt())
        finally:
            proxy.shutdown()
            worker.join()
    assert received == [], "ambient proxy intercepted the approved endpoint's CONNECT"


@pytest.mark.parametrize("variable", ["SSL_CERT_FILE", "SSL_CERT_DIR"])
def test_environment_ca_settings_cannot_change_model_tls(settings, monkeypatch, tmp_path, variable):
    monkeypatch.setenv(variable, str(tmp_path / "nonexistent-certificates"))
    settings.alive_meta_api_key = "synthetic-only"
    with socket.socket() as endpoint:
        endpoint.bind(("127.0.0.1", 0))
        settings.alive_meta_url = f"https://127.0.0.1:{endpoint.getsockname()[1]}/completions"
        settings.alive_meta_timeout = 2

        async def attempt():
            with pytest.raises(ProviderError) as caught:
                await MetaProvider(settings).structured("Synthetic", {}, {})
            assert caught.value.category in {"transient_network", "timeout"}

        asyncio.run(attempt())


def test_tls_verification_stays_enabled_and_explicit_test_transport_is_preserved(
    settings, monkeypatch
):
    fixtures = Path(__file__).parent / "fixtures" / "model-tls"
    received = []

    class Provider(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(self.rfile.read(int(self.headers["Content-Length"])))
            response = json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        def log_message(self, *args):
            pass

    server_tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_tls.load_cert_chain(fixtures / "synthetic-cert.pem", fixtures / "synthetic-key.pem")
    # Attempt to turn the fixture's untrusted CA into ambient trust. Production must ignore it.
    monkeypatch.setenv("SSL_CERT_FILE", str(fixtures / "synthetic-cert.pem"))
    with ThreadingHTTPServer(("127.0.0.1", 0), Provider) as server:
        server.socket = server_tls.wrap_socket(server.socket, server_side=True)
        settings.alive_meta_url = f"https://127.0.0.1:{server.server_port}/completions"
        settings.alive_meta_api_key = "synthetic-only"
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:

            async def attempt():
                with pytest.raises(ProviderError, match="transient_network"):
                    await MetaProvider(settings).structured("Synthetic", {}, {})
                assert received == [], "untrusted certificate must fail before sending source"
                test_tls = ssl.create_default_context(cafile=str(fixtures / "synthetic-cert.pem"))
                transport = httpx.AsyncHTTPTransport(verify=test_tls, trust_env=False)
                response = await MetaProvider(settings).structured(
                    "Synthetic",
                    {"source": "SYNTHETIC_TLS_CANARY"},
                    {},
                    transport=transport,
                )
                assert response.text == "{}"

            asyncio.run(attempt())
        finally:
            server.shutdown()
            worker.join()
    assert len(received) == 1
    assert b"SYNTHETIC_TLS_CANARY" in received[0]

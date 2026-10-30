#!/usr/bin/env python3
"""
0700-AAM Sovereign Web GUI Server & Hardware Bridge
==================================================
Serves the skeuomorphic webpage simulator over HTTP and provides
a real-time WebSocket bridge to the C++ 0700-aam-sim ComProtocol engine.
"""

import sys
import os
import argparse
import asyncio
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = REPO_ROOT / "web"

try:
    from aiohttp import web, WSMsgType
except ImportError:
    print("[Error] aiohttp is required to run the web simulator bridge.")
    print("Install via: pip install aiohttp")
    sys.exit(1)

# Connected WebSocket clients
ws_clients = set()

# ComProtocol magic & constants
MAGIC_0 = 0x4D # 'M'
MAGIC_1 = 0x54 # 'T'

def calculate_crc8(data: bytes) -> int:
    crc = 0xFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc

async def index_handler(request):
    return web.FileResponse(WEB_DIR / "index.html")

async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_clients.add(ws)
    print(f"[WebSocket] Client connected: {request.remote}")

    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                data = msg.data
                if len(data) >= 7 and data[0] == MAGIC_0 and data[1] == MAGIC_1:
                    cmd = data[4]
                    length = data[5]
                    payload = data[6:6+length]
                    # Log packet
                    # print(f"[ComProtocol IN] Cmd=0x{cmd:02X}, Len={length}, Payload={payload.hex()}")

                    # Broadcast packet to all other clients (or C++ backend)
                    for client in list(ws_clients):
                        if client != ws and not client.closed:
                            await client.send_bytes(data)
            elif msg.type == WSMsgType.ERROR:
                print(f"[WebSocket] Error: {ws.exception()}")
    finally:
        ws_clients.remove(ws)
        print(f"[WebSocket] Client disconnected: {request.remote}")

    return ws

def create_app():
    app = web.Application()
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", websocket_handler)
    # Serve static assets (css, js, icons)
    app.router.add_static("/", path=WEB_DIR, name="static")
    return app

def main():
    parser = argparse.ArgumentParser(description="0700-AAM Sovereign Web GUI Server")
    parser.add_argument("--port", type=int, default=8080, help="HTTP/WebSocket port (default: 8080)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host bind address (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    app = create_app()

    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print("  0700-AAM Sovereign Web Simulator & Hardware Harness")
    print(f"  Web GUI running at: {url}")
    print(f"  WebSocket endpoint: ws://{args.host}:{args.port}/ws")
    print("=" * 65)

    if not args.no_browser:
        asyncio.get_event_loop().call_later(0.8, lambda: webbrowser.open(url))

    web.run_app(app, host=args.host, port=args.port, print=None)

if __name__ == "__main__":
    main()

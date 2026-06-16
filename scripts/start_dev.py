#!/usr/bin/env python
"""Start server + cloudflare tunnel, sync APP_BASE_URL, verify health."""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

ROOT = Path(__file__).parent.parent
ENV_FILE = ROOT / ".env.local"
PORT = 8888


def _kill_port(port: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            [
                "powershell",
                "-Command",
                f"Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | "
                f"ForEach-Object {{ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }}",
            ],
            capture_output=True,
        )
    else:
        subprocess.run(["fuser", "-k", f"{port}/tcp"], capture_output=True)


def _update_env_url(url: str) -> None:
    text = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    line = f"APP_BASE_URL={url}"
    if "APP_BASE_URL=" in text:
        text = re.sub(r"APP_BASE_URL=.*", line, text)
    else:
        text += f"\n{line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    print(f"Updated .env.local → {url}")


def _wait_for_tunnel(log_path: Path, timeout: int = 45) -> str:
    pattern = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
    for _ in range(timeout):
        if log_path.exists():
            match = pattern.search(log_path.read_text(encoding="utf-8", errors="ignore"))
            if match:
                return match.group(0)
        time.sleep(1)
    raise RuntimeError("Timed out waiting for cloudflare tunnel URL")


def main() -> None:
    print("=== SlotBot Dev Startup ===\n")

    _kill_port(PORT)

    server_log = ROOT / ".dev_server.log"
    tunnel_log = ROOT / ".dev_tunnel.log"

    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "services.api.app:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=ROOT,
        stdout=open(server_log, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
    )
    print(f"Server starting on :{PORT} (pid {server.pid})...")

    tunnel_cmd = f"npx --yes cloudflared tunnel --url http://127.0.0.1:{PORT}"
    tunnel = subprocess.Popen(
        tunnel_cmd,
        cwd=ROOT,
        stdout=open(tunnel_log, "w", encoding="utf-8"),
        stderr=subprocess.STDOUT,
        shell=True,
    )
    print(f"Tunnel starting (pid {tunnel.pid})...")

    try:
        url = _wait_for_tunnel(tunnel_log)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        server.kill()
        tunnel.kill()
        sys.exit(1)

    _update_env_url(url)

    # Wait for server ready
    for _ in range(30):
        try:
            httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2.0)
            break
        except Exception:
            time.sleep(1)
    else:
        print("ERROR: Server did not become ready")
        sys.exit(1)

    # Verify tunnel end-to-end
    try:
        r = httpx.get(f"{url}/health", timeout=15.0)
        r.raise_for_status()
    except Exception as exc:
        print(f"ERROR: Tunnel health check failed: {exc}")
        sys.exit(1)

    print(f"\nReady!")
    print(f"  Tunnel:  {url}")
    print(f"  Health:  {url}/health")
    print(f"  Turn:    {url}/voice/turn")
    print()
    print("Place a call:")
    print(f"  python scripts/outbound_call.py 918275566293 --base-url {url}")
    print()
    print("Press Ctrl+C to stop (server + tunnel keep running in background).")
    print(f"Logs: {server_log.name}, {tunnel_log.name}")

    try:
        while True:
            time.sleep(60)
            if server.poll() is not None:
                print("WARNING: Server process exited!")
                break
            if tunnel.poll() is not None:
                print("WARNING: Tunnel process exited!")
                break
    except KeyboardInterrupt:
        print("\nStopping...")
        server.kill()
        tunnel.kill()


if __name__ == "__main__":
    main()

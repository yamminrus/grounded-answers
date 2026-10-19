"""Prove this is really an MCP server, using a client we did not write.

Starts server.py on Streamable HTTP, connects with the official MCP SDK
client, and asserts behaviour over the wire. Nothing here reaches into the
server's own modules, so a result cannot come from calling our own functions
in a loop and declaring victory.

It also plants a question the server MUST refuse. A server that can only
answer has not been shown to refuse, and refusing is the product.

    python prove_mcp.py
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import time
from pathlib import Path

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client

HERE = Path(__file__).parent
PORT = 8077
URL = f"http://127.0.0.1:{PORT}/mcp"

MUST_ANSWER = "when does the boiler warranty expire"
MUST_REFUSE = "what is the wifi password"

# A protocol revision looks like 2025-11-25 and nothing else counts.
REVISION = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def text_of(result) -> str:
    """Pull the text payload out of a CallToolResult across shapes."""
    if getattr(result, "structuredContent", None):
        return json.dumps(result.structuredContent)
    parts = []
    for c in getattr(result, "content", []) or []:
        parts.append(getattr(c, "text", "") or "")
    return "\n".join(parts)


async def run() -> int:
    failures = 0

    def check(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        failures += not ok
        print(f"  {'ok ' if ok else '!! '}{label}")
        if not ok and detail:
            print(f"      {detail}")

    async with streamable_http_client(URL) as streams:
        read, write = streams[0], streams[1]
        async with ClientSession(read, write) as session:
            init = await session.initialize()

            # Read the real field. An earlier version of this script used the
            # camelCase names, got nothing, fell back to the string "?", and
            # then PASSED the version check, because "?" > "2025-11-25" is True
            # in Python ("?" is ASCII 63, "2" is 50). A check that passes on
            # "I could not read it" is not a check. Hence: no fallback, and a
            # date comparison rather than a string one.
            server_name = getattr(getattr(init, "server_info", None), "name", None)
            proto = getattr(init, "protocol_version", None)
            print(f"  connected to '{server_name}', protocol {proto}")

            check(isinstance(proto, str) and REVISION.match(proto),
                  "the protocol version was actually read, not defaulted",
                  f"got {proto!r}, which is not a YYYY-MM-DD revision")

            if isinstance(proto, str) and REVISION.match(proto):
                got = tuple(int(x) for x in proto.split("-"))
                need = (2025, 11, 25)
                check(got >= need,
                      f"protocol {proto} meets the 2025-11-25 requirement",
                      f"negotiated {proto}, older than the track requires")
            else:
                check(False, "protocol version meets 2025-11-25",
                      "could not be evaluated, see above")

            check(server_name == "grounded-answers",
                  f"server identified itself as grounded-answers",
                  f"got {server_name!r}")

            tools = (await session.list_tools()).tools
            names = sorted(t.name for t in tools)
            print(f"  tools advertised: {names}")
            for want in ("ask", "say", "sources", "why_refused"):
                check(want in names, f"tool '{want}' is advertised over MCP")

            # The answerable one.
            r = await session.call_tool("ask", {"question": MUST_ANSWER})
            body = text_of(r)
            check('"ANSWERED"' in body or "'ANSWERED'" in body,
                  f"ANSWERED over the wire: {MUST_ANSWER!r}", body[:220])
            check("boiler-warranty.md" in body,
                  "the answer names the document it came from", body[:220])

            # The planted refusal. This is the gate: if it answers this, the
            # whole premise of the project is false.
            r = await session.call_tool("ask", {"question": MUST_REFUSE})
            body = text_of(r)
            check('"REFUSED"' in body or "'REFUSED'" in body,
                  f"REFUSED over the wire: {MUST_REFUSE!r}", body[:220])
            check("looked_in" in body or "checked" in body,
                  "the refusal carries what was searched", body[:220])

            # The spoken form, which is what a listener actually hears.
            r = await session.call_tool("say", {"question": MUST_REFUSE})
            spoken = text_of(r)
            check("cannot answer" in spoken.lower(),
                  "the spoken refusal says so plainly", spoken[:200])
            print(f"      spoken: {spoken[:150]}")

    print()
    if failures:
        print(f"  {failures} CHECK(S) FAILED")
    else:
        print("  MCP PROVEN over Streamable HTTP, by a client we did not write.")
    return 1 if failures else 0


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(HERE / "server.py"), "--port", str(PORT)],
        cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    try:
        # Wait for the port rather than sleeping a guessed amount.
        import socket
        for _ in range(100):
            if proc.poll() is not None:
                err = proc.stderr.read().decode()[-1500:] if proc.stderr else ""
                print("  server exited before serving:\n" + err)
                return 1
            with socket.socket() as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", PORT)) == 0:
                    break
            time.sleep(0.2)
        else:
            print(f"  server never opened port {PORT}")
            return 1
        return asyncio.run(run())
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())

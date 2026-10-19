"""An MCP server that can refuse.

Self-hosted, Streamable HTTP, for the Alexa+ track of the Amazon Developer
Hackathon 2026.

Run it:

    python server.py            # Streamable HTTP on 127.0.0.1:8000/mcp
    python server.py --stdio    # stdio, for a local MCP client

Why it exists: a voice assistant cannot show a citation. Every answer and
every refusal arrives in the same confident voice, and the listener has no way
to tell them apart. This server makes the difference audible. It answers only
from documents the household owns, and when it cannot, it says what it looked
in rather than inventing something plausible.
"""

from __future__ import annotations

import sys

from mcp.server.mcpserver import MCPServer

import sources
from mcp_refusal import INSTRUCTIONS, refusable

mcp = MCPServer(
    name="grounded-answers",
    title="Grounded Answers",
    version="0.1.0",
    instructions=(
        "Answers household questions ONLY from the household's own documents.\n\n"
        # The verdict contract comes from the mcp-refusal package rather than
        # being restated here, so the server and the library can never drift
        # into describing different behaviour to the model.
        + INSTRUCTIONS
    ),
)


@mcp.tool(
    name="ask",
    title="Ask the household documents",
    description=(
        "Answer a question from the household's own documents. Returns "
        "ANSWERED with the source and the exact line it came from, or REFUSED "
        "with the list of documents that were searched. Never guesses."
    ),
)
@refusable
def ask(question: str) -> dict:
    """Look the question up and return the verdict envelope.

    @refusable comes from mcp-refusal: if the lookup raises, the caller gets a
    CANNOT_CONCLUDE envelope naming what failed, instead of a protocol error
    that a voice assistant would have to paper over.
    """
    return sources.ask(question).to_dict()


@mcp.tool(
    name="say",
    title="What to read aloud",
    description=(
        "The same lookup as 'ask', returned as one sentence meant to be spoken "
        "verbatim. An answer names its source in the same breath; a refusal "
        "says what was searched."
    ),
)
def say(question: str) -> str:
    return sources.ask(question).spoken()


@mcp.tool(
    name="sources",
    title="What I can see",
    description=(
        "List the documents this server is able to answer from, so a person "
        "can tell whether a refusal means 'not true' or 'not loaded'."
    ),
)
@refusable
def list_sources() -> dict:
    docs = sources.load()
    return {
        "count": len(docs),
        "documents": [{"name": d.name, "lines": len(d.lines)} for d in docs],
        "note": (
            "These are the only things I can answer from. If something is not "
            "here, I will refuse rather than guess."
        ),
    }


@mcp.tool(
    name="why_refused",
    title="Why that was refused",
    description=(
        "Explain a refusal in full: every document searched and how many lines "
        "in each one touched the question. Use this when someone asks why the "
        "assistant would not answer."
    ),
)
def why_refused(question: str) -> dict:
    result = sources.ask(question)
    if result.verdict == "ANSWERED":
        return {
            "verdict": "ANSWERED",
            "note": "That question was not refused.",
            "source": result.source,
            "spoken": result.spoken(),
        }
    return {
        "verdict": "REFUSED",
        "because": result.because,
        "checked": [a.__dict__ for a in result.checked],
        "spoken": result.spoken(),
    }


def _port() -> int:
    if "--port" in sys.argv:
        return int(sys.argv[sys.argv.index("--port") + 1])
    return 8000


def _demo_app(port: int):
    """The MCP app, plus a page that speaks MCP to it from the browser.

    json_response=True so the transport is plain request/response JSON. SSE is
    the thing most likely to break behind nginx and Cloudflare, both of which
    buffer event streams, and it would break in the one place it cannot be
    debugged. See DEPLOY.md.
    """
    from pathlib import Path

    from starlette.responses import FileResponse
    from starlette.routing import Route

    page = Path(__file__).parent / "demo" / "index.html"
    app = mcp.streamable_http_app(json_response=True)
    app.routes.append(Route("/", lambda _req: FileResponse(page)))
    return app


if __name__ == "__main__":
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    elif "--demo" in sys.argv:
        import uvicorn

        port = _port()
        print(f"  Grounded Answers: http://127.0.0.1:{port}/   (MCP at /mcp)")
        uvicorn.run(_demo_app(port), host="127.0.0.1", port=port, log_level="warning")
    else:
        # Streamable HTTP is what the Alexa+ track requires. Bound to loopback
        # by default; put a TLS terminator in front of it to expose it.
        mcp.run(transport="streamable-http", host="127.0.0.1", port=_port())

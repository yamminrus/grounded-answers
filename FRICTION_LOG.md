# Friction Log

Build, Ship, Shape: Amazon Developer Hackathon 2026 — Alexa+ track.
Project: [Grounded Answers](https://github.com/yamminrus/grounded-answers).

Written while building, not reconstructed afterwards. Each entry gives the task,
the steps, expected vs. actual, a severity rating, the workaround we used, and a
suggestion we would actually want shipped.

---

## 1. A protocol check that could not fail — MCP Python SDK 2.x

**Severity: High.** Not because it broke the build, but because it did not.

**Task attempted.** Verify *over the wire* that our server negotiates protocol
revision `2025-11-25`, using the official SDK client rather than trusting our own
server's word for it.

**Steps taken.**

1. `pip install mcp` (2.x)
2. Open a session with `streamable_http_client` + `ClientSession`
3. Read the `InitializeResult` returned by `session.initialize()`
4. Assert the negotiated revision matches the expected one

**Expected result.** Reading the documented field returns the negotiated revision
string — or fails loudly if the attribute name is wrong.

**Actual result.** In 2.x, `InitializeResult` exposes `protocol_version`
(snake_case). The widely documented and widely blogged name is `protocolVersion`.
Reading the camelCase name does not raise. It returns `None`.

Our check did this:

```python
proto = getattr(init, "protocolVersion", "?")   # always "?" on 2.x
assert proto >= "2025-11-25"                    # "?" > "2" → True
```

In Python, `"?"` sorts after `"2"`, so the assertion **passed while reading
nothing at all.** The suite was green and the protocol version was never checked.

A failing test is a nuisance. A test that cannot fail is worse than no test,
because it is counted as coverage. We only found this because we went looking
specifically for checks that could not come out differently.

**Workaround used.** Read `protocol_version` with no default, assert it is a
string before comparing, and parse the revision as a date rather than comparing
strings — so a missing attribute raises instead of defaulting into a pass:

```python
proto = getattr(init, "protocol_version", None)
check(isinstance(proto, str) and REVISION.match(proto),
      "the protocol version was actually read, not defaulted")
```

**Suggestion.** Keep a deprecation shim on the renamed result-model attributes
that emits a `DeprecationWarning` and returns the real value, instead of letting
the old camelCase name resolve to `None`. The module-level renames already fail
loudly as `ImportError`, which is the correct behaviour — the attribute renames
should match it. Right now they are the only ones that fail *silently*.

---

## 2. The 1.x → 2.x rename has no migration table

**Severity: Medium.** Loud, harmless, and entirely avoidable.

**Task attempted.** Follow any current tutorial to stand up a Streamable HTTP
server.

**Expected result.** The imports in the docs work against the installed version.

**Actual result.** Nearly everything written about this SDK is 1.x.
`FastMCP` is now `MCPServer`. `streamablehttp_client` is now
`streamable_http_client`. Both fail as a plain `ImportError`, which reads like
"you installed it wrong" rather than "this moved."

**Workaround used.** Read the installed package's source to recover the new names.

**Suggestion.** A one-page 1.x → 2.x rename table in the docs. It would have
prevented this and entry 1 in about thirty seconds of reading.

---

## 3. SSE is the default, and SSE is what breaks in production

**Severity: High**, because the failure appears in the one place you cannot
attach a debugger.

**Task attempted.** Deploy the server behind nginx and a CDN.

**Expected result.** The transport works in production the way it works locally.

**Actual result.** The default Streamable HTTP app streams responses. Behind
nginx with `proxy_buffering on` — the default — and behind a CDN, an event stream
buffers. The client hangs with no error. Nothing is logged, because nothing went
wrong, exactly: the bytes are simply sitting in a buffer. Locally it had worked
every time.

**Workaround used.** `mcp.streamable_http_app(json_response=True)`, which makes
the transport plain request/response JSON and fixes it completely. This one
keyword is the difference between this project deploying and not deploying.

**Suggestion.** Make the trade-off louder in the deployment docs, close to the
first `streamable_http_app()` example. The failure it prevents looks like a
network problem rather than a transport choice, so people will debug the wrong
layer first. We did.

---

## What we would keep exactly as it is

Mounting MCP inside an existing ASGI app. `streamable_http_app()` returns an
ordinary Starlette app, so serving our demo page next to `/mcp` took one line and
no shimming:

```python
app = mcp.streamable_http_app(json_response=True)
app.routes.append(Route("/", lambda _req: FileResponse(page)))
```

And tool registration from type hints: the JSON schema that reaches the client is
generated from the Python signature, and it was correct every time without us
hand-writing one.

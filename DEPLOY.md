# Getting this where Alexa+ can reach it

Measured against the actual host on 2026-10-18, not sketched from memory.

## What the host already has

| | |
|---|---|
| nginx | active |
| certs present | `zealousmirror.com`, `app.zealousmirror.com` |
| python3 | 3.14.4, same as the build |
| port 80 | open to anyone (kept open for ACME HTTP-01) |
| **port 443** | **allowed from Cloudflare IP ranges only** |

## The constraint that decides the design

**Alexa+ connects from Amazon's infrastructure, not from Cloudflare.** With 443
restricted to Cloudflare ranges, a direct origin connection from Amazon is
refused before it reaches nginx.

So the endpoint goes **behind the Cloudflare proxy (orange cloud)**. Cloudflare
accepts the request from Amazon and connects to the origin from a Cloudflare
address, which the firewall already permits. The origin lock stays intact and no
firewall rule is loosened.

Note this is the **opposite** of what the Ledger deployment needed. That one
required grey cloud so certbot's HTTP-01 challenge could reach port 80
directly. Different requirement, opposite setting. Do not copy that step here.

## Use JSON responses, not SSE

Streamable HTTP can stream over `text/event-stream`. **nginx buffers SSE by
default and Cloudflare buffers and times it out**, so a streaming transport is
the most likely thing to break in the exact place it cannot be debugged.

The SDK's `json_response=True` serves plain JSON request/response instead.
Verified on 2026-10-18: protocol **2025-11-25** still negotiated, the refusal
path still works, no event stream required.

```python
mcp.run(transport="streamable-http", host="127.0.0.1", port=8000,
        json_response=True)
```

If SSE is ever needed, nginx requires `proxy_buffering off;` and
`proxy_read_timeout` raised, and Cloudflare will still cap the connection.

## The steps, in order

1. **DNS**: `mcp` → the host, **orange cloud (proxied)**.
2. **systemd unit** for the server, `Restart=always`, `Environment=HOST=127.0.0.1`,
   bound to loopback so nginx is the only route in. Same shape as the-ledger.
3. **nginx vhost**: `server_name mcp.zealousmirror.com;` proxying `/mcp` to
   `127.0.0.1:8000`, with `proxy_http_version 1.1` and the forwarding headers.
4. **Certificate**: Cloudflare terminates TLS for the visitor. The origin still
   needs a cert for Full mode; certbot over HTTP-01 needs port 80 reachable,
   which it is.
5. **Prove it from outside**: run `prove_mcp.py` against the public URL, not
   against loopback. A server that answers on 127.0.0.1 has not been shown to
   answer to Amazon.

## What is not done

No part of this has been deployed. Every line above is a measurement of the
host or of the SDK, plus the order the steps have to happen in. The entry works
locally and is proven locally; the public endpoint is still to build.

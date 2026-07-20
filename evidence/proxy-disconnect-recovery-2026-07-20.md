# Proxy disconnect recovery — 2026-07-20

A loopback upstream returns one complete SSE event in a chunked response and
then closes the socket without the terminating chunk. The generated proxy is
run under Node with a temporary registry and a fake published access token.

The regression proves that:

- the completed event reaches the client unchanged;
- the proxy does not append internal handler-error text to the partial stream;
- the proxy process stays alive after the upstream disconnect;
- the next request succeeds with the latest published token; and
- stale client authorization is still replaced at the upstream boundary.

No public endpoint, live credential, or installed proxy participates.

## Hosted-runtime red evidence

The first real GitHub Actions run (`29769238303`) exercised the same test under
Node 24 and failed. Unlike the local runtime, it appended
`token proxy: handler error: terminated` after the valid SSE event. The hosted
gate therefore blocked artifact upload.

The proxy error boundary now destroys an already-started downstream response
when upstream streaming fails. It emits a synthetic 502 body only when no
response headers have been sent. A structural regression assertion protects
this rule even on runtimes that treat the truncated upstream as a clean EOF.

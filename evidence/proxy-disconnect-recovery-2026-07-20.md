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

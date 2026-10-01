# Security and intended deployment

This is a single-user local prototype. Bind to loopback only; there is no internet deployment or
multiuser authorization layer. Namespace separation is not an access-control boundary. Local
clients with access to the service can read and append memory.

HTTP enforces trusted host and same-origin browser access. MCP uses stdio. Updates are append-only
and version-checked. No HTTP/MCP endpoint executes arbitrary commands or model-provided code.
The release fixture executes checked-in synthetic code only, in a disposable temporary directory.

Memory records and retrieved source text are untrusted input. Applications must preserve that
boundary when adding context to a model. The prototype does not guarantee resistance to prompt
injection, truthful extraction or correct model actions. `.local/` is ignored by Git but contains
full histories and raw model requests; review exports before sharing.

For a vulnerability report, use GitHub's private vulnerability reporting if enabled. Do not put
credentials or private user histories in public issues.

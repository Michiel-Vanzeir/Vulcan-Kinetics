# Runtime security findings

## Preview file inclusion

`preview-server.mjs` now binds every public asset to its own literal file read. HTTP
request paths select a handler, never a filename or filesystem URL. Unknown paths return
404. Query parameters cannot alter the selected file. Assets are still read per request,
so refreshing the preview continues to show HTML/CSS changes without a server restart.

HTTP regression tests cover traversal, encoded traversal, absolute paths, null bytes,
private configuration files and filename query parameters.

## Timing warning in the people panel

The panel has no password, bearer credential or secret comparison. The catalog's `token`
property contains public payroll identifiers such as `notice_period`, not authentication
tokens. Topic label lookup now uses a Map keyed by those public identifiers, and the
local variables are named `topicId` to distinguish them from credentials.

A password-bruteforce timing finding on that public lookup is a false positive.
JavaScript Map access is not claimed to be constant time. Real credentials remain on the
server and are checked with Python's `hmac.compare_digest` in `app/auth.py`. Do not add
credentials to browser state or replace server authentication with UI comparisons.

## Agent SSRF boundary

The capture transport accepts only HTTP(S) origins on `127.0.0.1`, `localhost` or `[::1]`.
`localhost` is converted to the literal `127.0.0.1`, avoiding DNS rebinding. URL credentials,
extra paths, query strings, fragments, external hosts and other protocols are rejected
before a worker starts. Ports remain configurable for local development.

Only `/analyze`, `/experts` and `/preferences` can be requested. Direct HTTP connections
do not follow redirects or use environment proxy settings, so a backend cannot redirect
the bearer credential or derived signals to another service. Responses are limited to
1 MiB and must contain a JSON object. All agent network I/O remains inside `Transport._post`.
The backend origin is operator configuration, never derived from typed text or API input.

Tests cover forbidden destinations and endpoints, literal loopback normalization,
redirect credential leakage and proxy bypass attempts.

## Repository assertions

`repository.create_node` uses an explicit allowlist check and raises `ValueError` before
interpolating a Cypher label. It no longer relies on `assert`, which Python removes with
`-O`. Properties remain query parameters. Tests verify that invalid labels never reach
the database and that validation still works in an optimized Python subprocess.

These are code changes and regression evidence, not an Aikido rescan. Publish the reviewed
commit and rescan it to confirm closure; retain the public-topic explanation when reviewing
the timing warning as a false positive.

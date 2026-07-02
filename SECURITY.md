# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead, use
GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository ("Security" tab → "Report a vulnerability"), or email the
maintainer at <vinoththecool7@gmail.com> with:

- a description of the issue and its impact,
- steps to reproduce (a curl command or short script is ideal),
- any suggested fix, if you have one.

You should get an initial response within a few days. Please give us a
reasonable window to ship a fix before public disclosure.

## Supported versions

Kara is pre-1.0: only the latest commit on `master` receives security fixes.

## Security model (what is — and isn't — protected)

Kara is a **single-user, self-hosted** application with **no built-in
authentication**. Anyone who can reach the API can read, create, and delete
every chat session and profile. Deploy it on `localhost` (the default
compose bindings) or behind your own authenticating reverse proxy — never
directly on the public internet.

Mitigations in place:

- All published ports bind to `127.0.0.1` by default (`KARA_BIND_HOST` to override).
- Host-header allowlist (`ALLOWED_HOSTS`) blocks DNS-rebinding attacks.
- PAN is masked to its last four characters before anything is persisted,
  returned to clients, or fed back into LLM context; document-derived free
  text is flattened before reaching prompts.
- Per-IP rate limits on chat/upload/compute (`X-Forwarded-For` honoured only
  when `TRUST_PROXY_HEADERS=true`).
- Security headers, generic error messages, session TTL cleanup,
  loopback-bound Postgres, non-root containers.

Reports that assume a deployment outside this model (e.g. "anyone on the
internet can call the API" on a deliberately exposed, un-proxied instance)
are appreciated but will likely be treated as documentation issues rather
than vulnerabilities.

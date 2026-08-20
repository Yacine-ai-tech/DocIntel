# Telemetry & Privacy

This document describes exactly what DocIntel's code sends over the network for
telemetry purposes, and how to turn it off. No vague language — this is what the code
in `api.py` actually does.

## What DocIntel's code sends

On startup, a background thread (`api.py`, `_send_telemetry`) sends **one HTTP POST**,
at most once per ~6 hours per running instance:

```json
{"service": "DocIntel", "event": "startup", "instance_id": "<random 16-char hex string>"}
```

That's the entire payload. No document content, filenames, extraction results, API keys,
IP addresses, or configuration are included by DocIntel's code.

- **Destination**: the `TELEMETRY_URL` env var. It defaults to **blank**, which disables
  telemetry entirely — no destination means no request is ever made. Set it yourself
  (e.g. to your own collector) to opt in.
- **`instance_id`**: a **randomly generated UUID** (`uuid.uuid4()`), created once and
  persisted to `logs/.telemetry_instance_id`, so repeat startups of the same install
  report the same ID (letting the receiving end de-duplicate) without that ID being
  derived from any hardware identifier. **Delete that file to reset it.** Earlier versions
  of this code derived the ID from the machine's MAC address (`uuid.getnode()`) — that was
  changed because a hardware-derived ID doesn't rotate and is a stronger, non-consensual
  fingerprint than a locally-generated random ID needs to be for a simple install count.
- **Rate limiting**: `logs/.telemetry_last_ping` timestamps the last send; no ping is sent
  again within 6 hours of the last one.

## What you should know about the destination, honestly

Once this POST leaves your machine, it's a normal HTTP request — like any HTTP request to
any server, the receiving server's infrastructure sees the connecting IP address and
standard request metadata (user agent, etc.) as part of accepting the connection. That's
true of every network request ever made by every piece of software; it is not something
DocIntel's code adds on top of the payload above. If you don't want this instance making
that connection at all, use the opt-out below — no HTTP request is made, period.

## What is NOT sent

- No document content, uploaded files, extraction results, or OCR text.
- No API keys, tokens, or `.env` contents.
- No IP address, hostname, or path information added by DocIntel's code (see above —
  DocIntel's *payload* contains only `service`, `event`, `instance_id`).

## Separately: local debug logging (never sent over the network)

If `global_scripts/omni_logging.py` is importable (only true when this DocIntel checkout
sits inside the author's own multi-project workspace — it's absent from a standalone
clone and the import is wrapped in a no-op fallback), route selections, fallbacks, and
request/response metrics are written to `logs/DocIntel.log` on disk for local debugging.
This is a local file write only — nothing in this path makes a network call.

## How to opt out

Two independent ways, either one is sufficient:

1. Set `TELEMETRY_OPT_OUT=true` in your `.env` (see `.env.example`). The background
   thread returns immediately and no HTTP request is made — not even a DNS lookup.
2. Leave `TELEMETRY_URL` blank (the default). With no destination configured, the code
   returns before making any request.

## README view pixel

`README.md` may include a 1×1 tracking pixel to count repository page views on GitHub —
unrelated to the code above. Remove the `<img>` tag from your fork's `README.md` to
disable it.

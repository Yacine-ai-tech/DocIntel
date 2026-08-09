# n8n Integration

DocIntel doesn't ship an n8n community node — it doesn't need one. Every endpoint is a
plain HTTP/multipart API, so n8n's built-in **HTTP Request** node is the integration
point. There are two patterns depending on whether you're processing one file or a batch.

## Pattern 1 — single document, synchronous (HTTP Request node only)

For one file at a time, just call DocIntel directly and use the response in the same
workflow — no webhook needed.

**HTTP Request node config:**
- Method: `POST`
- URL: `https://<your-docintel-host>/process`
- Body: `multipart-form-data`
  - `file`: binary data from a previous node (e.g. Google Drive/Slack/HTTP Request download)
  - `route`: `vision_route_a` (Claude, highest quality) or `vision_route_b` (your own
    Ollama, local or self-hosted-remote — see the main README for `ROUTE_B_MODE`) or
    `ocr_fallback`
  - `doc_type`: `auto`, `invoice`, `contract`, `receipt`, `financial_report`, `form`, ...

The response (`fields`, `confidence`, `page_count`) is available immediately to the next
node in the workflow.

## Pattern 2 — batch upload, async via webhook (no polling)

For many files, `/batch/upload` runs in the background and can return in milliseconds.
Rather than polling `GET /batch/{job_id}` in a loop, give DocIntel an n8n Webhook URL and
it will POST the finished results to it — this resumes a *second* n8n workflow the moment
the batch is done.

1. **Import** [`docintel-batch-webhook.json`](docintel-batch-webhook.json) into n8n
   (Workflows → Import from File), or build your own workflow starting with a **Webhook**
   node (`HTTP Method: POST`).
2. **Activate** the workflow and copy the Webhook node's **Production URL**.
3. From whatever workflow ingests your documents, add an **HTTP Request** node:
   - Method: `POST`
   - URL: `https://<your-docintel-host>/batch/upload`
   - Body: `multipart-form-data`
     - `files`: one or more binary files
     - `route`, `doc_type`: same as Pattern 1
     - `webhook_url`: the Production URL from step 2
4. DocIntel returns `{job_id, total, webhook_url}` immediately. When the batch finishes,
   it POSTs `{job_id, status, total, processed, failed, finished_at, results}` to
   `webhook_url` — `results` is the same array `GET /batch/{job_id}/results` would return.

The imported template splits `results` into one n8n item per file so you can fan each
extraction into a Sheet, database, CRM, or Slack message downstream.

## Notes

- `webhook_url` is optional — omit it and poll `GET /batch/{job_id}` / `GET
  /batch/{job_id}/results` instead, if you'd rather not expose a public n8n webhook.
- Webhook delivery is best-effort: if it fails (n8n unreachable, workflow deactivated,
  etc.), the job itself still completed and its results remain available via
  `GET /batch/{job_id}/results` — DocIntel logs the delivery failure but does not retry.
- If your n8n instance and DocIntel are both self-hosted on the same network, use the
  internal URL for `webhook_url` to avoid a round-trip through the public internet.

# Telemetry & Privacy Policy

This project strictly follows 2026 open-source privacy best practices. We believe in complete transparency regarding what data is collected and why.

### 1. Repository Analytics (Scarf.sh)
We embed a Scarf.sh tracking pixel in our `README.md` to monitor repository traffic and package downloads. 
- **Privacy Guarantee:** Strict IP anonymization is enabled. No personal data is tracked.
- **Opt-out:** You can freely remove the pixel link from the README in your own fork.

### 2. Edge Infrastructure & API Security
Our live demonstration APIs are protected by a global Edge Web Application Firewall (WAF).
- **Purpose:** The WAF captures standard, anonymized HTTP metadata (such as routing headers) exclusively to enforce strict rate-limiting, prevent abuse, and block DDoS attacks against our inference servers.
- **Privacy Guarantee:** We **NEVER** log, intercept, or transmit your private inputs, LLM prompts, or Personally Identifiable Information (PII). The edge layer is entirely blind to payload contents. 

Your data remains your own.

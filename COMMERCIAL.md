# Commercial Licensing

This software is free and open-source under the **GNU Affero General Public License v3.0 (AGPL-3.0)**. 

You are free to use this software for any purpose (including commercial use), **provided** you comply fully with the AGPL-3.0. A key requirement of the AGPL is that if you modify this software or use it as part of a service over a network, you must completely open-source your entire application and backend infrastructure.

### Enterprise & Proprietary Use
If your corporate legal policies forbid you from open-sourcing your proprietary internal systems, or if you wish to distribute a commercial product without the strict copyleft requirements of the AGPL, you **MUST** purchase a Commercial License.

**A Commercial License exempts you from the AGPL requirements, allowing you to:**
- Integrate this software into your proprietary, closed-source systems.
- Deploy the software for internal business operations without publishing your modifications.
- Offer the software as part of a managed or hosted service.

**To obtain a Commercial License, contact:** contact@ysiddo-ai-projects.app

Commercial licensing is offered through OmniIntelOS, the unified platform this project's
capability is also offered as part of (full-platform SaaS, per-module SaaS, or self-hosted/
hybrid deployment) — the same contact handles a standalone commercial license for this
repository or a broader OmniIntelOS engagement.

### Registering your license key

After purchasing a Commercial License you will receive a key in the form
`LIC-<PROJECT>-<ID>`. Set it in your deployment's environment:

```
LICENSE_KEY=LIC-<PROJECT>-<ID>
```

On startup the application reports the key anonymously (project, random install
id, version, coarse country/organization) so your licensed install is
associated with your license. This beacon is opt-out-able at any time:

```
LICENSE_BEACON_DISABLE=true
```

License status (active / expired / revoked / unlicensed) is visible only to the
licensor; no usage data beyond the install ping is collected.

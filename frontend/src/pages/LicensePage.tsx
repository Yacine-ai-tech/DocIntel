export default function LicensePage() {
  return (
    <div style={{ maxWidth: 820, margin: '0 auto', padding: '2rem 1.25rem', lineHeight: 1.7 }}>
      <h1 style={{ fontSize: '1.6rem', marginBottom: '0.5rem' }}>License & Terms</h1>
      <p style={{ opacity: 0.75 }}>
        This software is <strong>free and open-source</strong> under the{' '}
        <a href="https://www.gnu.org/licenses/agpl-3.0.html" target="_blank" rel="noreferrer">GNU Affero General Public License v3.0</a>.
        See the <code>LICENSE</code> file in the source repository.
      </p>

      <h2 style={{ fontSize: '1.15rem', marginTop: '1.75rem' }}>Open-source use (AGPL-3.0)</h2>
      <p>
        You may use, modify, and self-host this software — including for commercial purposes —
        provided that if you make a modified version available to users over a network, you
        release your corresponding source under AGPL-3.0 as well.
      </p>

      <h2 style={{ fontSize: '1.15rem', marginTop: '1.75rem' }}>Commercial license</h2>
      <p>
        If your use cannot comply with AGPL obligations (proprietary/closed-source deployments,
        embedded products, managed services without source disclosure), a{' '}
        <strong>Commercial License</strong> is available that waives copyleft for that use.
        See <code>COMMERCIAL.md</code> in the repository or contact the maintainer.
      </p>
      <p>
        Licensed installs set <code>LICENSE_KEY=LIC-...</code> in their environment; the key is
        reported anonymously at startup so the install is associated with the license.
        Opt out anytime with <code>LICENSE_BEACON_DISABLE=true</code>.
      </p>

      <h2 style={{ fontSize: '1.15rem', marginTop: '1.75rem' }}>This hosted demo</h2>
      <p>
        This demo is provided for evaluation. Uploaded content is processed for the app's
        function and may be retained for operational analytics; session-scoped sandbox uploads
        are wiped per the published retention policy. Do not upload unlawful content or data
        you lack rights to process. The demo is provided "as is" without warranty.
      </p>

      <h2 style={{ fontSize: '1.15rem', marginTop: '1.75rem' }}>Telemetry</h2>
      <p style={{ fontSize: '0.9rem', opacity: 0.8 }}>
        This deployment sends an anonymous startup ping (install count only) and usage analytics
        (pages, interactions, coarse country/organization) to the operator's gateway. Both are
        standard for the hosted demo; self-hosted instances can disable them via{' '}
        <code>TELEMETRY_OPT_OUT=true</code>, <code>DO_NOT_TRACK=1</code>, or by pointing{' '}
        <code>TELEMETRY_URL</code>/<code>LICENSE_BEACON_URL</code> at your own collector.
      </p>
    </div>
  );
}

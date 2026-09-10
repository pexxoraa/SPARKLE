/* Private data is rendered as text nodes, never interpreted as HTML. */
(() => {
  function text(document, parent, tag, value) {
    const element = document.createElement(tag);
    element.textContent = String(value);
    parent.appendChild(element);
    return element;
  }

  function render({container, proposals, api, onChange, document = globalThis.document,
                   confirm = (message) => globalThis.confirm(message), now = () => Date.now()}) {
    container.replaceChildren();
    const pending = proposals.filter((p) => p.status === 'pending');
    if (!pending.length) text(document, container, 'p', 'No pending proposals.');
    for (const proposal of pending) {
      const card = text(document, container, 'div', '');
      card.className = 'list-item';
      const claim = proposal.payload || {};
      const verification = proposal.verification || {};
      const id = proposal.id;
      const digest = proposal.digest;
      const identityValid = /^[a-f0-9]{32}$/.test(id || '') && /^[a-f0-9]{64}$/.test(digest || '') && claim.id === id;
      text(document, card, 'strong', `${claim.category} / ${claim.key}`);
      text(document, card, 'pre', claim.value || 'Missing claim');
      text(document, card, 'small', `Proposal: ${id}`);
      text(document, card, 'small', `Digest: ${digest}`);
      const expiryValid = Number.isFinite(claim.expires_at) && Number.isFinite(new Date(claim.expires_at * 1000).getTime());
      text(document, card, 'small', `Expiry: ${expiryValid ? new Date(claim.expires_at * 1000).toISOString() : 'UNKNOWN'}`);
      text(document, card, 'small', `Verification: ${verification.status || 'INCONCLUSIVE'} — ${verification.reason || 'missing evidence'}`);
      text(document, card, 'small', `Conflict: ${Boolean(proposal.conflict)}; target blocked: ${Boolean(proposal.target_blocked)}`);
      text(document, card, 'pre', JSON.stringify(proposal.evidence || [], null, 2));
      const label = text(document, card, 'label', 'Require VERIFIED evidence. Disable only after independent operator review. ');
      const strict = document.createElement('input'); strict.type = 'checkbox'; strict.checked = true; label.appendChild(strict);
      const approve = text(document, card, 'button', 'Approve exact proposal');
      const reject = text(document, card, 'button', 'Reject proposal');
      const validate = text(document, card, 'button', 'Revalidate evidence');
      const message = text(document, card, 'p', '');
      let busy = false;
      function canApprove() {
        return identityValid && expiryValid && claim.expires_at * 1000 > now() && proposal.expired === false &&
          proposal.conflict === false && proposal.target_blocked === false && ['VERIFIED','INCONCLUSIVE'].includes(verification.status) &&
          verification.status !== 'REJECTED' && (!strict.checked || verification.status === 'VERIFIED');
      }
      function controls() {
        approve.disabled = busy || !canApprove();
        reject.disabled = busy || !identityValid;
        validate.disabled = busy || !identityValid;
        strict.disabled = busy;
      }
      strict.addEventListener('change', controls);
      async function action(decision) {
        if (busy || !identityValid || (decision === 'approve' && !canApprove())) return;
        if (decision !== 'validate' && !confirm(`${decision === 'approve' ? 'Approve' : 'Reject'} this exact proposal? This does not prove broader factual truth.`)) return;
        busy = true; controls(); message.textContent = 'Submitting…';
        try {
          const body = {proposal_id:id, digest};
          if (decision !== 'validate') Object.assign(body, {decision, require_verified:strict.checked});
          await api(decision === 'validate' ? '/api/memory/validate' : '/api/memory/review', {
            method:'POST', body:JSON.stringify(body),
          });
          message.textContent = 'Recorded. Reloading current state…';
          await onChange();
        } catch (_) {
          message.textContent = 'Request failed. Reload and inspect current evidence; no success is assumed.';
        } finally {
          busy = false; controls();
        }
      }
      approve.addEventListener('click', () => action('approve'));
      reject.addEventListener('click', () => action('reject'));
      validate.addEventListener('click', () => action('validate'));
      controls();
    }
  }

  function history(container, events, document = globalThis.document) {
    container.replaceChildren();
    if (!events.length) text(document, container, 'p', 'No history recorded.');
    for (const event of events) {
      const card = text(document, container, 'div', ''); card.className = 'list-item';
      text(document, card, 'strong', `${event.id} · ${event.kind || event.action}`);
      text(document, card, 'pre', JSON.stringify(event, null, 2));
    }
  }
  const exports = {render, history};
  globalThis.SparkleMemoryReview = exports;
  if (typeof module !== 'undefined') module.exports = exports;
})();

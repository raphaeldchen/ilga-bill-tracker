let allActions = [];

// ── Init ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadBills();
  loadActions();
});

// ── Data loading ──────────────────────────────────────────────

async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  renderBills(bills);
}

async function loadActions() {
  const actions = await apiFetch('/api/actions');
  if (actions === null) return;

  // Sort most recent first. Dates from CSV are m/d/yyyy; from OpenStates yyyy-mm-dd.
  allActions = actions.sort((a, b) => parseDate(b.date) - parseDate(a.date));
  renderActions();
}

// ── Rendering ─────────────────────────────────────────────────

function renderBills(bills) {
  const list = document.getElementById('bill-list');
  if (bills.length === 0) {
    list.innerHTML = '<li style="color:var(--pico-muted-color);font-size:0.8rem">No bills tracked yet.</li>';
  } else {
    list.innerHTML = bills.map(b => `
      <li>
        <span>${b.id}</span>
        <button class="remove-btn" title="Remove ${b.id}" onclick="removeBill('${b.id}')">×</button>
      </li>
    `).join('');
  }

  const filter = document.getElementById('bill-filter');
  const current = filter.value;
  filter.innerHTML = '<option value="">All Bills</option>' +
    bills.map(b => `<option value="${b.id}">${b.id}</option>`).join('');
  if (current) filter.value = current;
}

function renderActions() {
  const filterId = document.getElementById('bill-filter').value;
  const rows = filterId ? allActions.filter(a => a.bill_id === filterId) : allActions;

  const count = document.getElementById('action-count');
  count.textContent = `${rows.length} action${rows.length !== 1 ? 's' : ''}`;

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(a => `
    <tr>
      <td>${a.bill_id}</td>
      <td>${a.date}</td>
      <td>${a.chamber}</td>
      <td>${escapeHtml(a.description)}</td>
    </tr>
  `).join('');
}

function applyFilter() {
  renderActions();
}

// ── Actions ───────────────────────────────────────────────────

async function addBill() {
  const input = document.getElementById('add-bill-input');
  const errorEl = document.getElementById('add-error');
  const btn = document.getElementById('add-bill-btn');
  const billId = input.value.trim();

  if (!billId) return;

  errorEl.classList.add('hidden');
  btn.setAttribute('aria-busy', 'true');

  try {
    const res = await fetch('/api/bills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bill_id: billId }),
    });

    if (res.ok) {
      input.value = '';
      await Promise.all([loadBills(), loadActions()]);
      showToast(`${billId.toUpperCase()} added`, 'success');
    } else {
      const err = await res.json();
      errorEl.textContent = err.detail || 'Failed to add bill.';
      errorEl.classList.remove('hidden');
    }
  } finally {
    btn.removeAttribute('aria-busy');
  }
}

async function removeBill(billId) {
  if (!confirm(`Remove ${billId} from tracking? Its action history will also be deleted.`)) return;

  const res = await fetch(`/api/bills/${billId}`, { method: 'DELETE' });
  if (res.ok) {
    await Promise.all([loadBills(), loadActions()]);
    showToast(`${billId} removed`, 'success');
  } else {
    showToast(`Failed to remove ${billId}`, 'error');
  }
}

async function fetchUpdates() {
  const btn = document.getElementById('fetch-btn');
  btn.setAttribute('aria-busy', 'true');
  btn.textContent = 'Fetching…';

  try {
    const res = await fetch('/api/fetch', { method: 'POST' });

    if (!res.ok) {
      const err = await res.json();
      const msg = res.status === 429
        ? 'Rate limit reached. OpenStates allows 250 requests/day on the free tier — try again tomorrow.'
        : (err.detail || 'Fetch failed.');
      showToast(msg, 'error');
      return;
    }

    const result = await res.json();
    await loadActions();

    const msg = `${result.new_actions} new action${result.new_actions !== 1 ? 's' : ''} across ${result.updated} bill${result.updated !== 1 ? 's' : ''}`;
    showToast(msg, 'success');

    if (result.errors.length > 0) {
      const failed = result.errors.map(e => e.bill_id).join(', ');
      showToast(`Could not fetch: ${failed}`, 'error');
    }

    setLastUpdated();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.textContent = 'Fetch Updates';
  }
}

// ── Helpers ───────────────────────────────────────────────────

async function apiFetch(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  } catch (e) {
    showToast(`Failed to load ${url}: ${e.message}`, 'error');
    return null;
  }
}

let toastTimer;
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.add('hidden'), 4000);
}

function setLastUpdated() {
  const el = document.getElementById('last-updated');
  el.textContent = `Last fetched ${new Date().toLocaleString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: 'numeric', minute: '2-digit',
  })}`;
}

function parseDate(str) {
  if (!str) return 0;
  // Handles both "1/13/2025" (CSV) and "2025-01-13" (OpenStates)
  return new Date(str).getTime() || 0;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

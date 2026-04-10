let allActions = [];

document.addEventListener('DOMContentLoaded', function() {
  loadBills();
  loadActions();

  document.getElementById('bill-list').addEventListener('click', function(e) {
    var btn = e.target.closest('.remove-btn');
    if (btn) removeBill(btn.dataset.billId);
  });
});

async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  renderBills(bills);
}

async function loadActions() {
  const actions = await apiFetch('/api/actions');
  if (actions === null) return;
  allActions = actions.sort(function(a, b) { return parseDate(b.date) - parseDate(a.date); });
  renderActions();
}

function renderBills(bills) {
  const list = document.getElementById('bill-list');
  if (bills.length === 0) {
    list.innerHTML = '<li style="color:var(--pico-muted-color);font-size:0.8rem">No bills tracked yet.</li>';
    document.getElementById('bill-filter').innerHTML = '<option value="">All Bills</option>';
    return;
  }

  list.innerHTML = bills.map(function(b) {
    var id = escapeHtml(b.id);
    return '<li><span>' + id + '</span>' +
      '<button class="remove-btn" data-bill-id="' + id + '" title="Remove ' + id + '">&times;</button>' +
      '</li>';
  }).join('');

  const filter = document.getElementById('bill-filter');
  const current = filter.value;
  filter.innerHTML = '<option value="">All Bills</option>' +
    bills.map(function(b) {
      var id = escapeHtml(b.id);
      return '<option value="' + id + '">' + id + '</option>';
    }).join('');
  if (current) filter.value = current;
}

function renderActions() {
  const filterId = document.getElementById('bill-filter').value;
  const rows = filterId ? allActions.filter(function(a) { return a.bill_id === filterId; }) : allActions;

  document.getElementById('action-count').textContent =
    rows.length + ' action' + (rows.length !== 1 ? 's' : '');

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(function(a) {
    return '<tr>' +
      '<td>' + escapeHtml(a.bill_id) + '</td>' +
      '<td>' + escapeHtml(a.date) + '</td>' +
      '<td>' + escapeHtml(a.chamber) + '</td>' +
      '<td>' + escapeHtml(a.description) + '</td>' +
      '</tr>';
  }).join('');
}

function applyFilter() {
  renderActions();
}

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

    if (res.status === 401) { window.location.href = '/login'; return; }

    if (res.ok) {
      input.value = '';
      await Promise.all([loadBills(), loadActions()]);
      showToast(billId.toUpperCase() + ' added', 'success');
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
  if (!confirm('Remove ' + billId + ' from tracking? Its action history will also be deleted.')) return;

  const res = await fetch('/api/bills/' + billId, { method: 'DELETE' });
  if (res.status === 401) { window.location.href = '/login'; return; }

  if (res.ok) {
    await Promise.all([loadBills(), loadActions()]);
    showToast(billId + ' removed', 'success');
  } else {
    showToast('Failed to remove ' + billId, 'error');
  }
}

async function fetchUpdates() {
  const btn = document.getElementById('fetch-btn');
  btn.setAttribute('aria-busy', 'true');
  btn.textContent = 'Fetching...';

  try {
    const res = await fetch('/api/fetch', { method: 'POST' });
    if (res.status === 401) { window.location.href = '/login'; return; }

    if (!res.ok) {
      const err = await res.json();
      const msg = res.status === 429
        ? (err.detail || 'OpenStates rate limit reached - try again tomorrow.')
        : (err.detail || 'Fetch failed.');
      showToast(msg, 'error');
      return;
    }

    const result = await res.json();
    await loadActions();

    showToast(
      result.new_actions + ' new action' + (result.new_actions !== 1 ? 's' : '') +
      ' across ' + result.updated + ' bill' + (result.updated !== 1 ? 's' : ''),
      'success'
    );

    if (result.errors.length > 0) {
      showToast('Could not fetch: ' + result.errors.map(function(e) { return e.bill_id + ' (' + e.error + ')'; }).join('; '), 'error');
    }

    setLastUpdated();
  } finally {
    btn.removeAttribute('aria-busy');
    btn.textContent = 'Fetch Updates';
  }
}

async function apiFetch(url) {
  try {
    const res = await fetch(url);
    if (res.status === 401) { window.location.href = '/login'; return null; }
    if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
    return res.json();
  } catch (e) {
    showToast('Failed to load data: ' + e.message, 'error');
    return null;
  }
}

let toastTimer;
function showToast(message, type) {
  type = type || 'success';
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function() { toast.classList.add('hidden'); }, 4000);
}

function setLastUpdated() {
  document.getElementById('last-updated').textContent =
    'Last fetched ' + new Date().toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
}

function parseDate(str) {
  if (!str) return 0;
  return new Date(str).getTime() || 0;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

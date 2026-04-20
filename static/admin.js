let allActions = [];
let allBills = [];
let collapsedView = true;

document.addEventListener('DOMContentLoaded', async function() {
  await loadBills();
  loadActions();

  document.getElementById('bill-list').addEventListener('click', function(e) {
    var btn = e.target.closest('.remove-btn');
    if (btn) removeBill(btn.dataset.billId);
  });
});

async function loadBills() {
  const bills = await apiFetch('/api/bills');
  if (bills === null) return;
  allBills = bills;
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

function latestActionPerBill(actions) {
  const seen = new Set();
  return actions.filter(function(a) {
    if (seen.has(a.bill_id)) return false;
    seen.add(a.bill_id);
    return true;
  });
}

function renderActions() {
  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });

  const filterId = document.getElementById('bill-filter').value;
  let rows = filterId ? allActions.filter(function(a) { return a.bill_id === filterId; }) : allActions;

  if (collapsedView && !filterId) rows = latestActionPerBill(rows);

  document.getElementById('action-count').textContent =
    rows.length + (collapsedView && !filterId ? ' bill' : ' action') + (rows.length !== 1 ? 's' : '');

  const tbody = document.getElementById('actions-tbody');
  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  const clickable = collapsedView && !filterId;
  tbody.innerHTML = rows.map(function(a) {
    var billId = escapeHtml(a.bill_id);
    var rowAttrs = clickable
      ? ' class="bill-row" data-bill-id="' + billId + '" onclick="toggleExpand(\'' + billId + '\')"'
      : '';
    return '<tr' + rowAttrs + '>' +
      '<td>' + billId + '</td>' +
      '<td>' + escapeHtml(a.date) + '</td>' +
      '<td>' + chamberBadge(a.chamber) + '</td>' +
      '<td>' + escapeHtml(a.description) + '</td>' +
      '</tr>';
  }).join('');
}

function applyFilter() {
  renderActions();
}

function toggleExpand(billId) {
  const existing = document.querySelector('tr.expanded-row[data-expanded-for="' + billId + '"]');
  if (existing) {
    existing.remove();
    return;
  }

  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });

  const billRow = document.querySelector('tr.bill-row[data-bill-id="' + billId + '"]');
  if (!billRow) return;

  const bill = allBills.find(function(b) { return b.id === billId; });
  // allActions is newest-first; reverse for oldest-first chronological display
  const billActions = allActions
    .filter(function(a) { return a.bill_id === billId; })
    .slice()
    .reverse();

  var historyRows = billActions.length
    ? billActions.map(function(a) {
        return '<tr>' +
          '<td>' + escapeHtml(a.date) + '</td>' +
          '<td>' + chamberBadge(a.chamber) + '</td>' +
          '<td>' + escapeHtml(a.description) + '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="3" class="empty-state">No actions.</td></tr>';

  var currentNote = bill ? (bill.note || '') : '';
  var safeId = escapeHtml(billId);
  var noteHtml = '<div class="expanded-notes">' +
    '<h6>Notes</h6>' +
    '<textarea id="note-' + safeId + '">' + escapeHtml(currentNote) + '</textarea>' +
    '<button class="save-note-btn" onclick="saveNote(\'' + safeId + '\')">Save</button>' +
    '</div>';

  var expandedRow = document.createElement('tr');
  expandedRow.className = 'expanded-row';
  expandedRow.setAttribute('data-expanded-for', billId);
  expandedRow.innerHTML = '<td colspan="4"><div class="expanded-content">' +
    '<div class="expanded-history"><h6>Action History</h6>' +
    '<table><thead><tr><th>Date</th><th>Chamber</th><th>Action</th></tr></thead>' +
    '<tbody>' + historyRows + '</tbody></table></div>' +
    noteHtml +
    '</div></td>';

  billRow.insertAdjacentElement('afterend', expandedRow);
}

async function saveNote(billId) {
  // billId here is the HTML-escaped safeId from the onclick attribute.
  // For IL bill IDs (alphanumeric only, e.g. HB1288), escapeHtml is a no-op so this is safe.
  const textarea = document.getElementById('note-' + billId);
  if (!textarea) return;
  const note = textarea.value;
  const btn = textarea.nextElementSibling;

  if (btn) btn.setAttribute('aria-busy', 'true');
  try {
    const res = await fetch('/api/bills/' + encodeURIComponent(billId) + '/note', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note }),
    });

    if (res.status === 401) { window.location.href = '/login'; return; }

    if (res.ok) {
      const bill = allBills.find(function(b) { return b.id === billId; });
      if (bill) bill.note = note;
      showToast('Note saved', 'success');
    } else {
      showToast('Failed to save note', 'error');
    }
  } finally {
    if (btn) btn.removeAttribute('aria-busy');
  }
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

function chamberBadge(chamber) {
  return '<span class="chamber-badge">' + escapeHtml(chamber) + '</span>';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

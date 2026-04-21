let allActions = [];
let allBills   = [];
let activeFilter = '';

// ── Theme ──────────────────────────────────────────────────────
function toggleTheme() {
  var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('theme', next);
  renderThemeIcon();
}

function renderThemeIcon() {
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  var dark = document.documentElement.getAttribute('data-theme') === 'dark';
  btn.innerHTML = dark ? sunIcon() : moonIcon();
  btn.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
}

function sunIcon() {
  return '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">' +
    '<circle cx="8" cy="8" r="2.8"/>' +
    '<line x1="8" y1="1.2" x2="8" y2="2.6"/><line x1="8" y1="13.4" x2="8" y2="14.8"/>' +
    '<line x1="1.2" y1="8" x2="2.6" y2="8"/><line x1="13.4" y1="8" x2="14.8" y2="8"/>' +
    '<line x1="3.1" y1="3.1" x2="4.1" y2="4.1"/><line x1="11.9" y1="11.9" x2="12.9" y2="12.9"/>' +
    '<line x1="12.9" y1="3.1" x2="11.9" y2="4.1"/><line x1="4.1" y1="11.9" x2="3.1" y2="12.9"/>' +
    '</svg>';
}

function moonIcon() {
  return '<svg viewBox="0 0 16 16" fill="currentColor">' +
    '<path d="M13.5 10.5A6 6 0 0 1 5.5 2.5a.5.5 0 0 0-.6-.6A6.5 6.5 0 1 0 14.1 11a.5.5 0 0 0-.6-.5z"/>' +
    '</svg>';
}

// ── Init ───────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function() {
  renderThemeIcon();

  document.getElementById('meta-date').textContent = new Date().toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric'
  });

  document.getElementById('bill-list').addEventListener('click', function(e) {
    var btn = e.target.closest('.remove-btn');
    if (btn) removeBill(btn.dataset.billId);
  });

  await loadBills();
  loadActions();
});

// ── Data ───────────────────────────────────────────────────────
async function loadBills() {
  var bills = await apiFetch('/api/bills');
  if (bills === null) return;
  allBills = bills;
  updateMetaCount(bills.length);
  renderBills(bills);
}

async function loadActions() {
  var actions = await apiFetch('/api/actions');
  if (actions === null) return;
  allActions = actions.sort(function(a, b) { return parseDate(b.date) - parseDate(a.date); });
  renderBills(allBills);
  renderActions();
}

function updateMetaCount(n) {
  var el = document.getElementById('meta-count');
  if (el) el.textContent = n + ' bill' + (n !== 1 ? 's' : '') + ' tracked';
}

// ── Sidebar ────────────────────────────────────────────────────
function renderBills(bills) {
  var list = document.getElementById('bill-list');
  if (!list) return;

  if (bills.length === 0) {
    list.innerHTML = '<li style="padding:0.75rem 1.25rem;font-size:0.8rem;color:var(--text-3);font-style:italic">No bills tracked yet.</li>';
    return;
  }

  list.innerHTML = bills.map(function(b) {
    var id    = escapeHtml(b.id);
    var title = b.title ? escapeHtml(b.title) : '';
    var latest = allActions.find(function(a) { return a.bill_id === b.id; });
    var meta  = latest ? 'Latest: ' + formatDate(latest.date) : '';
    return '<li>' +
      '<button class="bill-item' + (b.id === activeFilter ? ' active' : '') + '" ' +
        'data-bill-id="' + id + '" onclick="setFilter(\'' + id + '\')">' +
        '<div class="bill-item-id">' +
          id +
          '<button class="remove-btn" data-bill-id="' + id + '" title="Remove ' + id + '" ' +
            'onclick="event.stopPropagation();removeBill(\'' + id + '\')">&times;</button>' +
        '</div>' +
        (title ? '<div class="bill-item-title">' + title + '</div>' : '') +
        (meta   ? '<div class="bill-item-meta">' + meta + '</div>' : '') +
      '</button>' +
    '</li>';
  }).join('');
}

function setFilter(billId) {
  activeFilter = billId;

  document.querySelectorAll('.bill-item').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.billId === billId);
  });
  var allBtn = document.getElementById('all-bills-btn');
  if (allBtn) allBtn.classList.toggle('active', !billId);

  var titleEl = document.getElementById('content-title');
  if (titleEl) {
    if (!billId) {
      titleEl.textContent = 'All Activity';
    } else {
      var bill = allBills.find(function(b) { return b.id === billId; });
      titleEl.textContent = billId + (bill && bill.title ? ' — ' + bill.title : '');
    }
  }

  renderActions();
}

// ── Table ──────────────────────────────────────────────────────
function latestActionPerBill(actions) {
  var seen = new Set();
  return actions.filter(function(a) {
    if (seen.has(a.bill_id)) return false;
    seen.add(a.bill_id);
    return true;
  });
}

function renderActions() {
  document.querySelectorAll('tr.expanded-row').forEach(function(r) { r.remove(); });
  document.querySelectorAll('tr.bill-row').forEach(function(r) { r.classList.remove('row-expanded'); });

  var rows = activeFilter
    ? allActions.filter(function(a) { return a.bill_id === activeFilter; })
    : allActions;

  var collapsed = !activeFilter;
  if (collapsed) rows = latestActionPerBill(rows);

  var count = rows.length;
  var countEl = document.getElementById('action-count');
  if (countEl) countEl.textContent = count + (collapsed ? ' bill' : ' action') + (count !== 1 ? 's' : '');

  var tbody = document.getElementById('actions-tbody');
  if (!tbody) return;

  if (rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No actions found.</td></tr>';
    return;
  }

  tbody.innerHTML = rows.map(function(a) {
    var id = escapeHtml(a.bill_id);
    var rowClass = collapsed
      ? ' class="bill-row" data-bill-id="' + id + '" onclick="toggleExpand(\'' + id + '\')"'
      : ' class="action-row"';
    return '<tr' + rowClass + '>' +
      '<td class="cell-bill">' + id + '</td>' +
      '<td class="cell-date">' + formatDate(a.date) + '</td>' +
      '<td class="cell-chamber">' + chamberBadge(a.chamber) + '</td>' +
      '<td class="cell-action">' + escapeHtml(a.description) + '</td>' +
    '</tr>';
  }).join('');
}

// ── Expand ─────────────────────────────────────────────────────
function toggleExpand(billId) {
  var existing = document.querySelector('tr.expanded-row[data-expanded-for="' + billId + '"]');
  if (existing) {
    collapseRow(existing, billId);
    return;
  }

  document.querySelectorAll('tr.expanded-row').forEach(function(r) {
    collapseRow(r, r.dataset.expandedFor);
  });

  var billRow = document.querySelector('tr.bill-row[data-bill-id="' + billId + '"]');
  if (!billRow) return;
  billRow.classList.add('row-expanded');

  var bill = allBills.find(function(b) { return b.id === billId; });
  var billActions = allActions.filter(function(a) { return a.bill_id === billId; }).slice().reverse();

  var histRows = billActions.length
    ? billActions.map(function(a) {
        return '<tr>' +
          '<td>' + formatDate(a.date) + '</td>' +
          '<td>' + chamberBadge(a.chamber) + '</td>' +
          '<td>' + escapeHtml(a.description) + '</td>' +
        '</tr>';
      }).join('')
    : '<tr><td colspan="3" style="padding:0.4rem 0.5rem;font-style:italic;color:var(--text-3)">No actions recorded.</td></tr>';

  var safeId = escapeHtml(billId);
  var currentNote = bill ? (bill.note || '') : '';
  var noteHtml = '<div class="expanded-notes-section">' +
    '<p class="expanded-section-label">Notes</p>' +
    '<textarea class="note-textarea" id="note-' + safeId + '">' + escapeHtml(currentNote) + '</textarea>' +
    '<button class="save-note-btn" onclick="saveNote(\'' + safeId + '\')">Save note</button>' +
  '</div>';

  var expandedRow = document.createElement('tr');
  expandedRow.className = 'expanded-row';
  expandedRow.dataset.expandedFor = billId;
  expandedRow.innerHTML =
    '<td colspan="4">' +
      '<div class="expanded-inner">' +
        '<div class="expanded-inner-wrap">' +
          '<div class="expanded-content">' +
            '<div class="expanded-history">' +
              '<p class="expanded-section-label">Full History — ' + escapeHtml(billId) + '</p>' +
              '<table><thead><tr><th>Date</th><th>Ch.</th><th>Action</th></tr></thead>' +
              '<tbody>' + histRows + '</tbody></table>' +
            '</div>' +
            noteHtml +
          '</div>' +
        '</div>' +
      '</div>' +
    '</td>';

  billRow.insertAdjacentElement('afterend', expandedRow);
  requestAnimationFrame(function() {
    var inner = expandedRow.querySelector('.expanded-inner');
    if (inner) inner.classList.add('open');
  });
}

function collapseRow(row, billId) {
  var inner = row.querySelector('.expanded-inner');
  if (inner) inner.classList.remove('open');
  var billRow = billId ? document.querySelector('tr.bill-row[data-bill-id="' + billId + '"]') : null;
  if (billRow) billRow.classList.remove('row-expanded');
  setTimeout(function() { if (row.parentNode) row.remove(); }, 290);
}

// ── Admin actions ──────────────────────────────────────────────
async function saveNote(billId) {
  var textarea = document.getElementById('note-' + billId);
  if (!textarea) return;
  var note = textarea.value;
  var btn  = textarea.nextElementSibling;

  if (btn) btn.setAttribute('aria-busy', 'true');
  try {
    var res = await fetch('/api/bills/' + encodeURIComponent(billId) + '/note', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ note: note }),
    });

    if (res.status === 401) { window.location.href = '/login'; return; }

    if (res.ok) {
      var bill = allBills.find(function(b) { return b.id === billId; });
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
  var input   = document.getElementById('add-bill-input');
  var errorEl = document.getElementById('add-error');
  var btn     = document.getElementById('add-bill-btn');
  var billId  = input.value.trim();
  if (!billId) return;

  errorEl.classList.add('hidden');
  btn.setAttribute('aria-busy', 'true');

  try {
    var res = await fetch('/api/bills', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bill_id: billId }),
    });

    if (res.status === 401) { window.location.href = '/login'; return; }

    if (res.ok) {
      input.value = '';
      activeFilter = '';
      await Promise.all([loadBills(), loadActions()]);
      var allBtn = document.getElementById('all-bills-btn');
      if (allBtn) allBtn.classList.add('active');
      showToast(billId.toUpperCase() + ' added', 'success');
    } else {
      var err = await res.json();
      errorEl.textContent = err.detail || 'Failed to add bill.';
      errorEl.classList.remove('hidden');
    }
  } finally {
    btn.removeAttribute('aria-busy');
  }
}

async function removeBill(billId) {
  if (!confirm('Remove ' + billId + ' from tracking? Its action history will also be deleted.')) return;

  var res = await fetch('/api/bills/' + billId, { method: 'DELETE' });
  if (res.status === 401) { window.location.href = '/login'; return; }

  if (res.ok) {
    if (activeFilter === billId) {
      activeFilter = '';
      var allBtn = document.getElementById('all-bills-btn');
      if (allBtn) allBtn.classList.add('active');
      var titleEl = document.getElementById('content-title');
      if (titleEl) titleEl.textContent = 'All Activity';
    }
    await Promise.all([loadBills(), loadActions()]);
    showToast(billId + ' removed', 'success');
  } else {
    showToast('Failed to remove ' + billId, 'error');
  }
}

async function fetchUpdates() {
  var btn = document.getElementById('fetch-btn');
  btn.setAttribute('aria-busy', 'true');
  btn.textContent = 'Fetching…';

  try {
    var res = await fetch('/api/fetch', { method: 'POST' });
    if (res.status === 401) { window.location.href = '/login'; return; }

    if (!res.ok) {
      var err = await res.json();
      var msg = res.status === 429
        ? (err.detail || 'OpenStates rate limit reached — try again tomorrow.')
        : (err.detail || 'Fetch failed.');
      showToast(msg, 'error');
      return;
    }

    var result = await res.json();
    await loadActions();

    showToast(
      result.new_actions + ' new action' + (result.new_actions !== 1 ? 's' : '') +
      ' across ' + result.updated + ' bill' + (result.updated !== 1 ? 's' : ''),
      'success'
    );

    if (result.errors && result.errors.length > 0) {
      showToast(
        'Could not fetch: ' + result.errors.map(function(e) { return e.bill_id + ' (' + e.error + ')'; }).join('; '),
        'error'
      );
    }

    var lastEl = document.getElementById('last-updated');
    if (lastEl) {
      lastEl.textContent = 'Updated ' + new Date().toLocaleString('en-US', {
        month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit'
      });
    }
  } finally {
    btn.removeAttribute('aria-busy');
    btn.textContent = 'Fetch Updates';
  }
}

// ── Utilities ──────────────────────────────────────────────────
async function apiFetch(url) {
  try {
    var res = await fetch(url);
    if (res.status === 401) { window.location.href = '/login'; return null; }
    if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
    return res.json();
  } catch (e) {
    showToast('Failed to load: ' + e.message, 'error');
    return null;
  }
}

var toastTimer;
function showToast(message, type) {
  type = type || 'success';
  var toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast ' + type;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function() { toast.classList.add('hidden'); }, 4000);
}

function parseDate(str) {
  if (!str) return 0;
  return new Date(str).getTime() || 0;
}

function formatDate(str) {
  if (!str) return '';
  var d = new Date(str + 'T12:00:00');
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function chamberBadge(chamber) {
  if (!chamber) return '';
  var c = String(chamber).toLowerCase();
  var key = (c.startsWith('h') || c.startsWith('l')) ? 'H' : 'S';
  return '<span class="chamber ch-' + key + '">' + key + '</span>';
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

let allActions = [];
let allBills = [];
let collapsedView = true;  // show one row per bill by default

document.addEventListener('DOMContentLoaded', async function() {
  await loadBills();
  loadActions();
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
    return '<li><span>' + escapeHtml(b.id) + '</span></li>';
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
      '<td>' + escapeHtml(a.chamber) + '</td>' +
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
          '<td>' + escapeHtml(a.chamber) + '</td>' +
          '<td>' + escapeHtml(a.description) + '</td>' +
          '</tr>';
      }).join('')
    : '<tr><td colspan="3" class="empty-state">No actions.</td></tr>';

  var noteHtml = '';
  if (bill && bill.note) {
    noteHtml = '<div class="expanded-notes">' +
      '<h6>Notes</h6>' +
      '<p class="note-text">' + escapeHtml(bill.note) + '</p>' +
      '</div>';
  }

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

async function apiFetch(url) {
  try {
    const res = await fetch(url);
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

let allActions = [];

document.addEventListener('DOMContentLoaded', function() {
  loadBills();
  loadActions();
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

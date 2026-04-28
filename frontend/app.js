// ============================================================
//  CareFlow — app.js
//  Roles:
//    admin        → patients, doctors, nurses, appointments,
//                   treatments, billing, reports, users, admins
//    receptionist → patients, doctors, nurses, appointments, billing
//    doctor       → My Appointments, My Patients, billing (filtered by linked_record_id)
//    nurse        → My Appointments, My Patients, billing (filtered by linked_record_id)
//    patient      → My Health Portal, billing (own records only)
// ============================================================

let token            = localStorage.getItem('token')            || null;
let role             = localStorage.getItem('role')             || null;
let currentUsername  = localStorage.getItem('username')         || null;
let linkedRecordId   = parseInt(localStorage.getItem('linked_record_id')) || null;

let cachedPatients = [];
let cachedDoctors  = [];
let cachedNurses   = [];

const API = {
  get:  url         => authFetch(url),
  post: (url, body) => authFetch(url, { method: 'POST',   body: JSON.stringify(body) }),
  put:  (url, body) => authFetch(url, { method: 'PUT',    body: JSON.stringify(body) }),
  del:  url         => authFetch(url, { method: 'DELETE' }),
};

function authFetch(url, opts = {}) {
  opts.headers = Object.assign({ 'Content-Type': 'application/json' }, opts.headers || {});
  if (token) opts.headers['Authorization'] = 'Bearer ' + token;
  return fetch(url, opts);
}

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show ' + type;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = 'toast'; }, 3500);
}

// ── Modal helpers ──────────────────────────────────────────
function openModal(id)  { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) e.target.style.display = 'none';
});

// ── Tab switching ──────────────────────────────────────────
function switchTab(btn, tabName) {
  document.querySelectorAll('.tab-panel').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('tab-' + tabName);
  if (panel) panel.style.display = 'block';
  if (btn)   btn.classList.add('active');
}

function switchAuthTab(tab) {
  document.querySelectorAll('.auth-tab').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.auth-form').forEach(f => f.style.display = 'none');
  document.getElementById(tab + '-form').style.display = 'flex';
  event.currentTarget.classList.add('active');
}

// ── Table helpers ──────────────────────────────────────────
function filterTable(tableId, query) {
  const q = query.toLowerCase();
  document.querySelectorAll('#' + tableId + ' tbody tr').forEach(tr => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  });
}

function statusBadge(status) {
  const map = {
    scheduled:  'badge-scheduled',
    requested:  'badge-scheduled',   // same colour — pending confirmation
    completed:  'badge-completed',
    canceled:   'badge-canceled',
    paid:       'badge-paid',
    pending:    'badge-pending',
    unpaid:     'badge-unpaid',
    partial:    'badge-partial',
  };
  const cls = map[(status || '').toLowerCase()] || '';
  return `<span class="badge ${cls}">${status || '—'}</span>`;
}

function buildTable(tableId, data, cols, actions) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const thead = table.querySelector('thead tr');
  const tbody = table.querySelector('tbody');
  thead.innerHTML = '';
  tbody.innerHTML = '';

  const colCount = cols.length + (actions ? 1 : 0);
  if (!data || !data.length) {
    cols.forEach(c => {
      const th = document.createElement('th'); th.textContent = c.label; thead.appendChild(th);
    });
    if (actions) {
      const th = document.createElement('th'); th.textContent = 'Actions'; thead.appendChild(th);
    }
    tbody.innerHTML = `<tr><td colspan="${colCount}" class="empty-state">No records found.</td></tr>`;
    return;
  }

  cols.forEach(c => {
    const th = document.createElement('th'); th.textContent = c.label; thead.appendChild(th);
  });
  if (actions) {
    const th = document.createElement('th'); th.textContent = 'Actions'; thead.appendChild(th);
  }

  data.forEach(row => {
    const tr = document.createElement('tr');
    cols.forEach(c => {
      const td = document.createElement('td');
      td.innerHTML = c.render ? c.render(row[c.key], row) : (row[c.key] ?? '—');
      tr.appendChild(td);
    });
    if (actions) {
      const td = document.createElement('td');
      td.className = 'table-actions';
      td.innerHTML = actions(row);
      tr.appendChild(td);
    }
    tbody.appendChild(tr);
  });
}

// ── Dropdowns ──────────────────────────────────────────────
function populateSelect(selectId, items, valueFn, labelFn, placeholder) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = placeholder ? `<option value="" disabled selected>${placeholder}</option>` : '';
  items.forEach(item => {
    const opt = document.createElement('option');
    opt.value       = valueFn(item);
    opt.textContent = labelFn(item);
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

function populateAllDropdowns() {
  const patLabel = p => `${p.FirstName} ${p.LastName}`;
  const docLabel = d => `Dr. ${d.FirstName} ${d.LastName}${d.Specialty ? ' — ' + d.Specialty : ''}`;
  const nurLabel = n => `${n.FirstName} ${n.LastName} (${n.Certification || ''})`;

  ['appt-patient-select', 'edit-appt-patient-select'].forEach(id =>
    populateSelect(id, cachedPatients, p => p.PatientID, patLabel, 'Select patient…'));
  ['appt-doctor-select', 'edit-appt-doctor-select'].forEach(id =>
    populateSelect(id, cachedDoctors, d => d.DoctorID, docLabel, 'Select doctor…'));
  ['appt-nurse-select', 'edit-appt-nurse-select'].forEach(id =>
    populateSelect(id, cachedNurses, n => n.NurseID, nurLabel, 'Select nurse…'));

  // Patient portal doctor dropdown
  const pp = document.getElementById('portal-doctor-select');
  if (pp) {
    const prev = pp.value;
    pp.innerHTML = '<option value="" disabled selected>Choose a doctor…</option>';
    cachedDoctors.forEach(d => {
      const o = document.createElement('option');
      o.value = d.DoctorID;
      o.textContent = `Dr. ${d.FirstName} ${d.LastName}${d.Specialty ? ' — ' + d.Specialty : ''}`;
      pp.appendChild(o);
    });
    if (prev) pp.value = prev;
  }
}

// ── Session ────────────────────────────────────────────────
function startSession(data) {
  token           = data.token;
  role            = data.role || 'patient';
  currentUsername = data.username || '';
  linkedRecordId  = data.linked_record_id ? parseInt(data.linked_record_id) : null;

  localStorage.setItem('token',            token);
  localStorage.setItem('role',             role);
  localStorage.setItem('username',         currentUsername);
  localStorage.setItem('linked_record_id', linkedRecordId ?? '');

  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('app').style.display         = 'flex';

  document.getElementById('user-avatar').textContent     = (currentUsername[0] || '?').toUpperCase();
  document.getElementById('user-info').textContent       = currentUsername;
  document.getElementById('user-role-badge').textContent = role;

  buildNavForRole(role);
  loadDataForRole(role);
}

function endSession() {
  token = null; role = null; currentUsername = null; linkedRecordId = null;
  localStorage.clear();
  document.getElementById('auth-screen').style.display = 'flex';
  document.getElementById('app').style.display         = 'none';
}

// ── Nav ────────────────────────────────────────────────────
function buildNavForRole(r) {
  const showTabs = ids => ids.forEach(id => {
    const el = document.querySelector(`[data-tab="${id}"]`);
    if (el) el.style.display = 'flex';
  });
  const hideTabs = ids => ids.forEach(id => {
    const el = document.querySelector(`[data-tab="${id}"]`);
    if (el) el.style.display = 'none';
  });

  document.querySelectorAll('.admin-only').forEach(el =>
    el.style.display = (r === 'admin') ? '' : 'none');

  hideTabs(['patients','doctors','nurses','appointments','treatments',
            'users','admins','my-appointments','my-patients','portal','billing','reports']);

  if (r === 'admin') {
    showTabs(['patients','doctors','nurses','appointments','treatments',
              'billing','reports','users','admins']);
    setTimeout(() => switchTab(document.querySelector('[data-tab="patients"]'), 'patients'), 0);
  } else if (r === 'receptionist') {
    showTabs(['patients','doctors','nurses','appointments','billing']);
    setTimeout(() => switchTab(document.querySelector('[data-tab="patients"]'), 'patients'), 0);
  } else if (r === 'doctor' || r === 'nurse') {
    showTabs(['my-appointments','my-patients','billing']);
    setTimeout(() => switchTab(document.querySelector('[data-tab="my-appointments"]'), 'my-appointments'), 0);
  } else {
    showTabs(['portal','billing']);
    setTimeout(() => switchTab(document.querySelector('[data-tab="portal"]'), 'portal'), 0);
  }
}

// ── Data loaders ───────────────────────────────────────────
async function loadDataForRole(r) {
  if (r === 'admin' || r === 'receptionist') {
    await Promise.all([loadPatients(), loadDoctors(), loadNurses()]);
    await loadAppointments();
    await loadBilling();
    if (r === 'admin') { loadUsers(); loadAdmins(); loadTreatments(); loadReports(); }
  } else if (r === 'doctor' || r === 'nurse') {
    await Promise.all([loadMyAppointments(), loadMyPatients()]);
    await loadBilling();
  } else {
    // patient — load doctors/nurses for portal dropdown, then appointments & billing
    await Promise.all([loadDoctors(), loadNurses()]);
    await loadPortalAppointments();
    await loadBilling();
  }
}

// ══════════════════════════════════════════════════════════
//  ADMIN / RECEPTIONIST LOADERS
// ══════════════════════════════════════════════════════════

async function loadPatients() {
  const res = await API.get('/api/patients');
  if (!res.ok) return;
  cachedPatients = await res.json();
  populateAllDropdowns();

  const provMap  = { 1:'BlueCross', 2:'Aetna', 3:'Medicare', 4:'Cigna', 5:'UnitedHealth' };
  const canEdit  = (role === 'admin' || role === 'receptionist');
  buildTable('patients-table', cachedPatients, [
    { key:'PatientID',  label:'ID' },
    { key:'FirstName',  label:'First Name' },
    { key:'LastName',   label:'Last Name' },
    { key:'DOB',        label:'Date of Birth' },
    { key:'Gender',     label:'Gender' },
    { key:'Phone',      label:'Phone' },
    { key:'Address',    label:'Address' },
    { key:'ProviderID', label:'Insurance', render: v => provMap[v] || v },
  ], canEdit ? row => `
    <button class="btn-icon btn-edit"   onclick="openEditPatient(${JSON.stringify(row).replace(/"/g,'&quot;')})">✏️ Edit</button>
    <button class="btn-icon btn-delete" onclick="deletePatient(${row.PatientID})">🗑️ Delete</button>
  ` : null);
}

async function loadDoctors() {
  const res = await API.get('/api/doctors');
  if (!res.ok) return;
  cachedDoctors = await res.json();
  populateAllDropdowns();

  const deptMap = { 1:'Cardiology', 2:'Pediatrics', 3:'Emergency', 4:'Oncology', 5:'Neurology' };
  buildTable('doctors-table', cachedDoctors, [
    { key:'DoctorID',     label:'ID' },
    { key:'FirstName',    label:'First Name' },
    { key:'LastName',     label:'Last Name' },
    { key:'Specialty',    label:'Specialty' },
    { key:'Phone',        label:'Phone' },
    { key:'DepartmentID', label:'Department', render: v => deptMap[v] || v },
  ], role === 'admin' ? row => `
    <button class="btn-icon btn-delete" onclick="deleteDoctor(${row.DoctorID})">🗑️ Delete</button>
  ` : null);
}

async function loadNurses() {
  const res = await API.get('/api/nurses');
  if (!res.ok) return;
  cachedNurses = await res.json();
  populateAllDropdowns();

  const deptMap = { 1:'Cardiology', 2:'Pediatrics', 3:'Emergency', 4:'Oncology', 5:'Neurology' };
  buildTable('nurses-table', cachedNurses, [
    { key:'NurseID',       label:'ID' },
    { key:'FirstName',     label:'First Name' },
    { key:'LastName',      label:'Last Name' },
    { key:'Certification', label:'Certification' },
    { key:'Phone',         label:'Phone' },
    { key:'DepartmentID',  label:'Department', render: v => deptMap[v] || v },
  ], null);
}

async function loadAppointments() {
  const res = await API.get('/api/appointments');
  if (!res.ok) return;
  const data = await res.json();

  buildTable('appts-table', data, [
    { key:'AppointmentID',   label:'ID' },
    { key:'PatientID',       label:'Patient',  render: id => patientName(id) },
    { key:'DoctorID',        label:'Doctor',   render: id => doctorName(id) },
    { key:'NurseID',         label:'Nurse',    render: id => nurseName(id) },
    { key:'AppointmentDate', label:'Date' },
    { key:'AppointmentTime', label:'Time',     render: v => (v || '').substring(0, 5) },
    { key:'Status',          label:'Status',   render: v => statusBadge(v) },
    { key:'Purpose',         label:'Purpose' },
  ], row => {
    const approveBtn = row.Status === 'Requested'
      ? `<button class="btn-icon btn-primary" onclick="approveAppointment(${JSON.stringify(row).replace(/"/g,'&quot;')})">✔ Approve</button>`
      : '';
    return `
      ${approveBtn}
      <button class="btn-icon btn-edit"   onclick="openEditAppt(${JSON.stringify(row).replace(/"/g,'&quot;')})">✏️ Edit</button>
      <button class="btn-icon btn-delete" onclick="deleteAppointment(${row.AppointmentID})">🗑️ Delete</button>
    `;
  });
}

async function approveAppointment(row) {
  const updated = Object.assign({}, row, { Status: 'Scheduled' });
  const res = await API.put(`/api/appointments/${row.AppointmentID}`, updated);
  if (res.ok) { toast('Appointment approved'); loadAppointments(); }
  else { const e = await res.json(); toast(e.error || 'Failed to approve', 'error'); }
}

// ── Treatments ─────────────────────────────────────────────
async function loadTreatments(apptId) {
  const url = apptId ? `/api/treatments?appointment_id=${apptId}` : '/api/treatments';
  const res = await API.get(url);
  if (!res.ok) return;
  const data = await res.json();

  buildTable('treatments-table', data, [
    { key:'TreatmentID',   label:'ID' },
    { key:'AppointmentID', label:'Appt ID' },
    { key:'DiagnosisName', label:'Diagnosis' },
    { key:'TreatmentName', label:'Treatment' },
    { key:'Description',   label:'Description' },
    { key:'TreatmentCost', label:'Cost', render: fmt$ },
  ], role === 'admin' ? row => `
    <button class="btn-icon btn-delete" onclick="deleteTreatment(${row.TreatmentID})">🗑️ Delete</button>
  ` : null);
}

async function deleteTreatment(id) {
  if (!confirm('Delete this treatment? Billing will update automatically.')) return;
  const res = await API.del(`/api/treatments/${id}`);
  if (res.ok) { toast('Treatment deleted; billing updated'); loadTreatments(); loadBilling(); }
  else { const e = await res.json(); toast(e.error || 'Delete failed', 'error'); }
}

// ── Users & Admins ─────────────────────────────────────────
async function loadUsers() {
  const res = await API.get('/api/users');
  if (!res.ok) return;
  const data = await res.json();
  buildTable('users-table', data, [
    { key:'id',               label:'ID' },
    { key:'username',         label:'Username' },
    { key:'full_name',        label:'Full Name' },
    { key:'role',             label:'Role' },
    { key:'linked_record_id', label:'Linked Record ID' },
  ], row => `
    <button class="btn-icon btn-edit"   onclick="adminChangeRole(${row.id},'${row.role}')">🔑 Role</button>
    <button class="btn-icon btn-edit"   onclick="adminResetPw(${row.id})">🔒 Password</button>
    <button class="btn-icon btn-delete" onclick="adminDeleteUser(${row.id})">🗑️ Delete</button>
  `);
}

async function loadAdmins() {
  const res = await API.get('/api/admins');
  if (!res.ok) return;
  const data = await res.json();
  buildTable('admins-table', data, [
    { key:'AdminID',   label:'ID' },
    { key:'FirstName', label:'First Name' },
    { key:'LastName',  label:'Last Name' },
    { key:'Email',     label:'Email' },
    { key:'Role',      label:'Role' },
  ], row => `
    <button class="btn-icon btn-delete" onclick="deleteAdmin(${row.AdminID})">🗑️ Delete</button>
  `);
}

// ── Name helpers ───────────────────────────────────────────
function patientName(id) {
  const p = cachedPatients.find(p => p.PatientID == id);
  return p ? `${p.FirstName} ${p.LastName}` : `#${id}`;
}
function doctorName(id) {
  const d = cachedDoctors.find(d => d.DoctorID == id);
  return d ? `Dr. ${d.LastName}` : (id ? `#${id}` : '—');
}
function nurseName(id) {
  const n = cachedNurses.find(n => n.NurseID == id);
  return n ? `${n.FirstName} ${n.LastName}` : (id ? `#${id}` : '—');
}

// ══════════════════════════════════════════════════════════
//  DOCTOR / NURSE VIEWS  (filter by linked_record_id from JWT)
// ══════════════════════════════════════════════════════════

async function loadMyAppointments() {
  // Server already filters by linked_record_id in the JWT
  const [apptRes, patRes, docRes, nurRes] = await Promise.all([
    API.get('/api/appointments'),
    API.get('/api/patients'),
    API.get('/api/doctors'),
    API.get('/api/nurses'),
  ]);
  if (!apptRes.ok) return;

  cachedPatients = patRes.ok  ? await patRes.json()  : [];
  cachedDoctors  = docRes.ok  ? await docRes.json()  : [];
  cachedNurses   = nurRes.ok  ? await nurRes.json()  : [];

  const filtered = await apptRes.json();  // already scoped by server

  const cols = [
    { key:'AppointmentDate', label:'Date' },
    { key:'AppointmentTime', label:'Time',    render: v => (v || '').substring(0, 5) },
    { key:'PatientID',       label:'Patient', render: id => patientName(id) },
    { key:'Status',          label:'Status',  render: v => statusBadge(v) },
    { key:'Purpose',         label:'Purpose / Reason' },
  ];
  if (role === 'doctor')
    cols.push({ key:'NurseID', label:'Assigned Nurse', render: id => nurseName(id) });

  buildTable('my-appts-table', filtered, cols, null);
}

async function loadMyPatients() {
  const [apptRes, patRes, docRes, nurRes] = await Promise.all([
    API.get('/api/appointments'),
    API.get('/api/patients'),
    API.get('/api/doctors'),
    API.get('/api/nurses'),
  ]);
  if (!apptRes.ok || !patRes.ok) return;

  cachedPatients = await patRes.json();
  cachedDoctors  = docRes.ok ? await docRes.json() : cachedDoctors;
  cachedNurses   = nurRes.ok ? await nurRes.json() : cachedNurses;

  const myAppts = await apptRes.json(); // already filtered by server

  const myPids = new Set(myAppts.map(a => a.PatientID));
  buildTable('my-patients-table',
    cachedPatients.filter(p => myPids.has(p.PatientID)), [
      { key:'FirstName', label:'First Name' },
      { key:'LastName',  label:'Last Name' },
      { key:'DOB',       label:'Date of Birth' },
      { key:'Gender',    label:'Gender' },
      { key:'Phone',     label:'Phone' },
    ], null);
}

// ══════════════════════════════════════════════════════════
//  PATIENT PORTAL
// ══════════════════════════════════════════════════════════

async function loadPortalAppointments() {
  // Server filters by patient_record_id — no client-side matching needed
  const res = await API.get('/api/appointments');
  if (!res.ok) return;
  const mine = await res.json();

  buildTable('portal-appts-table', mine, [
    { key:'AppointmentDate', label:'Date' },
    { key:'AppointmentTime', label:'Time',    render: v => (v || '').substring(0, 5) },
    { key:'DoctorID',        label:'Doctor',  render: id => doctorName(id) },
    { key:'Status',          label:'Status',  render: v => statusBadge(v) },
    { key:'Purpose',         label:'Reason for Visit' },
  ], row => {
    const cancellable = row.Status === 'Requested' || row.Status === 'Scheduled';
    return cancellable
      ? `<button class="btn-icon btn-delete" onclick="cancelPortalAppointment(${row.AppointmentID})">✕ Cancel</button>`
      : '';
  });
}

async function cancelPortalAppointment(id) {
  if (!confirm('Cancel this appointment?')) return;
  const res = await API.put(`/api/appointments/${id}`, { Status: 'Canceled' });
  if (res.ok) { toast('Appointment canceled'); loadPortalAppointments(); }
  else toast('Could not cancel appointment', 'error');
}

// ══════════════════════════════════════════════════════════
//  BILLING
// ══════════════════════════════════════════════════════════

async function loadBilling() {
  const res = await API.get('/api/billing');
  if (!res.ok) return;
  const records = await res.json();

  const cols = [
    { key:'BillingID',         label:'ID' },
    { key:'PatientID',         label:'Patient',
      render: (id, row) => row.FirstName ? `${row.FirstName} ${row.LastName || ''}` : id },
    { key:'AppointmentID',     label:'Appt' },
    { key:'BillingDate',       label:'Date' },
    { key:'TotalCost',         label:'Total Cost',     render: fmt$ },
    { key:'InsuranceCoverage', label:'Insurance Paid', render: fmt$ },
    { key:'AmountOwed',        label:'Patient Owes',   render: fmt$ },
    { key:'AmountPaid',        label:'Patient Paid',   render: fmt$ },
    { key:'BalanceDue',        label:'Balance Due',
      render: v => `<span style="color:${v > 0 ? '#ef4444' : '#10b981'}">${fmt$(v)}</span>` },
    { key:'PaymentStatus',     label:'Status',         render: s => statusBadge(s) },
    { key:'PaymentMethod',     label:'Method' },
  ];

  const actions = row => {
    if (row.PaymentStatus === 'Canceled') return '—';
    if (role === 'patient') {
      return row.BalanceDue > 0
        ? `<button class="btn-icon btn-primary" onclick="openPayModal(${JSON.stringify(row).replace(/"/g,'&quot;')})">💳 Pay</button>`
        : '<span class="badge badge-paid">Paid ✓</span>';
    }
    if (role === 'admin') {
      return `
        <button class="btn-icon btn-edit" onclick="openPayModal(${JSON.stringify(row).replace(/"/g,'&quot;')})">💳 Pay</button>
        <select onchange="adminUpdateBillingStatus(${row.BillingID}, this.value)" style="font-size:.8rem;padding:4px 6px;border-radius:6px">
          <option value="">Status…</option>
          <option value="Paid">Mark Paid</option>
          <option value="Partial">Mark Partial</option>
          <option value="Unpaid">Mark Unpaid</option>
          <option value="Canceled">Mark Canceled</option>
        </select>`;
    }
    return '—';
  };

  buildTable('billing-table', records, cols, actions);
}

let _billingRowForPay = null;

function openPayModal(row) {
  _billingRowForPay = row;
  const balanceDue  = row.BalanceDue ?? (row.AmountOwed - row.AmountPaid);
  document.getElementById('pay-billing-id').textContent  = row.BillingID;
  document.getElementById('pay-balance-due').textContent = fmt$(balanceDue);
  document.getElementById('pay-amount-input').value      = balanceDue > 0 ? balanceDue.toFixed(2) : '0.00';
  document.getElementById('pay-method-select').value     = row.PaymentMethod || 'Card';
  openModal('pay-billing-modal');
}

document.getElementById('pay-billing-form').addEventListener('submit', async e => {
  e.preventDefault();
  if (!_billingRowForPay) return;
  const newPayment  = parseFloat(document.getElementById('pay-amount-input').value) || 0;
  const payMethod   = document.getElementById('pay-method-select').value;
  const currentPaid = parseFloat(_billingRowForPay.AmountPaid || 0);
  const res = await API.put(`/api/billing/${_billingRowForPay.BillingID}`, {
    AmountPaid:    currentPaid + newPayment,
    PaymentMethod: payMethod,
  });
  if (res.ok) {
    closeModal('pay-billing-modal');
    toast('Payment recorded!');
    loadBilling();
    if (role === 'admin') loadReports();
  } else {
    const err = await res.json();
    toast(err.error || 'Payment failed', 'error');
  }
});

async function adminUpdateBillingStatus(billingId, status) {
  if (!status) return;
  const res = await API.put(`/api/billing/${billingId}`, { PaymentStatus: status });
  if (res.ok) { toast('Billing status updated'); loadBilling(); }
  else { const e = await res.json(); toast(e.error || 'Update failed', 'error'); }
}

// ══════════════════════════════════════════════════════════
//  CRUD — Patients
// ══════════════════════════════════════════════════════════

document.getElementById('patient-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/patients', obj);
  if (res.ok) { closeModal('add-patient-modal'); e.target.reset(); toast('Patient registered'); loadPatients(); }
  else { const err = await res.json(); toast(err.error || 'Failed to add patient', 'error'); }
});

function openEditPatient(row) {
  const form = document.getElementById('edit-patient-form');
  Object.keys(row).forEach(k => { const el = form.elements[k]; if (el) el.value = row[k] || ''; });
  openModal('edit-patient-modal');
}

document.getElementById('edit-patient-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.put(`/api/patients/${obj.PatientID}`, obj);
  if (res.ok) { closeModal('edit-patient-modal'); toast('Patient updated'); loadPatients(); }
  else { const err = await res.json(); toast(err.error || 'Update failed', 'error'); }
});

async function deletePatient(id) {
  if (!confirm('Delete this patient record?')) return;
  const res = await API.del(`/api/patients/${id}`);
  if (res.ok) { toast('Patient deleted'); loadPatients(); }
  else toast('Delete failed', 'error');
}

// ══════════════════════════════════════════════════════════
//  CRUD — Doctors
// ══════════════════════════════════════════════════════════

document.getElementById('doctor-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/doctors', obj);
  if (res.ok) { closeModal('add-doctor-modal'); e.target.reset(); toast('Doctor added'); loadDoctors(); }
  else { const err = await res.json(); toast(err.error || 'Failed to add doctor', 'error'); }
});

async function deleteDoctor(id) {
  if (!confirm('Remove this doctor record?')) return;
  const res = await API.del(`/api/doctors/${id}`);
  if (res.ok) { toast('Doctor removed'); loadDoctors(); }
  else toast('Delete failed', 'error');
}

// ══════════════════════════════════════════════════════════
//  CRUD — Appointments
// ══════════════════════════════════════════════════════════

document.getElementById('appt-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  // AppointmentID is auto-generated server-side; remove if empty
  delete obj.AppointmentID;
  const res = await API.post('/api/appointments', obj);
  if (res.ok) { closeModal('add-appt-modal'); e.target.reset(); toast('Appointment scheduled'); loadAppointments(); }
  else { const err = await res.json(); toast(err.error || 'Failed to schedule', 'error'); }
});

function openEditAppt(row) {
  const form = document.getElementById('edit-appt-form');
  populateAllDropdowns();
  Object.keys(row).forEach(k => { const el = form.elements[k]; if (el) el.value = row[k] || ''; });
  openModal('edit-appt-modal');
}

document.getElementById('edit-appt-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.put(`/api/appointments/${obj.AppointmentID}`, obj);
  if (res.ok) { closeModal('edit-appt-modal'); toast('Appointment updated'); loadAppointments(); }
  else { const err = await res.json(); toast(err.error || 'Update failed', 'error'); }
});

async function deleteAppointment(id) {
  if (!confirm('Delete this appointment?')) return;
  const res = await API.del(`/api/appointments/${id}`);
  if (res.ok) { toast('Appointment deleted'); loadAppointments(); }
  else toast('Delete failed', 'error');
}

// ══════════════════════════════════════════════════════════
//  PATIENT PORTAL — appointment request form
// ══════════════════════════════════════════════════════════

const portalForm = document.getElementById('portal-appt-form');
if (portalForm) {
  portalForm.addEventListener('submit', async e => {
    e.preventDefault();
    const obj = Object.fromEntries(new FormData(e.target).entries());

    // Resolve PatientID from server (linked_record_id / patients/me)
    const meRes = await API.get('/api/patients/me');
    if (!meRes.ok) {
      toast('Could not find your patient record. Please contact reception.', 'error');
      return;
    }
    const me = await meRes.json();
    if (!me || !me.PatientID) {
      toast('Patient record not found. Please contact reception.', 'error');
      return;
    }
    obj.PatientID = me.PatientID;
    obj.Status    = 'Requested';

    // Auto-assign a nurse from the chosen doctor's department
    const doc   = cachedDoctors.find(d => d.DoctorID == obj.DoctorID);
    const nurse = doc
      ? cachedNurses.find(n => n.DepartmentID == doc.DepartmentID) || cachedNurses[0]
      : cachedNurses[0];
    obj.NurseID = nurse ? nurse.NurseID : null;

    const res = await API.post('/api/appointments', obj);
    if (res.ok) {
      closeModal('portal-appt-modal');
      e.target.reset();
      toast('Appointment requested! Reception will confirm shortly.');
      loadPortalAppointments();
    } else {
      const err = await res.json();
      toast(err.error || 'Could not book appointment', 'error');
    }
  });
}

// ══════════════════════════════════════════════════════════
//  CRUD — Treatments
// ══════════════════════════════════════════════════════════

document.getElementById('treatment-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  obj.TreatmentCost = parseFloat(obj.TreatmentCost) || 0;
  const res = await API.post('/api/treatments', obj);
  if (res.ok) {
    closeModal('add-treatment-modal');
    e.target.reset();
    toast('Treatment added; billing updated automatically');
    loadTreatments();
    loadBilling();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed to add treatment', 'error');
  }
});

// ══════════════════════════════════════════════════════════
//  CRUD — Hospital Admins
// ══════════════════════════════════════════════════════════

document.getElementById('admin-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/admins', obj);
  if (res.ok) { closeModal('add-admin-modal'); e.target.reset(); toast('Admin record added'); loadAdmins(); }
  else { const err = await res.json(); toast(err.error || 'Failed', 'error'); }
});

async function deleteAdmin(id) {
  if (!confirm('Delete this admin record?')) return;
  const res = await API.del(`/api/admins/${id}`);
  if (res.ok) { toast('Deleted'); loadAdmins(); }
  else toast('Delete failed', 'error');
}

// ══════════════════════════════════════════════════════════
//  CRUD — System Users
// ══════════════════════════════════════════════════════════

document.getElementById('create-user-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/users', obj);
  if (res.ok) {
    closeModal('add-user-modal');
    e.target.reset();
    toast('User created');
    loadUsers();
    // Refresh doctor/nurse lists if a staff account was created
    if (obj.role === 'doctor') loadDoctors();
    if (obj.role === 'nurse')  loadNurses();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed to create user', 'error');
  }
});

async function adminChangeRole(userId, currentRole) {
  const roles   = ALLOWED_ROLES_CLIENT;
  const newRole = prompt(`Change role (${roles.join(', ')}):`, currentRole);
  if (!newRole || !roles.includes(newRole.trim())) return;
  const res = await API.put(`/api/users/${userId}/role`, { role: newRole.trim() });
  if (res.ok) { toast('Role updated'); loadUsers(); }
  else { const e = await res.json(); toast(e.error || 'Failed', 'error'); }
}
const ALLOWED_ROLES_CLIENT = ['admin', 'doctor', 'nurse', 'receptionist', 'patient'];

async function adminResetPw(userId) {
  const pw = prompt('Enter new password:');
  if (!pw) return;
  const res = await API.put(`/api/users/${userId}/password`, { new_password: pw });
  if (res.ok) toast('Password updated');
  else { const e = await res.json(); toast(e.error || 'Failed', 'error'); }
}

async function adminDeleteUser(userId) {
  if (!confirm('Delete this user account?')) return;
  const res = await API.del(`/api/users/${userId}`);
  if (res.ok) { toast('User deleted'); loadUsers(); }
  else { const e = await res.json(); toast(e.error || 'Failed', 'error'); }
}

// ══════════════════════════════════════════════════════════
//  AUTH FORMS
// ══════════════════════════════════════════════════════════

document.getElementById('login-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch('/api/login', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(obj),
  });
  if (res.ok) { const data = await res.json(); startSession(data); }
  else toast('Invalid username or password', 'error');
});

document.getElementById('register-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch('/api/register', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(obj),
  });
  if (res.ok) {
    toast('Account created — you can now sign in');
    switchAuthTab('login');
    e.target.reset();
  } else {
    const err = await res.json();
    toast(err.error || 'Registration failed', 'error');
  }
});

document.getElementById('logout-btn').addEventListener('click', endSession);

document.getElementById('change-password-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.put('/api/users/me/password', obj);
  if (res.ok) { closeModal('change-password-modal'); e.target.reset(); toast('Password updated'); }
  else { const err = await res.json(); toast(err.error || 'Failed', 'error'); }
});

function openPasswordModal() { openModal('change-password-modal'); }

// ══════════════════════════════════════════════════════════
//  INIT — resume session from localStorage
// ══════════════════════════════════════════════════════════
if (token && role) {
  startSession({ token, role, username: currentUsername, linked_record_id: linkedRecordId });
}

// ══════════════════════════════════════════════════════════
//  FORMATTERS
// ══════════════════════════════════════════════════════════
function fmt$(n)   { return n == null ? '—' : '$' + Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
function fmtPct(n) { return n == null ? '—' : (Number(n) * 100).toFixed(1) + '%'; }
function fmtN(n)   { return n == null ? '—' : Number(n).toLocaleString('en-US'); }

function renderBarChart(containerId, items, colorClass, prefix) {
  const wrap = document.getElementById(containerId);
  if (!wrap) return;
  const max = Math.max(...items.map(i => i.value || 0), 1);
  wrap.innerHTML = `<div class="bar-chart-wrap">${
    items.map(i => {
      const pct   = Math.max(4, Math.round(((i.value || 0) / max) * 100));
      const label = prefix === '$' ? fmt$(i.value) : fmtN(i.value);
      return `<div class="bar-row">
        <div class="bar-label" title="${i.label}">${i.label}</div>
        <div class="bar-track">
          <div class="bar-fill ${colorClass}" style="width:${pct}%">${label}</div>
        </div>
      </div>`;
    }).join('')
  }</div>`;
}

// ══════════════════════════════════════════════════════════
//  REPORTS
// ══════════════════════════════════════════════════════════

async function loadReports() {
  const res = await API.get('/api/reports');
  if (!res.ok) { toast('Failed to load reports', 'error'); return; }
  const data = await res.json();

  const summary  = (data.billing_summary || [{}])[0] || {};
  const billing  = data.billing_by_status  || [];
  const totalDocs = (data.doctor_workload  || []).length;

  document.getElementById('report-kpis').innerHTML = `
    <div class="kpi-card">
      <div class="kpi-label">Total Billed</div>
      <div class="kpi-value">${fmt$(summary.TotalBilled)}</div>
      <div class="kpi-sub">${fmtN(summary.TotalBillings)} claims</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Insurance Covered</div>
      <div class="kpi-value">${fmt$(summary.TotalInsuranceCoverage)}</div>
      <div class="kpi-sub">${summary.TotalBilled ? Math.round((summary.TotalInsuranceCoverage / summary.TotalBilled) * 100) : 0}% of total</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Patient Owed</div>
      <div class="kpi-value">${fmt$(summary.TotalOwed)}</div>
      <div class="kpi-sub">after insurance</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Collected</div>
      <div class="kpi-value">${fmt$(summary.TotalCollected)}</div>
      <div class="kpi-sub">patient payments</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Outstanding</div>
      <div class="kpi-value" style="color:#ef4444">${fmt$(summary.OutstandingBalance)}</div>
      <div class="kpi-sub">unpaid balance</div>
    </div>
    <div class="kpi-card">
      <div class="kpi-label">Active Doctors</div>
      <div class="kpi-value">${fmtN(totalDocs)}</div>
      <div class="kpi-sub">on staff</div>
    </div>
  `;

  buildTable('report-billing-table', billing, [
    { key:'PaymentStatus',      label:'Status' },
    { key:'TotalRecords',       label:'COUNT' },
    { key:'TotalBilled',        label:'SUM Billed',    render: fmt$ },
    { key:'TotalCovered',       label:'SUM Insurance', render: fmt$ },
    { key:'TotalOwed',          label:'SUM Owed',      render: fmt$ },
    { key:'TotalCollected',     label:'SUM Collected', render: fmt$ },
    { key:'OutstandingBalance', label:'Outstanding',
      render: v => `<span style="color:${v > 0 ? '#ef4444' : '#10b981'}">${fmt$(v)}</span>` },
    { key:'AvgCost', label:'AVG Cost', render: fmt$ },
    { key:'MinCost', label:'MIN Cost', render: fmt$ },
    { key:'MaxCost', label:'MAX Cost', render: fmt$ },
  ], null);
  renderBarChart('report-billing-chart', billing.map(r => ({ label: r.PaymentStatus, value: r.TotalBilled })), 'c1', '$');

  const apptDept = data.appointments_by_dept || [];
  buildTable('report-appts-table', apptDept, [
    { key:'DepartmentName',    label:'Department' },
    { key:'TotalAppointments', label:'COUNT Total' },
    { key:'Completed',         label:'SUM Completed' },
    { key:'Scheduled',         label:'SUM Scheduled/Requested' },
    { key:'Canceled',          label:'SUM Canceled' },
    { key:'EarliestAppt',      label:'MIN Date' },
    { key:'LatestAppt',        label:'MAX Date' },
  ], null);
  renderBarChart('report-appts-chart', apptDept.map(r => ({ label: r.DepartmentName, value: r.TotalAppointments })), 'c2', '');

  const treatDept = data.treatment_by_dept || [];
  buildTable('report-treatment-table', treatDept, [
    { key:'DepartmentName',  label:'Department' },
    { key:'TotalTreatments', label:'COUNT' },
    { key:'TotalCost',       label:'SUM Cost', render: fmt$ },
    { key:'AvgCost',         label:'AVG Cost', render: fmt$ },
    { key:'MinCost',         label:'MIN Cost', render: fmt$ },
    { key:'MaxCost',         label:'MAX Cost', render: fmt$ },
  ], null);
  renderBarChart('report-treatment-chart', treatDept.map(r => ({ label: r.DepartmentName, value: r.TotalCost })), 'c3', '$');

  const docWork = data.doctor_workload || [];
  buildTable('report-doctors-table', docWork, [
    { key:'DoctorName',        label:'Doctor' },
    { key:'Specialty',         label:'Specialty' },
    { key:'DepartmentName',    label:'Department' },
    { key:'TotalAppointments', label:'COUNT Appts' },
    { key:'TotalRevenue',      label:'SUM Revenue', render: fmt$ },
    { key:'AvgRevenue',        label:'AVG Revenue', render: fmt$ },
    { key:'MinBill',           label:'MIN Bill',    render: fmt$ },
    { key:'MaxBill',           label:'MAX Bill',    render: fmt$ },
  ], null);
  renderBarChart('report-doctors-chart', docWork.map(r => ({ label: r.DoctorName, value: r.TotalAppointments })), 'c4', '');

  const ins = data.insurance_analysis || [];
  buildTable('report-insurance-table', ins, [
    { key:'ProviderName',    label:'Provider' },
    { key:'CoveragePercent', label:'Coverage %',   render: fmtPct },
    { key:'TotalPatients',   label:'COUNT Patients' },
    { key:'TotalClaims',     label:'COUNT Claims' },
    { key:'TotalBilled',     label:'SUM Billed',   render: fmt$ },
    { key:'TotalCovered',    label:'SUM Covered',  render: fmt$ },
    { key:'TotalPatientOwe', label:'Patient Owes', render: fmt$ },
    { key:'AvgCoverage',     label:'AVG Coverage', render: fmt$ },
    { key:'MinCoverage',     label:'MIN Coverage', render: fmt$ },
    { key:'MaxCoverage',     label:'MAX Coverage', render: fmt$ },
  ], null);
  renderBarChart('report-insurance-chart', ins.map(r => ({ label: r.ProviderName, value: r.TotalCovered })), 'c5', '$');
}
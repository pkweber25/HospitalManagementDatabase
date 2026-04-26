// ============================================================
//  CareFlow — app.js
//  Role-based views:
//    admin       → full access: patients, doctors, nurses,
//                  appointments, system users, hospital admins
//    receptionist→ patients, doctors, nurses, appointments
//    doctor      → My Appointments, My Patients (filtered)
//    nurse       → My Appointments, My Patients (filtered)
//    patient     → My Appointments (self-service portal)
// ============================================================

let token = localStorage.getItem('token') || null;
let role  = localStorage.getItem('role')  || null;
let currentUsername = localStorage.getItem('username') || null;

// In-memory caches used to populate dropdowns
let cachedPatients = [];
let cachedDoctors  = [];
let cachedNurses   = [];

const API = {
  get: (url)       => authFetch(url),
  post:(url, body) => authFetch(url, {method:'POST', body: JSON.stringify(body)}),
  put: (url, body) => authFetch(url, {method:'PUT',  body: JSON.stringify(body)}),
  del: (url)       => authFetch(url, {method:'DELETE'}),
};

function authFetch(url, opts = {}) {
  opts.headers = Object.assign({'Content-Type':'application/json'}, opts.headers || {});
  if (token) opts.headers['Authorization'] = 'Bearer ' + token;
  return fetch(url, opts);
}

// ── Toast ──────────────────────────────────────────────────
function toast(msg, type = 'success') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast show ' + type;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = 'toast'; }, 3000);
}

// ── Modal helpers ──────────────────────────────────────────
function openModal(id)  { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
// Close modal when clicking the overlay backdrop
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.style.display = 'none';
  }
});

// ── Tab switching ──────────────────────────────────────────
function switchTab(btn, tabName) {
  document.querySelectorAll('.tab-panel').forEach(s => s.style.display = 'none');
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  const panel = document.getElementById('tab-' + tabName);
  if (panel) panel.style.display = 'block';
  if (btn)   btn.classList.add('active');
}

// ── Auth tab (sign-in vs register) ────────────────────────
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
    scheduled: 'badge-scheduled', completed: 'badge-completed',
    canceled:  'badge-canceled',  paid:      'badge-paid',
    pending:   'badge-pending',
  };
  const cls = map[(status||'').toLowerCase()] || '';
  return `<span class="badge ${cls}">${status || '—'}</span>`;
}

// Build a generic data table.
// cols = [{key, label, render}]  (render is optional)
function buildTable(tableId, data, cols, actions) {
  const table = document.getElementById(tableId);
  if (!table) return;
  const thead = table.querySelector('thead tr');
  const tbody = table.querySelector('tbody');
  thead.innerHTML = '';
  tbody.innerHTML = '';

  if (!data || !data.length) {
    const colCount = cols.length + (actions ? 1 : 0);
    tbody.innerHTML = `<tr><td colspan="${colCount}" class="empty-state">No records found.</td></tr>`;
    // Still render headers
    cols.forEach(c => { const th = document.createElement('th'); th.textContent = c.label; thead.appendChild(th); });
    if (actions) { const th = document.createElement('th'); th.textContent = 'Actions'; thead.appendChild(th); }
    return;
  }

  cols.forEach(c => { const th = document.createElement('th'); th.textContent = c.label; thead.appendChild(th); });
  if (actions) { const th = document.createElement('th'); th.textContent = 'Actions'; thead.appendChild(th); }

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

// ── Dropdown population ────────────────────────────────────
function populateSelect(selectId, items, valueFn, labelFn, placeholder) {
  const sel = document.getElementById(selectId);
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = placeholder ? `<option value="" disabled selected>${placeholder}</option>` : '';
  items.forEach(item => {
    const opt = document.createElement('option');
    opt.value   = valueFn(item);
    opt.textContent = labelFn(item);
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

function populateAllDropdowns() {
  const patLabel = p => `${p.FirstName} ${p.LastName}`;
  const docLabel = d => `Dr. ${d.FirstName} ${d.LastName} — ${d.Specialty || d.DepartmentID}`;
  const nurLabel = n => `${n.FirstName} ${n.LastName} (${n.Certification || ''})`;

  ['appt-patient-select', 'edit-appt-patient-select'].forEach(id =>
    populateSelect(id, cachedPatients, p => p.PatientID, patLabel, 'Select patient…'));
  ['appt-doctor-select', 'edit-appt-doctor-select'].forEach(id =>
    populateSelect(id, cachedDoctors, d => d.DoctorID, docLabel, 'Select doctor…'));
  ['appt-nurse-select', 'edit-appt-nurse-select'].forEach(id =>
    populateSelect(id, cachedNurses, n => n.NurseID, nurLabel, 'Select nurse…'));

  // Patient portal: doctor-only select (simpler label)
  const pp = document.getElementById('portal-doctor-select');
  if (pp) {
    pp.innerHTML = '<option value="" disabled selected>Choose a doctor…</option>';
    cachedDoctors.forEach(d => {
      const o = document.createElement('option');
      o.value = d.DoctorID;
      o.textContent = `Dr. ${d.FirstName} ${d.LastName}${d.Specialty ? ' — ' + d.Specialty : ''}`;
      pp.appendChild(o);
    });
  }
}

// ── Session start/end ──────────────────────────────────────
function startSession(data) {
  token = data.token;
  role  = data.role || 'patient';
  currentUsername = data.username || '';
  localStorage.setItem('token',    token);
  localStorage.setItem('role',     role);
  localStorage.setItem('username', currentUsername);

  document.getElementById('auth-screen').style.display = 'none';
  document.getElementById('app').style.display = 'flex';

  // Avatar initial
  document.getElementById('user-avatar').textContent =
    (currentUsername[0] || '?').toUpperCase();
  document.getElementById('user-info').textContent = currentUsername;
  document.getElementById('user-role-badge').textContent = role;

  buildNavForRole(role);
  loadDataForRole(role);
}

function endSession() {
  token = null; role = null; currentUsername = null;
  localStorage.clear();
  document.getElementById('auth-screen').style.display = 'flex';
  document.getElementById('app').style.display = 'none';
}

// ── Nav visibility per role ────────────────────────────────
function buildNavForRole(r) {
  // Show/hide nav buttons
  const show = ids => ids.forEach(id => {
    const el = document.querySelector(`[data-tab="${id}"]`);
    if (el) el.style.display = 'flex';
  });
  const hide = ids => ids.forEach(id => {
    const el = document.querySelector(`[data-tab="${id}"]`);
    if (el) el.style.display = 'none';
  });
  // Admin section labels
  document.querySelectorAll('.admin-only').forEach(el => {
    el.style.display = (r === 'admin') ? '' : 'none';
  });

  // All tabs hidden by default first
  hide(['patients','doctors','nurses','appointments','users','admins','my-appointments','my-patients','portal']);

  if (r === 'admin') {
    show(['patients','doctors','nurses','appointments','users','admins']);
    // Activate patients tab
    setTimeout(() => {
      const btn = document.querySelector('[data-tab="patients"]');
      switchTab(btn, 'patients');
    }, 0);
  } else if (r === 'receptionist') {
    show(['patients','doctors','nurses','appointments']);
    setTimeout(() => {
      const btn = document.querySelector('[data-tab="patients"]');
      switchTab(btn, 'patients');
    }, 0);
  } else if (r === 'doctor' || r === 'nurse') {
    show(['my-appointments','my-patients']);
    setTimeout(() => {
      const btn = document.querySelector('[data-tab="my-appointments"]');
      switchTab(btn, 'my-appointments');
    }, 0);
  } else {
    // patient
    show(['portal']);
    setTimeout(() => {
      const btn = document.querySelector('[data-tab="portal"]');
      switchTab(btn, 'portal');
    }, 0);
  }
}

// ── Load data per role ─────────────────────────────────────
async function loadDataForRole(r) {
  if (r === 'admin' || r === 'receptionist') {
    await Promise.all([loadPatients(), loadDoctors(), loadNurses()]);
    await loadAppointments();
    if (r === 'admin') { loadUsers(); loadAdmins(); }
  } else if (r === 'doctor' || r === 'nurse') {
    await Promise.all([loadMyAppointments(), loadMyPatients()]);
  } else {
    // patient
    await Promise.all([loadDoctors(), loadNurses()]);
    await loadPortalAppointments();
  }
}

// ══════════════════════════════════════════════════════════
//  ADMIN / RECEPTIONIST DATA LOADERS
// ══════════════════════════════════════════════════════════

async function loadPatients() {
  const res = await API.get('/api/patients');
  if (!res.ok) return;
  cachedPatients = await res.json();
  populateAllDropdowns();

  const cols = [
    { key:'PatientID',  label:'ID' },
    { key:'FirstName',  label:'First Name' },
    { key:'LastName',   label:'Last Name' },
    { key:'DOB',        label:'Date of Birth' },
    { key:'Gender',     label:'Gender' },
    { key:'Phone',      label:'Phone' },
    { key:'Address',    label:'Address' },
    { key:'ProviderID', label:'Insurance', render: v => providerName(v) },
  ];
  const providerMap = {1:'BlueCross',2:'Aetna',3:'Medicare',4:'Cigna',5:'UnitedHealth'};
  function providerName(id) { return providerMap[id] || id; }

  const canEdit = (role === 'admin' || role === 'receptionist');
  buildTable('patients-table', cachedPatients, cols, canEdit ? row => `
    <button class="btn-icon btn-edit" onclick="openEditPatient(${JSON.stringify(row).replace(/"/g,'&quot;')})">✏️ Edit</button>
    <button class="btn-icon btn-delete" onclick="deletePatient(${row.PatientID})">🗑️ Delete</button>
  ` : null);
}

async function loadDoctors() {
  const res = await API.get('/api/doctors');
  if (!res.ok) return;
  cachedDoctors = await res.json();
  populateAllDropdowns();

  const cols = [
    {key:'DoctorID',    label:'ID'},
    {key:'FirstName',   label:'First Name'},
    {key:'LastName',    label:'Last Name'},
    {key:'Specialty',   label:'Specialty'},
    {key:'Phone',       label:'Phone'},
    {key:'DepartmentID',label:'Department', render: v => deptName(v)},
  ];
  const deptMap = {1:'Cardiology',2:'Pediatrics',3:'Emergency',4:'Oncology',5:'Neurology'};
  function deptName(id){ return deptMap[id] || id; }

  buildTable('doctors-table', cachedDoctors, cols,
    role === 'admin' ? row => `
      <button class="btn-icon btn-delete" onclick="deleteDoctor(${row.DoctorID})">🗑️ Delete</button>
    ` : null
  );
}

async function loadNurses() {
  const res = await API.get('/api/nurses');
  if (!res.ok) return;
  cachedNurses = await res.json();
  populateAllDropdowns();

  const cols = [
    {key:'NurseID',     label:'ID'},
    {key:'FirstName',   label:'First Name'},
    {key:'LastName',    label:'Last Name'},
    {key:'Certification',label:'Certification'},
    {key:'Phone',       label:'Phone'},
    {key:'DepartmentID',label:'Department', render: v => ({1:'Cardiology',2:'Pediatrics',3:'Emergency',4:'Oncology',5:'Neurology'}[v]||v)},
  ];
  buildTable('nurses-table', cachedNurses, cols, null);
}

async function loadAppointments() {
  const res = await API.get('/api/appointments');
  if (!res.ok) return;
  const data = await res.json();

  const cols = [
    {key:'AppointmentID',   label:'ID'},
    {key:'PatientID',       label:'Patient',  render: id => patientName(id)},
    {key:'DoctorID',        label:'Doctor',   render: id => doctorName(id)},
    {key:'NurseID',         label:'Nurse',    render: id => nurseName(id)},
    {key:'AppointmentDate', label:'Date'},
    {key:'AppointmentTime', label:'Time',     render: v => (v||'').substring(0,5)},
    {key:'Status',          label:'Status',   render: v => statusBadge(v)},
    {key:'Purpose',         label:'Purpose'},
  ];
  buildTable('appts-table', data, cols, row => `
    <button class="btn-icon btn-edit" onclick="openEditAppt(${JSON.stringify(row).replace(/"/g,'&quot;')})">✏️ Edit</button>
    <button class="btn-icon btn-delete" onclick="deleteAppointment(${row.AppointmentID})">🗑️ Delete</button>
  `);
}

// Helper name lookups
function patientName(id) {
  const p = cachedPatients.find(p => p.PatientID == id);
  return p ? `${p.FirstName} ${p.LastName}` : `#${id}`;
}
function doctorName(id) {
  const d = cachedDoctors.find(d => d.DoctorID == id);
  return d ? `Dr. ${d.LastName}` : `#${id}`;
}
function nurseName(id) {
  const n = cachedNurses.find(n => n.NurseID == id);
  return n ? `${n.FirstName} ${n.LastName}` : `#${id}`;
}

// ── Users & Admins (admin only) ────────────────────────────
async function loadUsers() {
  const res = await API.get('/api/users');
  if (!res.ok) return;
  const data = await res.json();
  const cols = [
    {key:'id',        label:'ID'},
    {key:'username',  label:'Username'},
    {key:'full_name', label:'Full Name'},
    {key:'role',      label:'Role'},
  ];
  buildTable('users-table', data, cols, row => `
    <button class="btn-icon btn-edit" onclick="adminChangeRole(${row.id},'${row.role}')">🔑 Role</button>
    <button class="btn-icon btn-edit" onclick="adminResetPw(${row.id})">🔒 Password</button>
    <button class="btn-icon btn-delete" onclick="adminDeleteUser(${row.id})">🗑️ Delete</button>
  `);
}

async function loadAdmins() {
  const res = await API.get('/api/admins');
  if (!res.ok) return;
  const data = await res.json();
  const cols = [
    {key:'AdminID',   label:'ID'},
    {key:'FirstName', label:'First Name'},
    {key:'LastName',  label:'Last Name'},
    {key:'Email',     label:'Email'},
    {key:'Role',      label:'Role'},
  ];
  buildTable('admins-table', data, cols, row => `
    <button class="btn-icon btn-delete" onclick="deleteAdmin(${row.AdminID})">🗑️ Delete</button>
  `);
}

// ══════════════════════════════════════════════════════════
//  DOCTOR / NURSE VIEWS  (filtered to "me")
// ══════════════════════════════════════════════════════════

async function loadMyAppointments() {
  // Fetch all appointments, then show those belonging to this user
  const [apptRes, patRes, docRes, nurRes] = await Promise.all([
    API.get('/api/appointments'),
    API.get('/api/patients'),
    API.get('/api/doctors'),
    API.get('/api/nurses'),
  ]);
  if (!apptRes.ok) return;

  cachedPatients = patRes.ok ? await patRes.json() : [];
  cachedDoctors  = docRes.ok ? await docRes.json() : [];
  cachedNurses   = nurRes.ok ? await nurRes.json() : [];

  const allAppts = await apptRes.json();

  // Match by username → look up DoctorID / NurseID
  let filtered = allAppts;
  if (role === 'doctor') {
    const doc = cachedDoctors.find(d =>
      `${d.FirstName} ${d.LastName}`.toLowerCase() === currentUsername.toLowerCase() ||
      d.LastName.toLowerCase() === currentUsername.toLowerCase()
    );
    if (doc) filtered = allAppts.filter(a => a.DoctorID == doc.DoctorID);
  } else if (role === 'nurse') {
    const nur = cachedNurses.find(n =>
      `${n.FirstName} ${n.LastName}`.toLowerCase() === currentUsername.toLowerCase() ||
      n.LastName.toLowerCase() === currentUsername.toLowerCase()
    );
    if (nur) filtered = allAppts.filter(a => a.NurseID == nur.NurseID);
  }

  const cols = [
    {key:'AppointmentDate', label:'Date'},
    {key:'AppointmentTime', label:'Time',    render: v => (v||'').substring(0,5)},
    {key:'PatientID',       label:'Patient', render: id => patientName(id)},
    {key:'Status',          label:'Status',  render: v => statusBadge(v)},
    {key:'Purpose',         label:'Purpose / Reason'},
  ];
  if (role === 'doctor') {
    cols.push({key:'NurseID', label:'Assigned Nurse', render: id => nurseName(id)});
  }
  buildTable('my-appts-table', filtered, cols, null);
}

async function loadMyPatients() {
  // Show unique patients from my appointments
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
  const allAppts  = await apptRes.json();

  let myPatientIds = new Set();
  if (role === 'doctor') {
    const doc = cachedDoctors.find(d =>
      `${d.FirstName} ${d.LastName}`.toLowerCase() === currentUsername.toLowerCase() ||
      d.LastName.toLowerCase() === currentUsername.toLowerCase()
    );
    if (doc) allAppts.filter(a => a.DoctorID == doc.DoctorID).forEach(a => myPatientIds.add(a.PatientID));
    else cachedPatients.forEach(p => myPatientIds.add(p.PatientID)); // fallback: show all
  } else if (role === 'nurse') {
    const nur = cachedNurses.find(n =>
      `${n.FirstName} ${n.LastName}`.toLowerCase() === currentUsername.toLowerCase() ||
      n.LastName.toLowerCase() === currentUsername.toLowerCase()
    );
    if (nur) allAppts.filter(a => a.NurseID == nur.NurseID).forEach(a => myPatientIds.add(a.PatientID));
    else cachedPatients.forEach(p => myPatientIds.add(p.PatientID));
  }

  const myPatients = cachedPatients.filter(p => myPatientIds.has(p.PatientID));
  const cols = [
    {key:'FirstName',  label:'First Name'},
    {key:'LastName',   label:'Last Name'},
    {key:'DOB',        label:'Date of Birth'},
    {key:'Gender',     label:'Gender'},
    {key:'Phone',      label:'Phone'},
  ];
  buildTable('my-patients-table', myPatients, cols, null);
}

// ══════════════════════════════════════════════════════════
//  PATIENT PORTAL
// ══════════════════════════════════════════════════════════

async function loadPortalAppointments() {
  // Patients can see their own appointments if their username
  // matches a patient record. We fetch all and filter.
  const res = await API.get('/api/appointments');
  if (!res.ok) return;
  const all = await res.json();

  // Try to find this patient's PatientID
  const me = cachedPatients.find(p =>
    `${p.FirstName} ${p.LastName}`.toLowerCase() === currentUsername.toLowerCase() ||
    p.LastName.toLowerCase() === currentUsername.toLowerCase()
  );

  const mine = me ? all.filter(a => a.PatientID == me.PatientID) : [];

  const cols = [
    {key:'AppointmentDate', label:'Date'},
    {key:'AppointmentTime', label:'Time',   render: v => (v||'').substring(0,5)},
    {key:'DoctorID',        label:'Doctor', render: id => doctorName(id)},
    {key:'Status',          label:'Status', render: v => statusBadge(v)},
    {key:'Purpose',         label:'Reason for Visit'},
  ];
  buildTable('portal-appts-table', mine, cols, row =>
    row.Status === 'Scheduled' ? `
      <button class="btn-icon btn-delete" onclick="cancelPortalAppointment(${row.AppointmentID})">✕ Cancel</button>
    ` : ''
  );
}

async function cancelPortalAppointment(id) {
  if (!confirm('Cancel this appointment?')) return;
  const res = await API.put(`/api/appointments/${id}`, {Status: 'Canceled'});
  if (res.ok) { toast('Appointment canceled'); loadPortalAppointments(); }
  else toast('Could not cancel appointment', 'error');
}

// ══════════════════════════════════════════════════════════
//  CRUD OPERATIONS
// ══════════════════════════════════════════════════════════

// ── Patients ───────────────────────────────────────────────
document.getElementById('patient-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/patients', obj);
  if (res.ok) {
    closeModal('add-patient-modal');
    e.target.reset();
    toast('Patient registered');
    loadPatients();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed to add patient', 'error');
  }
});

function openEditPatient(row) {
  const form = document.getElementById('edit-patient-form');
  Object.keys(row).forEach(k => {
    const el = form.elements[k];
    if (el) el.value = row[k] || '';
  });
  openModal('edit-patient-modal');
}

document.getElementById('edit-patient-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const id  = obj.PatientID;
  const res = await API.put(`/api/patients/${id}`, obj);
  if (res.ok) {
    closeModal('edit-patient-modal');
    toast('Patient updated');
    loadPatients();
  } else {
    const err = await res.json();
    toast(err.error || 'Update failed', 'error');
  }
});

async function deletePatient(id) {
  if (!confirm('Delete this patient record?')) return;
  const res = await API.del(`/api/patients/${id}`);
  if (res.ok) { toast('Patient deleted'); loadPatients(); }
  else toast('Delete failed', 'error');
}

// ── Doctors ────────────────────────────────────────────────
document.getElementById('doctor-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/doctors', obj);
  if (res.ok) {
    closeModal('add-doctor-modal');
    e.target.reset();
    toast('Doctor added');
    loadDoctors();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed to add doctor', 'error');
  }
});

async function deleteDoctor(id) {
  if (!confirm('Remove this doctor record?')) return;
  const res = await API.del(`/api/doctors/${id}`);
  if (res.ok) { toast('Doctor removed'); loadDoctors(); }
  else toast('Delete failed', 'error');
}

// ── Appointments ───────────────────────────────────────────
document.getElementById('appt-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/appointments', obj);
  if (res.ok) {
    closeModal('add-appt-modal');
    e.target.reset();
    toast('Appointment scheduled');
    loadAppointments();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed to schedule', 'error');
  }
});

function openEditAppt(row) {
  const form = document.getElementById('edit-appt-form');
  // Populate dropdowns first if empty
  populateAllDropdowns();
  Object.keys(row).forEach(k => {
    const el = form.elements[k];
    if (el) el.value = row[k] || '';
  });
  openModal('edit-appt-modal');
}

document.getElementById('edit-appt-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const id  = obj.AppointmentID;
  const res = await API.put(`/api/appointments/${id}`, obj);
  if (res.ok) {
    closeModal('edit-appt-modal');
    toast('Appointment updated');
    loadAppointments();
  } else {
    const err = await res.json();
    toast(err.error || 'Update failed', 'error');
  }
});

async function deleteAppointment(id) {
  if (!confirm('Delete this appointment?')) return;
  const res = await API.del(`/api/appointments/${id}`);
  if (res.ok) { toast('Appointment deleted'); loadAppointments(); }
  else toast('Delete failed', 'error');
}

// ── Patient portal appointment ─────────────────────────────
const portalForm = document.getElementById('portal-appt-form');
if (portalForm) {
  portalForm.addEventListener('submit', async e => {
    e.preventDefault();
    const obj = Object.fromEntries(new FormData(e.target).entries());
    // Fetch this patient's own linked record from the server
    const meRes = await API.get('/api/patients/me');
    if (!meRes.ok) {
      toast('Your patient record was not found. Please contact reception.', 'error');
      return;
    }
    const me = await meRes.json();
    if (!me || !me.PatientID) {
      toast('Your patient record was not found. Please contact reception.', 'error');
      return;
    }
    obj.PatientID = me.PatientID;
    obj.Status    = 'Scheduled';
    // Auto-assign a nurse from the selected doctor's department
    const doc  = cachedDoctors.find(d => d.DoctorID == obj.DoctorID);
    const nurse = doc ? cachedNurses.find(n => n.DepartmentID == doc.DepartmentID) : cachedNurses[0];
    obj.NurseID = nurse ? nurse.NurseID : 1;

    const res = await API.post('/api/appointments', obj);
    if (res.ok) {
      closeModal('portal-appt-modal');
      e.target.reset();
      toast('Appointment requested!');
      loadPortalAppointments();
    } else {
      const err = await res.json();
      toast(err.error || 'Could not book appointment', 'error');
    }
  });
}

// ── Hospital admins ────────────────────────────────────────
document.getElementById('admin-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/admins', obj);
  if (res.ok) {
    closeModal('add-admin-modal');
    e.target.reset();
    toast('Admin record added');
    loadAdmins();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed', 'error');
  }
});

async function deleteAdmin(id) {
  if (!confirm('Delete this admin record?')) return;
  const res = await API.del(`/api/admins/${id}`);
  if (res.ok) { toast('Deleted'); loadAdmins(); }
  else toast('Delete failed', 'error');
}

// ── System users (admin panel) ─────────────────────────────
document.getElementById('create-user-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await API.post('/api/users', obj);
  if (res.ok) {
    closeModal('add-user-modal');
    e.target.reset();
    toast('User created');
    loadUsers();
  } else {
    const err = await res.json();
    toast(err.error || 'Failed to create user', 'error');
  }
});

async function adminChangeRole(userId, currentRole) {
  const roles = ['admin','doctor','receptionist','patient'];
  const newRole = prompt(`Change role (${roles.join(', ')}):`, currentRole);
  if (!newRole || !roles.includes(newRole.trim())) return;
  const res = await API.put(`/api/users/${userId}/role`, {role: newRole.trim()});
  if (res.ok) { toast('Role updated'); loadUsers(); }
  else { const e = await res.json(); toast(e.error || 'Failed', 'error'); }
}

async function adminResetPw(userId) {
  const pw = prompt('Enter new password:');
  if (!pw) return;
  const res = await API.put(`/api/users/${userId}/password`, {new_password: pw});
  if (res.ok) { toast('Password updated'); }
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
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(obj),
  });
  if (res.ok) {
    const data = await res.json();
    startSession(data);
  } else {
    toast('Invalid username or password', 'error');
  }
});

document.getElementById('register-form').addEventListener('submit', async e => {
  e.preventDefault();
  const obj = Object.fromEntries(new FormData(e.target).entries());
  const res = await fetch('/api/register', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(obj),
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
  if (res.ok) {
    closeModal('change-password-modal');
    e.target.reset();
    toast('Password updated');
  } else {
    const err = await res.json();
    toast(err.error || 'Failed', 'error');
  }
});

function openPasswordModal() { openModal('change-password-modal'); }

// ══════════════════════════════════════════════════════════
//  INIT — resume session if token exists
// ══════════════════════════════════════════════════════════
if (token && role) {
  startSession({ token, role, username: currentUsername });
}
let token = localStorage.getItem('token') || null;
let role = localStorage.getItem('role') || null;

function showTab(id){
  document.querySelectorAll('.tab').forEach(s=>s.style.display='none');
  const el = document.getElementById(id);
  if(el) el.style.display='block';
}

// Generic helper to build table from data
function buildTable(tableId, data){
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const thead = table.querySelector('thead tr');
  tbody.innerHTML=''; thead.innerHTML='';
  if(!data || !data.length) return;
  const keys = Object.keys(data[0]);
  // header
  keys.forEach(k=>{ const th=document.createElement('th'); th.textContent=k; thead.appendChild(th); });
  const actTh = document.createElement('th'); actTh.textContent='Actions'; thead.appendChild(actTh);
  data.forEach(row=>{
    const tr=document.createElement('tr');
    keys.forEach(k=>{ const td=document.createElement('td'); td.textContent=row[k]; tr.appendChild(td); });
    const actTd=document.createElement('td'); actTd.className='table-actions';
    const del=document.createElement('button'); del.textContent='Delete'; del.onclick=()=>{ if(confirm('Delete?')) delRow(tableId,row); };
    actTd.appendChild(del); tr.appendChild(actTd);
    tbody.appendChild(tr);
  });
}

// Build users table (admin)
function buildUsersTable(data){
  const table = document.getElementById('users-table');
  const tbody = table.querySelector('tbody');
  const thead = table.querySelector('thead tr');
  tbody.innerHTML=''; thead.innerHTML='';
  if(!data || !data.length){ thead.innerHTML='<th>No users</th>'; return; }
  const keys = ['id','username','role','full_name'];
  keys.forEach(k=>{ const th=document.createElement('th'); th.textContent=k; thead.appendChild(th); });
  const actTh = document.createElement('th'); actTh.textContent='Actions'; thead.appendChild(actTh);
  data.forEach(row=>{
    const tr=document.createElement('tr');
    keys.forEach(k=>{ const td=document.createElement('td'); td.textContent=row[k] || ''; tr.appendChild(td); });
    const actTd=document.createElement('td');
    const roleBtn=document.createElement('button'); roleBtn.textContent='Change Role'; roleBtn.onclick=()=>adminChangeUserRole(row.id, row.role);
    const pwBtn=document.createElement('button'); pwBtn.textContent='Change Password'; pwBtn.onclick=()=>adminChangeUserPassword(row.id);
    const delBtn=document.createElement('button'); delBtn.textContent='Delete'; delBtn.onclick=()=>adminDeleteUser(row.id);
    actTd.appendChild(roleBtn); actTd.appendChild(pwBtn); actTd.appendChild(delBtn); tr.appendChild(actTd);
    tbody.appendChild(tr);
  });
}

function authFetch(url, opts={}){
  opts = Object.assign({}, opts);
  opts.headers = Object.assign({}, opts.headers || {});
  if(!(opts.body instanceof FormData)) opts.headers['Content-Type'] = opts.headers['Content-Type'] || 'application/json';
  if(token) opts.headers['Authorization'] = 'Bearer ' + token;
  return fetch(url, opts);
}

// API calls
async function fetchPatients(){
  const res = await authFetch('/api/patients');
  const data = await res.json(); buildTable('patients-table',data);
}
async function fetchDoctors(){
  const res = await authFetch('/api/doctors');
  const data = await res.json(); buildTable('doctors-table',data);
}
async function fetchAppts(){
  const res = await authFetch('/api/appointments');
  const data = await res.json(); buildTable('appts-table',data);
}
async function fetchUsers(){
  if(role!=='admin') return alert('Admin only');
  const res = await authFetch('/api/users');
  if(!res.ok) return alert('Failed to fetch users');
  const data = await res.json(); buildUsersTable(data);
}

async function fetchAdmins(){
  const res = await authFetch('/api/admins');
  const data = await res.json(); buildTable('admins-table',data);
}

// Auth handlers
document.getElementById('login-form').addEventListener('submit', async e=>{
  e.preventDefault(); const form = new FormData(e.target); const obj = Object.fromEntries(form.entries());
  const res = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(obj)});
  if(res.ok){ 
    const data = await res.json(); 
    token = data.token; 
    role = data.role || 'user';
    localStorage.setItem('token', token); 
    localStorage.setItem('username', data.username || '');
    localStorage.setItem('role', role);
    document.getElementById('logged-out').style.display='none';
    document.getElementById('logged-in').style.display='block';
    document.getElementById('user-info').textContent = 'Signed in as: '+ (data.username || '');
    if(role==='admin') {
      document.getElementById('nav-users').style.display='inline-block';
      document.getElementById('nav-admins').style.display='inline-block';
    }
    fetchPatients(); fetchDoctors(); fetchAppts(); if(role==='admin') { fetchUsers(); fetchAdmins(); }
  } else { alert('Login failed'); }
});

document.getElementById('register-form').addEventListener('submit', async e=>{
  e.preventDefault(); const form = new FormData(e.target); const obj = Object.fromEntries(form.entries());
  const res = await fetch('/api/register', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(obj)});
  if(res.ok){ alert('Registered. You can now log in.'); e.target.reset(); } else { const txt = await res.text(); alert('Register failed: '+txt); }
});

document.getElementById('logout-btn').addEventListener('click', e=>{
  token = null; role = null; localStorage.removeItem('token'); localStorage.removeItem('username'); localStorage.removeItem('role'); document.getElementById('logged-out').style.display='block'; document.getElementById('logged-in').style.display='none'; document.getElementById('user-info').textContent=''; document.getElementById('nav-users').style.display='none'; document.getElementById('nav-admins').style.display='none';
});

// Change own password
const changeForm = document.getElementById('change-password-form');
if(changeForm){
  changeForm.addEventListener('submit', async e=>{
    e.preventDefault(); const form = new FormData(e.target); const obj = Object.fromEntries(form.entries());
    const res = await authFetch('/api/users/me/password', {method:'PUT', body: JSON.stringify(obj)});
    if(res.ok){ alert('Password changed'); e.target.reset(); } else { const txt = await res.json(); alert('Error: '+(txt.error||JSON.stringify(txt))); }
  });
}

// Add handlers for create actions
if(document.getElementById('patient-form')){
  document.getElementById('patient-form').addEventListener('submit', async e=>{
    e.preventDefault(); const form=new FormData(e.target); const obj=Object.fromEntries(form.entries());
    await authFetch('/api/patients',{method:'POST',body:JSON.stringify(obj)}); e.target.reset(); fetchPatients();
  });
}

if(document.getElementById('doctor-form')){
  document.getElementById('doctor-form').addEventListener('submit', async e=>{
    e.preventDefault(); const form=new FormData(e.target); const obj=Object.fromEntries(form.entries());
    await authFetch('/api/doctors',{method:'POST',body:JSON.stringify(obj)}); e.target.reset(); fetchDoctors();
  });
}

if(document.getElementById('appt-form')){
  document.getElementById('appt-form').addEventListener('submit', async e=>{
    e.preventDefault(); const form=new FormData(e.target); const obj=Object.fromEntries(form.entries());
    await authFetch('/api/appointments',{method:'POST',body:JSON.stringify(obj)}); e.target.reset(); fetchAppts();
  });
}

if(document.getElementById('admin-form')){
  document.getElementById('admin-form').addEventListener('submit', async e=>{
    e.preventDefault(); const form=new FormData(e.target); const obj=Object.fromEntries(form.entries());
    const res = await authFetch('/api/admins',{method:'POST',body:JSON.stringify(obj)}); 
    if(res.ok) { e.target.reset(); fetchAdmins(); } 
    else { const err = await res.json(); alert('Admin Error: ' + err.error); }
  });
}

// delete based on table id
async function delRow(tableId,row){
  if(tableId==='patients-table') await authFetch('/api/patients/'+encodeURIComponent(row.PatientID),{method:'DELETE'});
  if(tableId==='doctors-table') await authFetch('/api/doctors/'+encodeURIComponent(row.DoctorID),{method:'DELETE'});
  if(tableId==='appts-table') await authFetch('/api/appointments/'+encodeURIComponent(row.AppointmentID),{method:'DELETE'});
  if(tableId==='admins-table') await authFetch('/api/admins/'+encodeURIComponent(row.AdminID),{method:'DELETE'});
  fetchPatients(); fetchDoctors(); fetchAppts(); fetchAdmins();
}

// Admin actions
async function adminChangeUserPassword(userId){
  const new_password = prompt('Enter new password for user id '+userId);
  if(!new_password) return;
  const res = await authFetch('/api/users/'+userId+'/password', {method:'PUT', body: JSON.stringify({new_password})});
  if(res.ok){ alert('Password updated'); fetchUsers(); } else { const txt = await res.json(); alert('Error: '+(txt.error||JSON.stringify(txt))); }
}

async function adminChangeUserRole(userId, currentRole){
  const roles = ['admin','doctor','receptionist','patient'];
  let new_role = prompt('Enter new role ('+roles.join(',')+')', currentRole || 'patient');
  if(!new_role) return;
  new_role = new_role.trim();
  if(!roles.includes(new_role)){ alert('Invalid role'); return; }
  const res = await authFetch('/api/users/'+userId+'/role', {method:'PUT', body: JSON.stringify({role:new_role})});
  if(res.ok){ alert('Role updated'); fetchUsers(); } else { const txt = await res.json(); alert('Error: '+(txt.error||JSON.stringify(txt))); }
}

async function adminDeleteUser(userId){
  if(!confirm('Delete user '+userId+'?')) return;
  const res = await authFetch('/api/users/'+userId, {method:'DELETE'});
  if(res.ok){ alert('Deleted'); fetchUsers(); } else { const txt = await res.json(); alert('Error: '+(txt.error||JSON.stringify(txt))); }
}

// Create user form handler (admin)
const createUserForm = document.getElementById('create-user-form');
if(createUserForm){
  createUserForm.addEventListener('submit', async e=>{
    e.preventDefault();
    const obj = Object.fromEntries(new FormData(createUserForm).entries());
    const res = await authFetch('/api/users', {method:'POST', body: JSON.stringify(obj)});
    if(res.ok){ alert('User created'); createUserForm.reset(); fetchUsers(); } else { const txt = await res.json(); alert('Error: '+(txt.error||JSON.stringify(txt))); }
  });
}

// initial load
if(localStorage.getItem('token')){ 
  token = localStorage.getItem('token'); 
  role = localStorage.getItem('role') || null;
  document.getElementById('logged-out').style.display='none'; 
  document.getElementById('logged-in').style.display='block'; 
  document.getElementById('user-info').textContent = 'Signed in as: '+ (localStorage.getItem('username')||''); 
  if(role==='admin') {
    document.getElementById('nav-users').style.display='inline-block';
    document.getElementById('nav-admins').style.display='inline-block';
  }
  document.getElementById('nav-admins').style.display='inline-block';
}
showTab('patients'); fetchPatients(); fetchDoctors(); fetchAppts(); if(role==='admin') { fetchUsers(); fetchAdmins(); }
const API = CONFIG.BACKEND_URL;

function switchTab(tab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('login-form').style.display = tab === 'login' ? 'block' : 'none';
  document.getElementById('register-form').style.display = tab === 'register' ? 'block' : 'none';
}

function showMsg(id, text, type) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.className = 'msg ' + type;
}

async function login() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const role = document.getElementById('login-role').value;

  if (!email || !password) return showMsg('login-msg', 'Please fill in all fields.', 'error');

  try {
    const res = await fetch(`${API}/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, role })
    });
    const data = await res.json();
    if (res.ok) {
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      window.location.href = data.user.role === 'admin' ? 'admin.html' : 'employee.html';
    } else {
      showMsg('login-msg', data.error || 'Login failed.', 'error');
    }
  } catch {
    showMsg('login-msg', 'Cannot connect to server. Make sure backend is running.', 'error');
  }
}

async function register() {
  const name = document.getElementById('reg-name').value.trim();
  const email = document.getElementById('reg-email').value.trim();
  const password = document.getElementById('reg-password').value;
  const department = document.getElementById('reg-dept').value.trim();

  if (!name || !email || !password || !department)
    return showMsg('register-msg', 'Please fill in all fields.', 'error');

  try {
    const res = await fetch(`${API}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password, department })
    });
    const data = await res.json();
    if (res.ok) {
      showMsg('register-msg', 'Account created! You can now login.', 'success');
    } else {
      showMsg('register-msg', data.error || 'Registration failed.', 'error');
    }
  } catch {
    showMsg('register-msg', 'Cannot connect to server.', 'error');
  }
}

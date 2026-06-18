const API = CONFIG.BACKEND_URL;
let user = null, token = null;
let editingQuiz = null, questionCount = 0;

window.onload = function () {
  user = JSON.parse(localStorage.getItem('user') || 'null');
  token = localStorage.getItem('token');
  if (!user || user.role !== 'admin') return window.location.href = 'index.html';
  document.getElementById('sidebar-name').textContent = user.name;
  loadDashboard();
};

function animateCount(elId, target) {
  const el = document.getElementById(elId);
  if (!el || target === 0) return;
  let start = 0;
  const duration = 700;
  const step = timestamp => {
    if (!start) start = timestamp;
    const progress = Math.min((timestamp - start) / duration, 1);
    el.textContent = Math.floor(progress * target);
    if (progress < 1) requestAnimationFrame(step);
    else el.textContent = target;
  };
  requestAnimationFrame(step);
}

function h() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
}

function showPage(name, navEl) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  if (navEl) navEl.classList.add('active');
  if (name === 'quizzes') loadAdminQuizzes();
  if (name === 'employees') loadEmployees();
  if (name === 'results') loadAllResults();
}

function logout() { localStorage.clear(); window.location.href = 'index.html'; }

function initials(name) {
  return name ? name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0,2) : '?';
}

function bc(label) {
  if (label === 'High Performer') return 'badge-green';
  if (label === 'Average Performer') return 'badge-orange';
  if (label === 'Needs Improvement') return 'badge-red';
  return 'badge-gray';
}

function scoreColor(score) {
  if (score >= 80) return '#2f9e44';
  if (score >= 50) return '#f59f00';
  return '#e03131';
}

// ── DASHBOARD ────────────────────────────────────────────────────────────────

let adminScoreChart = null, adminPerfChart = null;

async function loadDashboard() {
  try {
    const [statsRes, recentRes] = await Promise.all([
      fetch(`${API}/admin/stats`, { headers: h() }),
      fetch(`${API}/admin/all-results`, { headers: h() })
    ]);
    const stats = await statsRes.json();
    const recentData = await recentRes.json();

    document.getElementById('k-emp').textContent = stats.total_employees || 0;
    document.getElementById('k-quiz').textContent = stats.total_quizzes || 0;
    document.getElementById('k-att').textContent = stats.total_attempts || 0;
    document.getElementById('k-avg').textContent = stats.avg_score ? stats.avg_score + '%' : '–';
    // animate numbers
    animateCount('k-emp', stats.total_employees || 0);
    animateCount('k-quiz', stats.total_quizzes || 0);
    animateCount('k-att', stats.total_attempts || 0);

    // ── Analytics Charts ───────────────────────────────────────────────────
    const results = recentData.results || [];
    if (results.length > 0) {
      // Score trend — last 10 submissions sorted by date
      const sorted = [...results].sort((a,b) => new Date(a.submitted_at) - new Date(b.submitted_at)).slice(-10);
      const scoreLabels = sorted.map(r => r.employee_name.split(' ')[0] + ' - ' + (r.quiz_title||'').slice(0,8));
      const scoreData   = sorted.map(r => r.score);

      if (adminScoreChart) adminScoreChart.destroy();
      adminScoreChart = new Chart(document.getElementById('chart-admin-scores'), {
        type: 'line',
        data: {
          labels: scoreLabels,
          datasets: [{ label: 'Score %', data: scoreData,
            borderColor: '#3b5bdb', backgroundColor: 'rgba(59,91,219,0.1)',
            tension: 0.4, fill: true, pointRadius: 4, pointBackgroundColor: '#3b5bdb' }]
        },
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{ legend:{display:false} },
          scales:{ y:{ min:0, max:100, ticks:{callback:v=>v+'%'} }, x:{ticks:{maxRotation:30,font:{size:9}}} } }
      });

      // ML Performance Distribution donut
      const perfCounts = { 'High Performer':0, 'Average Performer':0, 'Needs Improvement':0 };
      results.forEach(r => { if (perfCounts[r.performance_label] !== undefined) perfCounts[r.performance_label]++; });
      if (adminPerfChart) adminPerfChart.destroy();
      adminPerfChart = new Chart(document.getElementById('chart-admin-perf'), {
        type: 'doughnut',
        data: {
          labels: ['High', 'Average', 'Needs Work'],
          datasets: [{ data: [perfCounts['High Performer'], perfCounts['Average Performer'], perfCounts['Needs Improvement']],
            backgroundColor: ['#2f9e44','#f59f00','#e03131'],
            borderWidth: 2, borderColor: '#fff' }]
        },
        options: { responsive:true, maintainAspectRatio:false,
          plugins:{ legend:{ position:'bottom', labels:{font:{size:11}, padding:8} } } }
      });
    }

    const results = (recentData.results || []).slice(0, 6);
    const container = document.getElementById('recent-subs');
    if (results.length === 0) {
      container.innerHTML = '<div class="empty-state"><span>📭</span>No submissions yet.</div>';
    } else {
      container.innerHTML = results.map(r => `
        <div class="sub-card">
          <div class="sub-avatar">${initials(r.employee_name)}</div>
          <div>
            <div class="sub-name">${r.employee_name}</div>
            <div class="sub-quiz">${r.quiz_title}</div>
          </div>
          <div class="sub-right">
            <div class="sub-score" style="color:${scoreColor(r.score)}">${r.score}%</div>
            <span class="badge ${bc(r.performance_label)}">${r.performance_label}</span>
            <span style="font-size:12px;color:var(--muted)">${new Date(r.submitted_at).toLocaleDateString()}</span>
          </div>
        </div>`).join('');
    }
  } catch (e) { console.error(e); }
}

// ── QUIZZES ──────────────────────────────────────────────────────────────────

async function loadAdminQuizzes() {
  try {
    const res = await fetch(`${API}/quizzes`, { headers: h() });
    const data = await res.json();
    const quizzes = data.quizzes || [];
    const container = document.getElementById('quiz-list');
    if (quizzes.length === 0) {
      container.innerHTML = '<div class="empty-state"><span>📭</span>No quizzes yet.</div>';
      return;
    }
    container.innerHTML = quizzes.map(q => `
      <div class="quiz-card">
        <div class="quiz-card-info">
          <h4>${q.title}</h4>
          <p>${q.description || 'No description'} &nbsp;·&nbsp; <strong>${q.question_count}</strong> questions</p>
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn-sm btn-outline" onclick="editQuiz(${q.id})">✏️ Edit</button>
          <button class="btn-sm btn-red" onclick="deleteQuiz(${q.id})">Delete</button>
        </div>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

function openCreateQuizModal() {
  document.getElementById('modal-quiz-title').value = '';
  document.getElementById('modal-quiz-desc').value = '';
  document.getElementById('quiz-modal').style.display = 'flex';
}
function closeModal() { document.getElementById('quiz-modal').style.display = 'none'; }

async function createQuizAndEdit() {
  const title = document.getElementById('modal-quiz-title').value.trim();
  const description = document.getElementById('modal-quiz-desc').value.trim();
  if (!title) return alert('Please enter a title.');
  try {
    const res = await fetch(`${API}/admin/create-quiz`, {
      method: 'POST', headers: h(),
      body: JSON.stringify({ title, description })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.error || 'Server error ' + res.status);
    }
    const data = await res.json();
    if (!data.quiz_id) throw new Error('No quiz_id returned');
    closeModal();
    editQuiz(data.quiz_id);
  } catch (e) { alert('Failed to create quiz: ' + e.message); }
}

async function editQuiz(quizId) {
  try {
    const res = await fetch(`${API}/quiz/${quizId}`, { headers: h() });
    editingQuiz = await res.json();
    document.getElementById('edit-quiz-title').textContent = 'Edit: ' + editingQuiz.title;
    document.getElementById('quiz-title-input').value = editingQuiz.title;
    document.getElementById('quiz-desc-input').value = editingQuiz.description || '';
    questionCount = 0;
    document.getElementById('questions-editor').innerHTML = '';
    (editingQuiz.questions || []).forEach(q => addQuestion(q));
    showPage('edit-quiz');
  } catch (e) { alert('Could not load quiz.'); }
}

function addQuestion(existing) {
  questionCount++;
  const id = 'q_' + questionCount;
  const opts = existing ? existing.options : ['', '', '', ''];
  const correct = existing ? existing.correct_index : 0;
  const div = document.createElement('div');
  div.className = 'card';
  div.style.marginBottom = '12px';
  div.id = id;
  div.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
      <strong style="color:var(--primary)">Question ${questionCount}</strong>
      <button class="btn-sm btn-red" onclick="removeQuestion('${id}')">Remove</button>
    </div>
    <div class="form-group">
      <label>Question Text</label>
      <textarea class="q-text-input" placeholder="Type your question here...">${existing ? existing.question_text : ''}</textarea>
    </div>
    <label style="font-size:13px;font-weight:600;display:block;margin-bottom:8px">Options <span style="color:var(--muted);font-weight:400">(select correct answer)</span></label>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px">
      ${opts.map((o, i) => `
        <div style="display:flex;align-items:center;gap:8px;background:#f7f8fc;border:1.5px solid #dee2e6;border-radius:8px;padding:8px 10px">
          <input type="radio" name="${id}_correct" value="${i}" ${correct === i ? 'checked' : ''} title="Mark as correct" style="width:16px;height:16px;flex-shrink:0;accent-color:#3b5bdb;cursor:pointer"/>
          <input type="text" class="opt-input" placeholder="Option ${i + 1}" value="${o}" style="flex:1;border:none;background:transparent;outline:none;font-size:14px;font-family:inherit;color:#1a1a2e"/>
        </div>`).join('')}
    </div>
    <div style="font-size:12px;color:var(--muted)">🔵 = correct answer</div>`;
  document.getElementById('questions-editor').appendChild(div);
}

function removeQuestion(id) { document.getElementById(id)?.remove(); }

async function saveQuiz() {
  const title = document.getElementById('quiz-title-input').value.trim();
  const description = document.getElementById('quiz-desc-input').value.trim();
  if (!title) return alert('Quiz title is required.');
  const questionDivs = document.querySelectorAll('#questions-editor .card');
  const questions = [];
  for (const div of questionDivs) {
    const text = div.querySelector('.q-text-input')?.value.trim();
    if (!text) continue;
    const opts = [...div.querySelectorAll('.opt-input')].map(i => i.value.trim()).filter(Boolean);
    const correctEl = div.querySelector('input[type=radio]:checked');
    questions.push({ question_text: text, options: opts, correct_index: correctEl ? parseInt(correctEl.value) : 0 });
  }
  try {
    const res = await fetch(`${API}/admin/save-quiz`, {
      method: 'POST', headers: h(),
      body: JSON.stringify({ quiz_id: editingQuiz.id, title, description, questions })
    });
    if (res.ok) {
      showToast('Quiz saved successfully! ✓');
      const msg = document.getElementById('quiz-save-msg');
      msg.textContent = '✅ Quiz saved!';
      msg.className = 'msg success';
      setTimeout(() => showPage('quizzes'), 1000);
    } else { alert('Save failed.'); }
  } catch (e) { alert('Save failed.'); }
}

async function deleteQuiz(quizId) {
  if (!confirm('Delete this quiz? This cannot be undone.')) return;
  await fetch(`${API}/admin/delete-quiz/${quizId}`, { method: 'DELETE', headers: h() });
  loadAdminQuizzes();
}

// ── EMPLOYEES ────────────────────────────────────────────────────────────────

async function loadEmployees() {
  const grid = document.getElementById('emp-grid');
  grid.innerHTML = `<div style="grid-column:1/-1;padding:20px">
    ${[1,2,3].map(() => `<div style="background:#fff;border-radius:12px;padding:18px;margin-bottom:14px;border:1px solid var(--border)">
      <div style="display:flex;gap:12px;margin-bottom:14px"><div class="skeleton" style="width:44px;height:44px;border-radius:50%"></div>
      <div style="flex:1"><div class="skeleton" style="width:60%;margin-bottom:8px"></div><div class="skeleton" style="width:40%"></div></div></div>
      <div style="display:flex;gap:16px"><div class="skeleton" style="width:50px"></div><div class="skeleton" style="width:60px"></div><div class="skeleton" style="width:70px"></div></div>
    </div>`).join('')}</div>`;
  try {
    const res = await fetch(`${API}/admin/employees`, { headers: h() });
    const data = await res.json();
    const emps = data.employees || [];
    const grid = document.getElementById('emp-grid');
    if (emps.length === 0) {
      grid.innerHTML = '<div class="empty-state"><span>👥</span>No employees registered yet.</div>';
      return;
    }
    grid.innerHTML = emps.map(e => `
      <div class="emp-card">
        <div onclick="openEmployeeDetail(${e.id})" style="cursor:pointer">
          <div class="emp-card-top">
            <div class="emp-avatar">${initials(e.name)}</div>
            <div>
              <div class="emp-card-name">${e.name}</div>
              <div class="emp-card-dept">${e.email}</div>
              <div class="emp-card-dept" style="margin-top:2px">🏢 ${e.department || '–'}</div>
            </div>
          </div>
          <div class="emp-stats">
            <div class="emp-stat"><div class="emp-stat-val">${e.quiz_count}</div><div class="emp-stat-lbl">Quizzes</div></div>
            <div class="emp-stat"><div class="emp-stat-val" style="color:${scoreColor(e.avg_score||0)}">${e.avg_score ? e.avg_score + '%' : '–'}</div><div class="emp-stat-lbl">Avg Score</div></div>
            <div class="emp-stat"><span class="badge ${bc(e.performance_label)}" style="font-size:11px">${e.performance_label || '–'}</span><div class="emp-stat-lbl" style="margin-top:4px">Level</div></div>
          </div>
        </div>
        <div style="border-top:1px solid var(--border);margin-top:12px;padding-top:10px;display:flex;gap:8px">
          <button class="btn-sm btn-outline" style="flex:1" onclick="openEmployeeDetail(${e.id})">View Details</button>
          <button class="btn-sm btn-red" onclick="deleteEmployee(${e.id}, '${e.name}')">🗑 Delete</button>
        </div>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

async function deleteEmployee(empId, empName) {
  if (!confirm(`Delete employee "${empName}"?\n\nThis will also delete ALL their quiz results and cannot be undone.`)) return;
  try {
    const res = await fetch(`${API}/admin/delete-employee/${empId}`, { method: 'DELETE', headers: h() });
    if (res.ok) {
      showToast(`${empName} has been removed.`);
      loadEmployees();
      loadDashboard();
    } else {
      alert('Could not delete employee.');
    }
  } catch (e) { alert('Delete failed.'); }
}

async function deleteResult(resultId, empId) {
  if (!confirm('Delete this quiz attempt? This cannot be undone.')) return;
  try {
    await fetch(`${API}/admin/delete-result/${resultId}`, { method: 'DELETE', headers: h() });
    openEmployeeDetail(empId);
  } catch (e) { alert('Delete failed.'); }
}

async function openEmployeeDetail(empId) {
  try {
    const res = await fetch(`${API}/admin/employee/${empId}`, { headers: h() });
    const data = await res.json();
    const emp = data.employee;
    const overall = data.overall;
    const quizzes = data.quiz_summary || [];

    // Header
    document.getElementById('detail-header').innerHTML = `
      <div class="detail-avatar">${initials(emp.name)}</div>
      <div>
        <div class="detail-name">${emp.name}</div>
        <div class="detail-meta">${emp.email} &nbsp;·&nbsp; ${emp.department || '–'}</div>
      </div>
      <div class="detail-kpis">
        <div class="detail-kpi">
          <div class="detail-kpi-val">${overall.unique_quizzes}</div>
          <div class="detail-kpi-lbl">Topics</div>
        </div>
        <div class="detail-kpi">
          <div class="detail-kpi-val">${overall.total_attempts}</div>
          <div class="detail-kpi-lbl">Total Attempts</div>
        </div>
        <div class="detail-kpi">
          <div class="detail-kpi-val" style="color:${scoreColor(overall.avg_score||0)}">
            ${overall.avg_score ? overall.avg_score + '%' : '–'}
          </div>
          <div class="detail-kpi-lbl">Avg Score</div>
        </div>
        <div class="detail-kpi">
          <span class="badge ${bc(overall.performance_label)}">${overall.performance_label || '–'}</span>
          <div class="detail-kpi-lbl" style="margin-top:4px">Level</div>
        </div>
      </div>`;

    // Quiz summary table — one row per topic
    const tbody = document.getElementById('detail-table');
    if (quizzes.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No quiz attempts yet.</td></tr>';
    } else {
      tbody.innerHTML = quizzes.map(q => {
        const totalQ = q.total_questions || 0;
        const correct = Math.round((q.best_accuracy / 100) * totalQ);
        const wrong = totalQ - correct;
        return `
        <tr style="border-bottom:none">
          <td><strong>${q.quiz_title}</strong></td>
          <td>${totalQ}</td>
          <td style="color:var(--success);font-weight:700">${correct} ✓</td>
          <td style="color:var(--danger);font-weight:700">${wrong} ✗</td>
          <td><span class="score-pill" style="background:${scoreColor(q.best_score)}22;color:${scoreColor(q.best_score)}">${q.best_score}%</span></td>
          <td style="text-align:center;font-weight:700;color:var(--primary)">${q.total_attempts}</td>
          <td><span class="badge ${bc(q.performance_label)}">${q.performance_label || '–'}</span></td>
          <td>${new Date(q.last_attempted).toLocaleDateString()}</td>
        </tr>
        ${q.latest_feedback ? `
        <tr>
          <td colspan="8" style="padding:4px 14px 14px;font-size:13px;color:var(--muted);background:#fafbff;border-bottom:2px solid var(--border)">
            💬 <em>${q.latest_feedback}</em>
          </td>
        </tr>` : ''}`;
      }).join('');
    }

    document.getElementById('detail-feedback-section').innerHTML = '';
    showPage('emp-detail');
  } catch (e) { console.error(e); alert('Could not load employee details.'); }
}

// ── ALL RESULTS ───────────────────────────────────────────────────────────────

async function loadAllResults() {
  try {
    const res = await fetch(`${API}/admin/all-results`, { headers: h() });
    const data = await res.json();
    const results = data.results || [];
    const tbody = document.getElementById('all-results-table');
    if (results.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No results yet.</td></tr>';
      return;
    }
    tbody.innerHTML = results.map(r => `
      <tr>
        <td><strong>${r.employee_name}</strong></td>
        <td style="color:var(--muted);font-size:13px">${r.department || '–'}</td>
        <td>${r.quiz_title}</td>
        <td><span class="score-pill" style="background:${scoreColor(r.score)}22;color:${scoreColor(r.score)}">${r.score}%</span></td>
        <td>${r.accuracy}%</td>
        <td>${r.time_taken} min</td>
        <td><span class="badge ${bc(r.performance_label)}">${r.performance_label}</span></td>
        <td style="text-align:center">${r.total_attempts}</td>
        <td>${new Date(r.submitted_at).toLocaleDateString()}</td>
      </tr>`).join('');
  } catch (e) { console.error(e); }
}

// ── TOAST ──────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.classList.add('hide'); setTimeout(() => t.remove(), 300); }, 2800);
}
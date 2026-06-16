const API = CONFIG.BACKEND_URL;
// Anthropic API key — set via localStorage for local dev:
//   localStorage.setItem('anthropic_key', 'sk-ant-...')
// Or inject it server-side into window.ANTHROPIC_API_KEY
const ANTHROPIC_KEY = window.ANTHROPIC_API_KEY || localStorage.getItem('anthropic_key') || '';
let user = null, token = null;
let currentQuiz = null, answers = {}, currentQ = 0, startTime = null;
let isSubmitting = false;
let timerInterval = null, timeLeft = 60;
let lastResult = null;

// ── INIT ─────────────────────────────────────────────────────────────────────
window.onload = function () {
  user = JSON.parse(localStorage.getItem('user') || 'null');
  token = localStorage.getItem('token');
  if (!user || user.role !== 'employee') return window.location.href = 'index.html';
  document.getElementById('sidebar-name').textContent = user.name;
  document.getElementById('greet-name').textContent = `Welcome back, ${user.name.split(' ')[0]}!`;
  loadDashboard();
  loadQuizzes();
  loadHistory();
};

function headers() {
  return { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` };
}

function animateCount(elId, target) {
  const el = document.getElementById(elId);
  if (!el || !target) return;
  let start = 0; const dur = 700;
  const step = ts => {
    if (!start) start = ts;
    const p = Math.min((ts - start) / dur, 1);
    el.textContent = Math.floor(p * target);
    if (p < 1) requestAnimationFrame(step); else el.textContent = target;
  };
  requestAnimationFrame(step);
}

function showToast(msg, type = 'success') {
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.classList.add('hide'); setTimeout(() => t.remove(), 300); }, 2800);
}

function showPage(name, navEl) {
  stopTimer();
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  if (navEl) navEl.classList.add('active');
  if (name === 'history') loadHistory();
}

function logout() { localStorage.clear(); window.location.href = 'index.html'; }

function badgeClass(label) {
  if (label === 'High Performer') return 'badge-green';
  if (label === 'Average Performer') return 'badge-orange';
  return 'badge-red';
}

// ── DASHBOARD ─────────────────────────────────────────────────────────────────
async function loadDashboard() {
  try {
    const res = await fetch(`${API}/my-results`, { headers: headers() });
    const data = await res.json();
    const results = data.results || [];
    animateCount('stat-taken', results.length);
    if (results.length) {
      const avg = (results.reduce((s, r) => s + r.score, 0) / results.length).toFixed(1);
      document.getElementById('stat-avg').textContent = avg + '%';
      const last = results[results.length - 1];
      const lvlEl = document.getElementById('stat-level');
      lvlEl.innerHTML = `<span class="badge ${badgeClass(last.performance_label)}">${last.performance_label}</span>`;
    }
    const recent = results.slice(-5).reverse();
    document.getElementById('recent-table').innerHTML = recent.length
      ? recent.map(r => `<tr>
          <td>${r.quiz_title}</td>
          <td><strong>${r.score}%</strong></td>
          <td>${new Date(r.submitted_at).toLocaleDateString()}</td>
          <td><span class="badge ${badgeClass(r.performance_label)}">${r.performance_label}</span></td>
        </tr>`).join('')
      : '<tr><td colspan="4" class="empty-state">No attempts yet.</td></tr>';
  } catch (e) { console.error(e); }
}

// ── QUIZZES ───────────────────────────────────────────────────────────────────
async function loadQuizzes() {
  try {
    const res = await fetch(`${API}/quizzes`, { headers: headers() });
    const data = await res.json();
    const quizzes = data.quizzes || [];
    const container = document.getElementById('quiz-list-container');
    container.innerHTML = quizzes.length
      ? quizzes.map(q => `
        <div class="card" style="margin-bottom:14px;display:flex;align-items:center;justify-content:space-between;gap:16px">
          <div>
            <div style="font-weight:700;font-size:16px">${q.title}</div>
            <div style="color:var(--muted);font-size:13px;margin-top:4px">${q.description || '–'} &nbsp;·&nbsp; ${q.question_count} questions &nbsp;·&nbsp; ⏱ ${q.question_count} min</div>
          </div>
          <button class="btn-sm btn-blue" style="flex-shrink:0" onclick="startQuiz(${q.id})">Start →</button>
        </div>`).join('')
      : '<div class="empty-state"><span>📭</span>No quizzes available yet.</div>';
  } catch (e) { console.error(e); }
}

// ── QUIZ ATTEMPT ──────────────────────────────────────────────────────────────
async function startQuiz(quizId) {
  try {
    const res = await fetch(`${API}/quiz/${quizId}`, { headers: headers() });
    const data = await res.json();
    currentQuiz = data;
    answers = {};
    currentQ = 0;
    isSubmitting = false;
    startTime = Date.now();
    document.getElementById('attempt-title').textContent = data.title;
    showPage('attempt', null);
    renderQuestion();
  } catch (e) { alert('Could not load quiz.'); }
}

function renderQuestion() {
  const q = currentQuiz.questions[currentQ];
  const total = currentQuiz.questions.length;

  document.getElementById('q-count').textContent = `Question ${currentQ + 1} of ${total}`;
  document.getElementById('progress-bar').style.width = `${((currentQ + 1) / total) * 100}%`;

  document.getElementById('question-area').innerHTML = `
    <div class="question-card card" style="animation:fadeInUp 0.3s both">
      <div class="q-text" style="font-size:16px;font-weight:700;margin-bottom:16px;line-height:1.5">${currentQ + 1}. ${q.question_text}</div>
      ${q.options.map((opt, i) => `
        <div class="option ${answers[q.id] === i ? 'selected' : ''}" onclick="selectAnswer(${q.id}, ${i}, this)">
          <input type="radio" name="q${q.id}" ${answers[q.id] === i ? 'checked' : ''} style="pointer-events:none"/>
          <span>${opt}</span>
        </div>`).join('')}
    </div>`;

  document.getElementById('btn-prev').style.display = currentQ === 0 ? 'none' : '';
  const isLast = currentQ === total - 1;
  document.getElementById('btn-next').style.display = isLast ? 'none' : '';
  document.getElementById('btn-submit').style.display = isLast ? '' : 'none';

  // start per-question timer
  startTimer(60);
}

function selectAnswer(qId, idx, el) {
  answers[qId] = idx;
  document.querySelectorAll('.option').forEach(o => o.classList.remove('selected'));
  el.classList.add('selected');
  el.querySelector('input').checked = true;
}

function nextQuestion() {
  if (currentQ < currentQuiz.questions.length - 1) { currentQ++; renderQuestion(); }
}
function prevQuestion() {
  if (currentQ > 0) { currentQ--; renderQuestion(); }
}

// ── TIMER ────────────────────────────────────────────────────────────────────
function startTimer(seconds) {
  stopTimer();
  timeLeft = seconds;
  updateTimerUI();
  timerInterval = setInterval(() => {
    timeLeft--;
    updateTimerUI();
    if (timeLeft <= 0) {
      stopTimer();
      // auto-advance or submit on timeout
      const total = currentQuiz.questions.length;
      if (currentQ < total - 1) {
        showToast('Time up! Moving to next question.', 'error');
        currentQ++;
        renderQuestion();
      } else {
        showToast('Time up! Submitting quiz.', 'error');
        submitQuiz();
      }
    }
  }, 1000);
}

function stopTimer() {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
}

function updateTimerUI() {
  const pct = (timeLeft / 60) * 100;
  const bar = document.getElementById('timer-bar');
  const display = document.getElementById('timer-display');
  const text = document.getElementById('timer-text');
  if (!bar || !display || !text) return;
  text.textContent = `${timeLeft}s`;
  bar.style.width = pct + '%';
  bar.style.background = timeLeft > 30 ? 'var(--primary)' : timeLeft > 10 ? 'var(--warning)' : 'var(--danger)';
  display.className = 'timer-display' + (timeLeft <= 10 ? ' danger' : timeLeft <= 30 ? ' warning' : '');
}

// ── SUBMIT ───────────────────────────────────────────────────────────────────
async function submitQuiz() {
  if (isSubmitting) return;
  isSubmitting = true;
  stopTimer();
  // Lock the attempt page visually while we wait
  const attemptPage = document.getElementById('page-attempt');
  if (attemptPage) attemptPage.classList.add('submitting');
  const btn = document.getElementById('btn-submit');
  if (btn) { btn.disabled = true; btn.textContent = 'Submitting...'; }
  const timeTaken = Math.round((Date.now() - startTime) / 60000 * 10) / 10;
  try {
    const res = await fetch(`${API}/submit-quiz`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ quiz_id: currentQuiz.id, answers, time_taken: timeTaken })
    });
    const data = await res.json();
    console.log('[Submit] Response:', data);
    if (!res.ok) {
      if (attemptPage) attemptPage.classList.remove('submitting');
      alert('Submission error: ' + (data.error || 'Unknown error'));
      if (btn) { btn.disabled = false; btn.textContent = '✓ Submit Quiz'; }
      isSubmitting = false;
      return;
    }
    if (attemptPage) attemptPage.classList.remove('submitting');
    lastResult = { ...data, quiz: currentQuiz };
    showResult(data);
    loadDashboard();
  } catch (e) {
    if (attemptPage) attemptPage.classList.remove('submitting');
    alert('Submission failed. Please check your connection.');
    if (btn) { btn.disabled = false; btn.textContent = '✓ Submit Quiz'; }
    isSubmitting = false;
  }
}

// ── RESULT ───────────────────────────────────────────────────────────────────
function showResult(data) {
  // show page first so elements exist in DOM
  showPage('result', null);

  // small delay to let page become active
  setTimeout(() => {
    const score = data.score ?? 0;
    const label = data.performance_label ?? 'Needs Improvement';
    const correct = data.correct ?? 0;
    const wrong = data.wrong ?? 0;
    const timeTaken = data.time_taken ?? 0;
    const staticFeedback = data.feedback || 'Keep practicing — every attempt helps you improve!';

    const scoreEl = document.getElementById('res-score');
    if (scoreEl) scoreEl.textContent = score + '%';

    const tagEl = document.getElementById('res-tag');
    if (tagEl) tagEl.textContent = label;

    const correctEl = document.getElementById('res-correct');
    if (correctEl) correctEl.textContent = correct;

    const wrongEl = document.getElementById('res-wrong');
    if (wrongEl) wrongEl.textContent = wrong;

    const timeEl = document.getElementById('res-time');
    if (timeEl) timeEl.textContent = timeTaken;

    // color the hero based on score
    const hero = document.querySelector('.result-hero');
    if (hero) {
      if (score >= 80) hero.style.background = 'linear-gradient(135deg, #2f9e44 0%, #40c057 100%)';
      else if (score >= 50) hero.style.background = 'linear-gradient(135deg, #f59f00 0%, #fcc419 100%)';
      else hero.style.background = 'linear-gradient(135deg, #e03131 0%, #f03e3e 100%)';
    }

    // Show static feedback immediately, then stream AI feedback
    const fbEl = document.getElementById('res-feedback');
    if (fbEl) {
      fbEl.innerHTML = `<span style="opacity:0.7">${staticFeedback}</span>`;
    }

    // Stream real-time AI feedback
    streamAIFeedback({ score, label, correct, wrong, timeTaken, quizTitle: currentQuiz?.title || 'the quiz' });
  }, 50);
}

// ── AI FEEDBACK STREAMING ─────────────────────────────────────────────────────
async function streamAIFeedback({ score, label, correct, wrong, timeTaken, quizTitle }) {
  const fbEl = document.getElementById('res-feedback');
  const fbTitle = document.querySelector('.fb-title');
  if (!fbEl) return;

  // Show typing indicator
  fbEl.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px">
      <div style="display:flex;gap:4px">
        <span style="animation:pulse 1.2s infinite;width:7px;height:7px;background:currentColor;border-radius:50%;display:inline-block"></span>
        <span style="animation:pulse 1.2s 0.4s infinite;width:7px;height:7px;background:currentColor;border-radius:50%;display:inline-block"></span>
        <span style="animation:pulse 1.2s 0.8s infinite;width:7px;height:7px;background:currentColor;border-radius:50%;display:inline-block"></span>
      </div>
      <span>Generating your personalised feedback…</span>
    </div>`;
  if (fbTitle) fbTitle.innerHTML = '✨ AI Feedback <span style="font-size:11px;font-weight:500;opacity:0.6;margin-left:6px">Live</span>';

  try {
    // Call backend proxy — no API key needed in the browser
    const response = await fetch(`${API}/ai-feedback`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ score, label, correct, wrong, time_taken: timeTaken, quiz_title: quizTitle })
    });

    if (!response.ok) {
      const errBody = await response.json().catch(() => ({}));
      throw new Error(errBody?.error || `Server error ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';
    let started = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6).trim();
        if (!jsonStr) continue;

        try {
          const evt = JSON.parse(jsonStr);
          if (evt.error) throw new Error(evt.error);
          if (evt.text) {
            if (!started) { fbEl.textContent = ''; started = true; }
            fullText += evt.text;
            fbEl.textContent = fullText;
          }
        } catch (parseErr) {
          if (parseErr.message !== 'Unexpected end of JSON input') throw parseErr;
        }
      }
    }

    if (!fullText) throw new Error('Empty response from AI');

  } catch (err) {
    console.error('[AI Feedback]', err);
    // Graceful fallback using static feedback from submit response
    const s = lastResult?.score ?? score;
    let fallback = lastResult?.feedback || '';
    if (!fallback) {
      if (s >= 80) fallback = `Great work! You scored ${s}% and showed strong understanding of the topic. Keep it up!`;
      else if (s >= 50) fallback = `You scored ${s}% — a solid attempt. Review the questions you missed to push your score higher.`;
      else fallback = `You scored ${s}% this time. Don't be discouraged — revisiting the material before your next attempt will make a real difference.`;
    }
    fbEl.textContent = fallback;
    if (fbTitle) fbTitle.textContent = '📝 Feedback';
  }
}

function retryQuiz() {
  if (currentQuiz) startQuiz(currentQuiz.id);
}

function goBackToQuizzes() {
  // Reset quiz state so a fresh start is clean
  currentQuiz = null;
  answers = {};
  currentQ = 0;
  isSubmitting = false;
  lastResult = null;
  showPage('quizzes', document.querySelector('.nav-item:nth-child(2)'));
}

// ── REVIEW ───────────────────────────────────────────────────────────────────
function showReview() {
  if (!lastResult || !lastResult.quiz) return;
  const quiz = lastResult.quiz;
  document.getElementById('review-subtitle').textContent =
    `${quiz.title} — You scored ${lastResult.score}%`;

  const container = document.getElementById('review-container');
  container.innerHTML = quiz.questions.map((q, idx) => {
    const userAns = answers[q.id];
    const isCorrect = userAns === q.correct_index;
    return `
      <div class="review-item" style="animation-delay:${idx * 0.06}s">
        <div class="r-question">${idx + 1}. ${q.question_text}</div>
        ${q.options.map((opt, i) => {
          let cls = 'neutral', icon = '○';
          if (i === q.correct_index) { cls = 'correct'; icon = '✓'; }
          else if (i === userAns && !isCorrect) { cls = 'wrong'; icon = '✗'; }
          return `<div class="review-opt ${cls}">
            <span class="r-icon">${icon}</span>
            <span>${opt}</span>
            ${i === q.correct_index ? '<span style="margin-left:auto;font-size:11px;opacity:0.7">Correct answer</span>' : ''}
            ${i === userAns && !isCorrect ? '<span style="margin-left:auto;font-size:11px;opacity:0.7">Your answer</span>' : ''}
          </div>`;
        }).join('')}
      </div>`;
  }).join('');

  showPage('review', null);
}

// ── HISTORY ───────────────────────────────────────────────────────────────────
async function loadHistory() {
  try {
    const res = await fetch(`${API}/my-results`, { headers: headers() });
    const data = await res.json();
    const results = (data.results || []).reverse();
    const container = document.getElementById('history-container');
    if (!results.length) {
      container.innerHTML = '<div class="empty-state"><span>📭</span>No results yet.</div>';
      return;
    }
    container.innerHTML = results.map(r => `
      <div class="card" style="margin-bottom:12px;display:flex;align-items:center;gap:16px;justify-content:space-between">
        <div style="flex:1">
          <div style="font-weight:700;font-size:15px">${r.quiz_title}</div>
          <div style="font-size:13px;color:var(--muted);margin-top:3px">
            ${new Date(r.submitted_at).toLocaleDateString()} &nbsp;·&nbsp;
            Attempt #${r.attempt_number} &nbsp;·&nbsp; ${r.time_taken} min
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:12px;flex-shrink:0">
          <div style="text-align:center">
            <div style="font-size:22px;font-weight:800;color:var(--primary)">${r.score}%</div>
            <div style="font-size:11px;color:var(--muted)">${r.correct_count || '–'}/${r.total_questions || '–'} correct</div>
          </div>
          <span class="badge ${badgeClass(r.performance_label)}">${r.performance_label}</span>
          <button class="btn-sm btn-outline" onclick="openHistoryReview(${r.quiz_id}, ${JSON.stringify(r).replace(/"/g,'&quot;')})">Review</button>
        </div>
      </div>`).join('');
  } catch (e) { console.error(e); }
}

async function openHistoryReview(quizId, result) {
  try {
    const res = await fetch(`${API}/quiz/${quizId}`, { headers: headers() });
    const quiz = await res.json();

    // Parse stored user answers: {"question_id": selected_index, ...}
    let userAnswers = {};
    try { userAnswers = JSON.parse(result.user_answers || '{}'); } catch (_) {}

    document.getElementById('review-subtitle').textContent =
      `${quiz.title} — Score: ${result.score}% (${result.correct_count || '?'}/${result.total_questions || '?'} correct)`;

    const container = document.getElementById('review-container');
    container.innerHTML = quiz.questions.map((q, idx) => {
      const userAns = userAnswers[String(q.id)];
      const isCorrect = userAns !== undefined && Number(userAns) === q.correct_index;
      const skipped = userAns === undefined || userAns === null;

      return `
        <div class="review-item" style="animation-delay:${idx * 0.06}s">
          <div class="r-question" style="display:flex;align-items:center;gap:8px">
            <span>${idx + 1}. ${q.question_text}</span>
            <span style="margin-left:auto;font-size:12px;padding:2px 8px;border-radius:12px;font-weight:600;flex-shrink:0;
              background:${isCorrect ? '#d3f9d8' : skipped ? '#f1f3f5' : '#ffe3e3'};
              color:${isCorrect ? '#2f9e44' : skipped ? '#868e96' : '#e03131'}">
              ${isCorrect ? '✓ Correct' : skipped ? '— Skipped' : '✗ Wrong'}
            </span>
          </div>
          ${q.options.map((opt, i) => {
            const isUserPick = !skipped && Number(userAns) === i;
            const isRightAns = i === q.correct_index;

            let cls = 'neutral', icon = '○';
            if (isUserPick && isRightAns)  { cls = 'correct'; icon = '✓'; }
            else if (isUserPick && !isRightAns) { cls = 'wrong'; icon = '✗'; }
            else if (isRightAns)           { cls = 'correct'; icon = '✓'; }

            return `<div class="review-opt ${cls}">
              <span class="r-icon">${icon}</span>
              <span>${opt}</span>
              <span style="margin-left:auto;font-size:11px;opacity:0.75;white-space:nowrap">
                ${isUserPick && isRightAns ? 'Your answer · Correct' :
                  isUserPick ? 'Your answer' :
                  isRightAns ? 'Correct answer' : ''}
              </span>
            </div>`;
          }).join('')}
        </div>`;
    }).join('');

    showPage('review', null);
  } catch (e) { alert('Could not load quiz for review.'); }
}
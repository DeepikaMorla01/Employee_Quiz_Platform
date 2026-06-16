# WorkEval – Employee Assessment Platform

A web-based employee quiz and assessment system with performance prediction and personalized feedback.

---

## Project Overview

WorkEval lets HR teams create quizzes and assess employee knowledge. After each quiz, the system predicts the employee's performance level and generates personalized feedback.

**Key features:**
- Employee registration and login
- Admin panel to create and manage quizzes
- Quiz attempt with automatic scoring
- Performance prediction (High / Average / Needs Improvement)
- Personalized feedback generation via Gemini API

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, Flask |
| Database | SQLite |
| Prediction | Scikit-learn (Random Forest) |
| Feedback | Google Gemini API |

---

## Project Structure

```
EmployeeQuizPlatform/
├── Frontend/
│   ├── index.html       → Login / Register page
│   ├── employee.html    → Employee dashboard
│   ├── admin.html       → Admin / HR dashboard
│   ├── style.css        → All styles
│   ├── auth.js          → Login/Register logic
│   ├── employee.js      → Employee dashboard logic
│   └── admin.js         → Admin dashboard logic
│
├── Backend/
│   ├── app.py           → Flask API (all routes)
│   ├── ml_predictor.py  → Performance prediction module
│   ├── feedback_generator.py → Feedback via Gemini API
│   └── requirements.txt
│
└── ML/
    ├── train_model.py   → Model training script
    ├── employee_data.csv → Dataset (auto-generated on first run)
    └── model.pkl         → Saved model (created after training)
```

---

## Setup Instructions

### Step 1 – Train the model

```bash
cd ML
python train_model.py
```

This generates `employee_data.csv` and saves `model.pkl`. Copy `model.pkl` to the `ML/` folder (it's already there after training).

### Step 2 – Install backend dependencies

```bash
cd Backend
pip install -r requirements.txt
```

### Step 3 – Set Gemini API key (optional)

```bash
# Windows
set GEMINI_API_KEY=your_key_here

# Mac/Linux
export GEMINI_API_KEY=your_key_here
```

If no key is set, the system uses pre-written feedback templates.

### Step 4 – Start the backend

```bash
cd Backend
python app.py
```

Backend runs at: `http://localhost:5000`

### Step 5 – Open the frontend

Open `Frontend/index.html` in your browser. Or use Live Server in VS Code.

---

## Default Login

| Role | Email | Password |
|------|-------|----------|
| Admin / HR | admin@workeval.com | admin123 |

Register a new employee account from the login page.

---

## How It Works

1. Admin creates a quiz with MCQ questions
2. Employee logs in and takes the quiz
3. System scores the quiz automatically
4. Random Forest model predicts performance level
5. Gemini API generates personalized feedback
6. Results are stored and shown on dashboards

---

## Evaluation Notes

- ML model: Random Forest with 5 input features (score, accuracy, time, attempts, previous average)
- Fallback: Rule-based prediction if model file is missing
- GenAI: Gemini 1.5 Flash for feedback; static templates as fallback
- No hardcoded outputs — all predictions and feedback are dynamic

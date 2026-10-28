# AI-Powered Technical Interview Coach with Rubric-Based Feedback & Code Evaluation

---

## 🌟 Overview
**TechInterview Coach AI** is an autonomous, full-stack technical interview preparation and evaluation platform. It bridges the gap between passive online judges (LeetCode/HackerRank) and real human interviewers by combining:

1. **Socratic AI Interviewer:** Progressive pedagogical hints without leaking full code.
2. **Subprocess Test Sandbox:** Dynamic execution with timeouts and security defenses.
3. **Static AST Code Analyzer:** Cyclomatic complexity, loop nesting depth, and recursion tracking.
4. **Hybrid RAG Pipeline:** BM25 lexical + dense semantic search grounding rubric evaluation against FAANG benchmarks.
5. **LLM-as-a-Judge 5-Dimensional Rubric Engine:** Weighted scoring, interactive Canvas Radar Chart, and actionable improvement roadmaps.

---

## 🚀 Quickstart (Zero External Dependencies Required!)

The system is engineered using the Python 3 standard library. You can start the server with **no pip installations**:

```bash
# Navigate to the project directory
cd /Users/abhaygupta/.gemini/antigravity/scratch/ai-interview-coach

# Run the project
python3 run.py
```

Then open your browser at **`http://127.0.0.1:8080`**.

---

## 🧪 Running Automated Unit Tests

To run the unit test suite verifying the AST analyzer, code executor, security filters, and RAG engine:

```bash
python3 tests/test_engine.py
```

---

## 📂 Project Structure

```
ai-interview-coach/
├── core/
│   ├── __init__.py
│   ├── rubric.py          # 5-Dimensional rubric schema & scoring weights
│   ├── ast_analyzer.py    # Static AST parser (Cyclomatic complexity, recursion, Big-O)
│   ├── code_executor.py   # Subprocess sandbox with timeouts & security filters
│   ├── rag_engine.py      # BM25 + Semantic RAG retriever over rubrics
│   └── llm_evaluator.py   # Gemini API integration & Deterministic Local Engine
├── data/
│   └── questions.json     # Coding problems, test suites, and rubric benchmarks
├── web/
│   ├── server.py          # Zero-dependency HTTP REST & API server
│   └── static/
│       ├── index.html     # Modern glassmorphism UI with presentation tabs
│       ├── styles.css     # Cyber-academic dark mode theme
│       └── app.js         # Interactive controller & Canvas Radar Chart generator
├── tests/
│   └── test_engine.py     # Automated test suite
├── seminar_kit/
│   ├── SLIDES_PRESENTATION.md # Exact 10-Minute Slide Deck script (09:00-09:10)
│   ├── VIVA_DEFENSE_QA.md     # 15 High-impact seminar defense questions & answers
│   └── SEMINAR_REPORT.md      # Formal academic seminar project report
├── run.py                 # Single-command launcher
├── requirements.txt       # Optional extended packages (google-genai)
└── README.md              # Project documentation
```

---

## 📊 The 5-Dimensional Rubric

| Dimension | Weight | Description |
|---|---|---|
| **Algorithmic Correctness & Edge Cases** | **30%** | Public & hidden unit test verification, null/empty bounds, duplicate values. |
| **Time & Space Complexity** | **20%** | Asymptotic Big-O optimality, loop nesting depth, auxiliary memory. |
| **Code Quality, Modularity & Style** | **20%** | Cyclomatic complexity, naming conventions, docstrings, clean abstractions. |
| **Problem Solving Approach** | **15%** | Pattern identification (Hash Table, Two Pointers, DP, Intervals). |
| **Communication & Articulation** | **15%** | Candidate thought process, Socratic responsiveness, clarity of explanation. |

---

## 🎓 Seminar Presentation Tips for Abhay Gupta

1. **Timing:** Keep presentation to strictly 8 minutes, leaving 2 minutes for faculty Q&A.
2. **Demo Flow:**
   - Select *Two Sum* in the **Interview Arena**.
   - Run tests to show the **Sandboxed Subprocess Runner**.
   - Show the **Socratic Interviewer** giving a hint without leaking the code.
   - Click **Submit for Rubric Evaluation** and showcase the **Canvas Radar Chart** in the **Rubric Scorecard** tab.
   - Switch to the **RAG Architecture** tab to demonstrate why grounding prevents hallucination.
3. **Viva Prep:** Study `seminar_kit/VIVA_DEFENSE_QA.md` for answers to examiner questions on prompt injection, sandboxing, and RAG.

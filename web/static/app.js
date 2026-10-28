/**
 * Interactive Frontend Controller for AI Technical Interview Coach.
 * Handles state, code execution, AST static metrics, Socratic chat,
 * Canvas Radar Chart visualization, RAG retrieval inspection, and Seminar timer.
 */

const state = {
  currentQuestionId: "two-sum",
  questions: [],
  currentQuestionData: null,
  chatHistory: [],
  lastEvalResult: null,
  stopwatchSeconds: 0,
  stopwatchInterval: null,
  userCodeMap: {}
};

// --- Global Navigation & Helper Functions (Called from HTML buttons) ---
window.navigateToTab = function(tabId) {
  const btn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
  if (btn) {
    btn.click();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
};

window.launchProblemFromHome = async function(qId) {
  window.navigateToTab('tab-arena');
  await selectQuestion(qId);
};

// Global helper for Reset Code button
window.resetEditorCode = function() {
  if (state.currentQuestionData) {
    const starter = state.currentQuestionData.starter_code || "";
    const editor = document.getElementById("code-editor");
    if (editor) editor.value = starter;
    if (state.currentQuestionId) {
      delete state.userCodeMap[state.currentQuestionId];
      try { localStorage.removeItem("user_code_" + state.currentQuestionId); } catch(e){}
    }
  }
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
  setupTabs();
  setupEventListeners();
  loadQuestions();
  checkSystemStatus();
});

function setupTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      tabBtns.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) targetPane.classList.add("active");

      // Redraw radar chart if switching to evaluation tab
      if (targetId === "tab-eval" && state.lastEvalResult) {
        drawRadarChart(state.lastEvalResult.dimension_scores);
      }

      // Refresh RAG chunks when opening RAG tab
      if (targetId === "tab-rag") {
        inspectRAG(state.currentQuestionId);
      }
    });
  });
}

function setupEventListeners() {
  const qSelect = document.getElementById("question-selector");
  if (qSelect) {
    qSelect.addEventListener("change", (e) => {
      selectQuestion(e.target.value);
    });
  }

  const runBtn = document.getElementById("btn-run-tests");
  if (runBtn) runBtn.addEventListener("click", runTests);

  const evalBtn = document.getElementById("btn-evaluate");
  if (evalBtn) evalBtn.addEventListener("click", runFullEvaluation);

  // Reset Code in Editor Button
  const resetCodeBtn = document.getElementById("btn-reset-code");
  if (resetCodeBtn) {
    resetCodeBtn.addEventListener("click", () => {
      window.resetEditorCode();
      const outDiv = document.getElementById("test-runner-output");
      if (outDiv) {
        outDiv.innerHTML = '<span style="color: var(--accent-cyan);">🔄 Code reset to canonical starter template. Local changes cleared.</span>';
      }
    });
  }

  // Reset Questions to Defaults Button
  const resetQBtn = document.getElementById("btn-reset-questions");
  if (resetQBtn) {
    resetQBtn.addEventListener("click", async () => {
      try {
        await fetch("/api/questions/reset", { method: "POST" });
        await loadQuestions("two-sum");
        alert("✨ Reset back to standard 9 FAANG problems! 'Two Sum' selected.");
      } catch (err) {
        alert("Error resetting questions: " + err.message);
      }
    });
  }

  const chatInput = document.getElementById("chat-input");
  const chatSendBtn = document.getElementById("btn-chat-send");
  if (chatSendBtn && chatInput) {
    chatSendBtn.addEventListener("click", () => sendChatMessage());
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") sendChatMessage();
    });
  }

  // Quick hint buttons
  document.querySelectorAll(".quick-hint-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-prompt");
      sendChatMessage(prompt);
    });
  });

  // Settings modal
  const settingsBtn = document.getElementById("btn-settings");
  const modal = document.getElementById("settings-modal");
  const closeBtn = document.getElementById("btn-close-modal");
  const saveKeyBtn = document.getElementById("btn-save-key");
  const testConnBtn = document.getElementById("btn-test-connection");

  if (settingsBtn && modal) {
    settingsBtn.addEventListener("click", () => { modal.style.display = "flex"; });
  }
  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => { modal.style.display = "none"; });
  }

  if (testConnBtn) {
    testConnBtn.addEventListener("click", async () => {
      const statusDiv = document.getElementById("test-connection-status");
      const keyVal = document.getElementById("gemini-api-key-input").value.trim();
      const modelVal = document.getElementById("gemini-model-select").value;

      testConnBtn.disabled = true;
      testConnBtn.innerHTML = "⏳ Testing...";
      if (statusDiv) statusDiv.innerHTML = '<span style="color: var(--accent-cyan);">Connecting to Google Gemini API...</span>';

      try {
        const res = await fetch("/api/test-connection", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: keyVal, model: modelVal })
        });
        const data = await res.json();
        if (data.success) {
          statusDiv.innerHTML = `<span style="color: var(--accent-emerald); font-weight: 600;">🟢 ${data.status} (${data.latency_ms}ms)</span> - ${data.message}`;
        } else {
          statusDiv.innerHTML = `<span style="color: var(--accent-rose); font-weight: 600;">🔴 ${data.status}</span> - ${data.message}`;
        }
      } catch (err) {
        if (statusDiv) statusDiv.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
      } finally {
        testConnBtn.disabled = false;
        testConnBtn.innerHTML = "🧪 Test Connection";
      }
    });
  }

  if (saveKeyBtn && modal) {
    saveKeyBtn.addEventListener("click", async () => {
      const keyVal = document.getElementById("gemini-api-key-input").value.trim();
      const modelVal = document.getElementById("gemini-model-select").value;

      try {
        const res = await fetch("/api/config", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ api_key: keyVal, model: modelVal, provider_mode: "gemini_cloud" })
        });
        const data = await res.json();
        updateProviderUI(data);
        modal.style.display = "none";
        alert("✅ Google Gemini AI settings saved! Model: " + (modelVal || "Gemini 2.5 Flash"));
      } catch (err) {
        alert("Error saving config: " + err.message);
      }
    });
  }

  // Quick Sample Note buttons in RAG Tab
  const sampleFaangBtn = document.getElementById("btn-sample-faang-rubric");
  if (sampleFaangBtn) {
    sampleFaangBtn.addEventListener("click", () => {
      document.getElementById("rag-upload-filename").value = "faang_grading_rubric.md";
      document.getElementById("rag-upload-content").value = 
`# FAANG Engineering Interview Rubric Addendum
Candidates must explain time complexity before typing code.
For Two Sum and Array questions:
- Optimal solution requires a single-pass hash map with O(N) time and O(N) auxiliary space.
- Deduct 20% on Complexity if candidate uses nested loops resulting in O(N^2) quadratic time.
- Verify edge cases: negative integer complements, duplicate numbers, and empty array inputs.`;
    });
  }

  const sampleCleanBtn = document.getElementById("btn-sample-clean-code");
  if (sampleCleanBtn) {
    sampleCleanBtn.addEventListener("click", () => {
      document.getElementById("rag-upload-filename").value = "concurrency_guidelines.md";
      document.getElementById("rag-upload-content").value = 
`# Concurrency & Distributed Systems Interview Invariants
When evaluating LRU Cache and Data Structures:
- Candidate must state thread-safety assumptions (e.g. mutex locking vs concurrent read locks).
- Fast O(1) get and put operations require combining a hash map with a doubly linked list.
- Eviction of least recently used item must update head and tail pointers in O(1) without memory leaks.`;
    });
  }

  // Document Ingestion in RAG Tab
  const uploadBtn = document.getElementById("btn-submit-rag-upload");
  if (uploadBtn) {
    uploadBtn.addEventListener("click", async () => {
      const content = document.getElementById("rag-upload-content").value.trim();
      const filename = document.getElementById("rag-upload-filename").value.trim() || "interview_notes.md";
      const statusDiv = document.getElementById("rag-ingest-status");

      if (!content) {
        alert("Please paste or type document text/markdown to ingest.");
        return;
      }

      uploadBtn.disabled = true;
      uploadBtn.textContent = "⏳ Chunking & Indexing...";
      if (statusDiv) statusDiv.innerHTML = `<span style="color: var(--accent-cyan);">Splitting into semantic chunks and indexing BM25 + vector embeddings...</span>`;

      try {
        const res = await fetch("/api/rag-upload", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ filename: filename, content: content, category: "Uploaded Rubric" })
        });
        const data = await res.json();
        if (data.success) {
          const meta = data.ingest_meta;
          if (statusDiv) {
            statusDiv.innerHTML = `<span style="color: var(--accent-emerald); font-weight: 600;">✅ Ingested "${meta.filename}"</span>: Created ${meta.chunks_created} semantic chunks (${meta.total_words} words). Total corpus chunks: ${data.total_indexed_chunks}.`;
          }
          document.getElementById("rag-upload-content").value = "";
          inspectRAG(state.currentQuestionId);
        } else {
          if (statusDiv) statusDiv.innerHTML = `<span style="color: var(--accent-rose);">❌ ${data.error}</span>`;
        }
      } catch (err) {
        if (statusDiv) statusDiv.innerHTML = `<span style="color: var(--accent-rose);">Error: ${err.message}</span>`;
      } finally {
        uploadBtn.disabled = false;
        uploadBtn.textContent = "📥 Ingest & Chunk Document";
      }
    });
  }

  // RAG ON vs RAG OFF Comparison Button
  const compareBtn = document.getElementById("btn-run-rag-compare");
  if (compareBtn) {
    compareBtn.addEventListener("click", async () => {
      const box = document.getElementById("rag-compare-box");
      const contentDiv = document.getElementById("rag-compare-content");
      const code = document.getElementById("code-editor").value;

      if (box) box.style.display = "block";
      if (contentDiv) contentDiv.innerHTML = `<span style="color: var(--accent-cyan);">⚡ Running dual comparative evaluation: Ungrounded Naive vs RAG-Grounded...</span>`;

      try {
        const res = await fetch("/api/rag-compare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question_id: state.currentQuestionId, code: code })
        });
        const data = await res.json();

        contentDiv.innerHTML = `
          <div style="margin-bottom: 1rem; padding: 0.75rem; background: rgba(99, 102, 241, 0.1); border-left: 3px solid var(--accent-indigo); border-radius: 6px; font-size: 0.85rem; color: #cbd5e1;">
            <strong>Comparative Benchmark for "${data.problem}":</strong> ${data.comparative_analysis}
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.25rem;">
            <!-- RAG OFF Card -->
            <div style="background: rgba(244, 63, 94, 0.06); border: 1px solid rgba(244, 63, 94, 0.25); border-radius: 8px; padding: 1.2rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <strong style="color: var(--accent-rose); font-size: 0.95rem;">❌ RAG OFF: Naive Prompting</strong>
                <span class="badge" style="background: rgba(244, 63, 94, 0.2); color: #fda4af;">Zero-Shot</span>
              </div>
              <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.6;">
                <div style="margin-bottom: 0.4rem;"><strong>Context Chunks:</strong> 0 chunks injected</div>
                <div style="margin-bottom: 0.4rem;"><strong>Hallucination Risk:</strong> <span style="color: var(--accent-rose); font-weight: bold;">${data.rag_off.hallucination_rate}</span></div>
                <div style="margin-bottom: 0.4rem;"><strong>Target Big-O Anchor:</strong> ${data.rag_off.complexity_anchor}</div>
                <div style="margin-bottom: 0.4rem;"><strong>Scoring Stability:</strong> ${data.rag_off.scoring_stability}</div>
                <div style="margin-bottom: 0.6rem;"><strong>Citations:</strong> <span style="color: var(--text-muted);">${data.rag_off.citations.join(", ")}</span></div>
                <div style="background: rgba(0,0,0,0.3); padding: 0.6rem; border-radius: 6px; font-style: italic; font-size: 0.8rem; color: #94a3b8;">
                  "${data.rag_off.example_feedback}"
                </div>
              </div>
            </div>

            <!-- RAG ON Card -->
            <div style="background: rgba(16, 185, 129, 0.06); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; padding: 1.2rem;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                <strong style="color: var(--accent-emerald); font-size: 0.95rem;">✅ RAG ON: Grounded Evaluation</strong>
                <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #6ee7b7;">Hybrid BM25 + Cosine</span>
              </div>
              <div style="font-size: 0.82rem; color: #cbd5e1; line-height: 1.6;">
                <div style="margin-bottom: 0.4rem;"><strong>Context Chunks:</strong> ${data.rag_on.retrieved_chunks_count} verified rubric chunks</div>
                <div style="margin-bottom: 0.4rem;"><strong>Hallucination Risk:</strong> <span style="color: var(--accent-emerald); font-weight: bold;">${data.rag_on.hallucination_rate}</span></div>
                <div style="margin-bottom: 0.4rem;"><strong>Target Big-O Anchor:</strong> <code style="color: var(--accent-cyan);">${data.rag_on.complexity_anchor}</code></div>
                <div style="margin-bottom: 0.4rem;"><strong>Scoring Stability:</strong> ${data.rag_on.scoring_stability}</div>
                <div style="margin-bottom: 0.6rem;"><strong>Grounded Citations:</strong> <br><span style="color: var(--accent-emerald); font-family: var(--font-mono); font-size: 0.75rem;">${data.rag_on.citations.map(c => `• ${c}`).join("<br>")}</span></div>
                <div style="background: rgba(0,0,0,0.3); padding: 0.6rem; border-radius: 6px; font-style: italic; font-size: 0.8rem; color: #94a3b8;">
                  "${data.rag_on.example_feedback}"
                </div>
              </div>
            </div>
          </div>
        `;
      } catch (err) {
        if (contentDiv) contentDiv.innerHTML = `<span style="color: var(--accent-rose);">Comparison error: ${err.message}</span>`;
      }
    });
  }

  // Custom Problem Modal
  const openCustomBtn = document.getElementById("btn-open-custom-modal");
  const customModal = document.getElementById("custom-problem-modal");
  const closeCustomBtn = document.getElementById("btn-close-custom-modal");
  const saveCustomBtn = document.getElementById("btn-save-custom-q");

  if (openCustomBtn && customModal) {
    openCustomBtn.addEventListener("click", () => { customModal.style.display = "flex"; });
  }
  if (closeCustomBtn && customModal) {
    closeCustomBtn.addEventListener("click", () => { customModal.style.display = "none"; });
  }

  // Quick Template auto-fill buttons inside custom problem modal
  document.querySelectorAll(".q-template-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const type = btn.getAttribute("data-template");
      if (type === "twosum") {
        document.getElementById("custom-q-title").value = "Custom Two Sum";
        document.getElementById("custom-q-difficulty").value = "Easy";
        document.getElementById("custom-q-category").value = "Arrays & Hashing";
        document.getElementById("custom-q-time").value = "O(N)";
        document.getElementById("custom-q-space").value = "O(N)";
        document.getElementById("custom-q-desc").value = "Find two indices in nums that sum to target.";
        document.getElementById("custom-q-entrypoint").value = "two_sum";
        document.getElementById("custom-q-tests").value = JSON.stringify([
          {"id": 1, "input_args": [[2, 7, 11, 15], 9], "expected": [0, 1]},
          {"id": 2, "input_args": [[3, 2, 4], 6], "expected": [1, 2]}
        ], null, 2);
      } else if (type === "palindrome") {
        document.getElementById("custom-q-title").value = "Custom Palindrome";
        document.getElementById("custom-q-difficulty").value = "Easy";
        document.getElementById("custom-q-category").value = "Strings";
        document.getElementById("custom-q-time").value = "O(N)";
        document.getElementById("custom-q-space").value = "O(1)";
        document.getElementById("custom-q-desc").value = "Check if string s is a palindrome.";
        document.getElementById("custom-q-entrypoint").value = "is_palindrome";
        document.getElementById("custom-q-tests").value = JSON.stringify([
          {"id": 1, "input_args": ["racecar"], "expected": true},
          {"id": 2, "input_args": ["hello"], "expected": false}
        ], null, 2);
      } else if (type === "math") {
        document.getElementById("custom-q-title").value = "Square Number";
        document.getElementById("custom-q-difficulty").value = "Easy";
        document.getElementById("custom-q-category").value = "Math";
        document.getElementById("custom-q-time").value = "O(1)";
        document.getElementById("custom-q-space").value = "O(1)";
        document.getElementById("custom-q-desc").value = "Return square of n.";
        document.getElementById("custom-q-entrypoint").value = "square";
        document.getElementById("custom-q-tests").value = JSON.stringify([
          {"id": 1, "input_args": [4], "expected": 16},
          {"id": 2, "input_args": [5], "expected": 25}
        ], null, 2);
      }
    });
  });

  if (saveCustomBtn && customModal) {
    saveCustomBtn.addEventListener("click", async () => {
      const title = document.getElementById("custom-q-title").value.trim() || "Custom Problem";
      const diff = document.getElementById("custom-q-difficulty").value;
      const cat = document.getElementById("custom-q-category").value.trim() || "Custom";
      const time = document.getElementById("custom-q-time").value.trim() || "O(N)";
      const space = document.getElementById("custom-q-space").value.trim() || "O(1)";
      const desc = document.getElementById("custom-q-desc").value.trim() || "Custom coding challenge.";
      const entry = document.getElementById("custom-q-entrypoint").value.trim() || "solution";

      let testCases = [];
      try {
        testCases = JSON.parse(document.getElementById("custom-q-tests").value.trim());
      } catch (e) {
        testCases = [{"id": 1, "input_args": ["racecar"], "expected": true}];
      }

      // Ensure every test case has the entrypoint assigned
      testCases.forEach((tc, i) => {
        tc.id = tc.id || (i + 1);
        tc.entrypoint = tc.entrypoint || entry;
      });

      const qId = "custom-" + Date.now();
      const payload = {
        question: {
          id: qId,
          title: title,
          difficulty: diff,
          category: cat,
          optimal_time: time,
          optimal_space: space,
          description: desc,
          entrypoint: entry,
          function_signature: `def ${entry}(*args):`,
          starter_code: `def ${entry}(*args):\n    # TODO: Write your ${title} solution here\n    pass\n`,
          test_cases: testCases,
          rubric_benchmark: {
            key_insight: `Solve ${title} within ${time} and ${space}.`,
            common_mistakes: ["Overcomplicating the state transition", "Missing edge inputs"],
            algorithmic_correctness_criteria: "Passes unit test cases and boundary conditions.",
            time_complexity_criteria: `Target optimal time is ${time}.`,
            space_complexity_criteria: `Target optimal auxiliary space is ${space}.`
          }
        }
      };

      try {
        const res = await fetch("/api/questions/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        customModal.style.display = "none";
        await loadQuestions(qId);
        alert(`🎉 Problem "${title}" dynamically added and vector-indexed into RAG!`);
      } catch (err) {
        alert("Error adding question: " + err.message);
      }
    });
  }

  // Code editor auto-save and Tab key support
  const editor = document.getElementById("code-editor");
  if (editor) {
    editor.addEventListener("input", function() {
      if (state.currentQuestionId) {
        state.userCodeMap[state.currentQuestionId] = this.value;
        try { localStorage.setItem("user_code_" + state.currentQuestionId, this.value); } catch(e){}
      }
    });

    editor.addEventListener("keydown", function(e) {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value = this.value.substring(0, start) + "    " + this.value.substring(end);
        this.selectionStart = this.selectionEnd = start + 4;
        if (state.currentQuestionId) {
          state.userCodeMap[state.currentQuestionId] = this.value;
          try { localStorage.setItem("user_code_" + state.currentQuestionId, this.value); } catch(e){}
        }
      }
    });
  }
}

// --- Check System Status (Provider Mode & Masked Key) ---
async function checkSystemStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateProviderUI(data);
  } catch (err) {
    console.warn("Could not check system status:", err);
  }
}

function updateProviderUI(data) {
  const pill = document.getElementById("active-provider-pill");
  const dot = document.getElementById("active-provider-dot");
  const text = document.getElementById("active-provider-text");
  const keyInput = document.getElementById("gemini-api-key-input");
  const modelSelect = document.getElementById("gemini-model-select");

  if (modelSelect && data.model) modelSelect.value = data.model;
  if (keyInput && data.masked_key) {
    keyInput.placeholder = data.masked_key;
  }

  const modelLabel = data.model ? data.model.replace("gemini-", "Gemini ") : "Gemini 2.5 Flash";

  if (data.has_gemini_api_key) {
    if (pill) {
      pill.style.background = "rgba(16, 185, 129, 0.15)";
      pill.style.color = "#34d399";
      pill.style.borderColor = "rgba(16, 185, 129, 0.4)";
    }
    if (dot) dot.style.background = "#10b981";
    if (text) text.textContent = `${modelLabel} Connected`;
  } else {
    if (pill) {
      pill.style.background = "rgba(245, 158, 11, 0.15)";
      pill.style.color = "#fbbf24";
      pill.style.borderColor = "rgba(245, 158, 11, 0.4)";
    }
    if (dot) dot.style.background = "#f59e0b";
    if (text) text.textContent = `Gemini API Key Required (Click ⚙️)`;
  }
}

// --- Data Loading ---
async function loadQuestions(selectedId = null) {
  try {
    const res = await fetch("/api/questions");
    const data = await res.json();
    state.questions = data.questions || [];

    const select = document.getElementById("question-selector");
    if (select) {
      select.innerHTML = state.questions.map(q => 
        `<option value="${q.id}">[${q.difficulty}] ${q.title}</option>`
      ).join("");
    }

    const targetId = selectedId || (state.questions.length > 0 ? state.questions[0].id : null);
    if (targetId) {
      selectQuestion(targetId);
    }
  } catch (err) {
    console.error("Failed to load questions:", err);
  }
}

async function selectQuestion(qId) {
  state.currentQuestionId = qId;
  const select = document.getElementById("question-selector");
  if (select && select.value !== qId) {
    select.value = qId;
  }
  try {
    const res = await fetch(`/api/questions/${qId}`);
    const qData = await res.json();
    state.currentQuestionData = qData;

    // Update UI elements
    document.getElementById("problem-title").textContent = qData.title;
    document.getElementById("problem-desc").textContent = qData.description;
    document.getElementById("target-time").textContent = qData.optimal_time;
    document.getElementById("target-space").textContent = qData.optimal_space;
    document.getElementById("problem-category").textContent = qData.category;

    const diffBadge = document.getElementById("difficulty-badge");
    diffBadge.textContent = qData.difficulty;
    diffBadge.className = `badge badge-${qData.difficulty.toLowerCase()}`;

    // Restore candidate's previous code for this question if it exists, else load starter code
    let savedCode = null;
    try { savedCode = localStorage.getItem("user_code_" + qId); } catch(e){}
    if (!savedCode && state.userCodeMap[qId]) savedCode = state.userCodeMap[qId];

    if (savedCode !== null && savedCode !== undefined && savedCode.trim()) {
      document.getElementById("code-editor").value = savedCode;
    } else {
      document.getElementById("code-editor").value = qData.starter_code || "";
    }

    // Reset test drawer
    document.getElementById("test-runner-output").innerHTML = 
      `<span style="color: var(--text-muted);">Ready to run tests. Click "Run Tests" or submit for Rubric Evaluation.</span>`;

    // Clear chat & post greeting
    state.chatHistory = [];
    const chatContainer = document.getElementById("chat-messages");
    chatContainer.innerHTML = "";
    appendChatMessage("coach", 
      `Hello! I'm your Technical Interview Coach. We are exploring "${qData.title}". Take a moment to read the specification. When you're ready, outline your initial thoughts or start coding!`
    );

    // Refresh RAG Inspector
    inspectRAG(qId);
  } catch (err) {
    console.error("Error selecting question:", err);
  }
}

// --- Dynamic Test Execution ---
async function runTests() {
  const code = document.getElementById("code-editor").value;
  const outDiv = document.getElementById("test-runner-output");
  outDiv.innerHTML = `<span style="color: var(--accent-cyan);">⚡ Sandboxing & executing tests in isolated subprocess...</span>`;

  try {
    const res = await fetch("/api/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code, question_id: state.currentQuestionId })
    });
    const result = await res.json();

    if (result.security_blocked) {
      outDiv.innerHTML = `<div style="color: var(--accent-rose); font-weight: 700;">🚨 SECURITY ALERT: Execution blocked! ${result.violations.join("<br>")}</div>`;
      return;
    }

    if (!result.success) {
      outDiv.innerHTML = `<div style="color: var(--accent-rose); font-weight: 600;">❌ ${result.error}</div>`;
      return;
    }

    let chipsHtml = result.test_results.map(tc => {
      const cls = tc.passed ? "pass" : "fail";
      const icon = tc.passed ? "✓" : "✗";
      return `<span class="test-chip ${cls}">${icon} Test #${tc.id} (${tc.duration_ms}ms)</span>`;
    }).join("");

    let failedDetails = result.test_results
      .filter(tc => !tc.passed)
      .map(tc => {
        let errDesc = tc.error 
          ? `<span style="color: var(--accent-rose);">${tc.error}</span>` 
          : `Got: <code style="color: var(--accent-rose);">${JSON.stringify(tc.actual)}</code> (Expected: <code style="color: var(--accent-emerald);">${JSON.stringify(tc.expected)}</code>)`;
        return `<div style="font-size: 0.8rem; margin-top: 0.4rem; padding: 0.45rem 0.7rem; background: rgba(244, 63, 94, 0.12); border-left: 3px solid var(--accent-rose); border-radius: 4px; font-family: var(--font-mono);">
          <strong>❌ Test #${tc.id} Failed:</strong> Input: <code>${JSON.stringify(tc.input_args)}</code> ➔ ${errDesc}
        </div>`;
      }).join("");

    const summaryText = result.all_passed 
      ? `<span style="color: var(--accent-emerald); font-weight: bold;">All ${result.passed_count}/${result.total_count} Tests Passed in ${result.duration_ms}ms!</span>`
      : `<span style="color: var(--accent-amber); font-weight: bold;">Passed ${result.passed_count}/${result.total_count} Tests (${result.duration_ms}ms)</span>`;

    outDiv.innerHTML = `<div>${summaryText}</div><div style="margin-top: 0.4rem;">${chipsHtml}</div>${failedDetails ? `<div style="margin-top: 0.5rem;">${failedDetails}</div>` : ''}`;
  } catch (err) {
    outDiv.innerHTML = `<span style="color: var(--accent-rose);">Runner error: ${err.message}</span>`;
  }
}

// --- Socratic Interview Chat ---
async function sendChatMessage(customText = null) {
  const input = document.getElementById("chat-input");
  const text = customText || input.value.trim();
  if (!text) return;

  if (!customText) input.value = "";

  appendChatMessage("user", text);
  state.chatHistory.push({ role: "candidate", content: text });

  const typingId = appendChatMessage("coach", "<em>Thinking...</em>");

  try {
    const code = document.getElementById("code-editor").value;
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_id: state.currentQuestionId,
        code: code,
        message: text,
        history: state.chatHistory
      })
    });
    const data = await res.json();
    
    // Replace typing indicator with response
    const bubble = document.getElementById(typingId);
    if (bubble) bubble.innerHTML = data.content;
    state.chatHistory.push({ role: "interviewer", content: data.content });
  } catch (err) {
    const bubble = document.getElementById(typingId);
    if (bubble) bubble.textContent = "I'm reviewing your code. Walk me through your boundary case logic!";
  }
}

function appendChatMessage(role, text) {
  const container = document.getElementById("chat-messages");
  const msgId = "msg-" + Date.now() + Math.random().toString(36).substring(2, 5);
  const bubble = document.createElement("div");
  bubble.id = msgId;
  bubble.className = `chat-bubble ${role}`;
  bubble.innerHTML = text;
  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
  return msgId;
}

// --- Full Rubric Evaluation ---
async function runFullEvaluation() {
  const code = document.getElementById("code-editor").value;
  const evalBtn = document.getElementById("btn-evaluate");
  const origText = evalBtn.innerHTML;
  evalBtn.innerHTML = "⏳ Evaluating...";
  evalBtn.disabled = true;

  try {
    const res = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question_id: state.currentQuestionId,
        code: code
      })
    });
    const result = await res.json();
    state.lastEvalResult = result;

    renderScorecard(result);

    // Switch to Evaluation Tab smoothly
    document.querySelector('[data-tab="tab-eval"]').click();
  } catch (err) {
    alert("Evaluation error: " + err.message);
  } finally {
    evalBtn.innerHTML = origText;
    evalBtn.disabled = false;
  }
}

function renderScorecard(result) {
  document.getElementById("eval-overall-score").textContent = result.overall_score;
  document.getElementById("eval-recommendation").textContent = result.recommendation;
  document.getElementById("eval-verdict").textContent = result.verdict_summary;
  document.getElementById("eval-time-detected").textContent = result.detected_time_complexity;
  document.getElementById("eval-space-detected").textContent = result.detected_space_complexity;

  // AST Badges
  const ast = result.ast_metrics || {};
  document.getElementById("ast-cyclomatic").textContent = ast.cyclomatic_complexity || 1;
  document.getElementById("ast-nesting").textContent = ast.max_loop_nesting || 0;
  document.getElementById("ast-recursion").textContent = ast.recursion_detected ? "Yes" : "No";

  // Strengths & Growth
  const strList = document.getElementById("eval-strengths-list");
  strList.innerHTML = (result.strengths || []).map(s => `<li>✓ ${s}</li>`).join("");

  const growList = document.getElementById("eval-growth-list");
  growList.innerHTML = (result.growth_areas || []).map(g => `<li>⚡ ${g}</li>`).join("");

  // Detailed Rubric Cards with Citations
  const cardsContainer = document.getElementById("rubric-cards-container");
  cardsContainer.innerHTML = "";

  const dimScores = result.dimension_scores || {};
  Object.keys(dimScores).forEach(key => {
    const d = dimScores[key];
    const card = document.createElement("div");
    card.className = "rubric-dimension-card";
    card.innerHTML = `
      <div class="rubric-card-header">
        <span class="rubric-dim-name">${d.dimension_name} (${(d.weight * 100).toFixed(0)}%)</span>
        <span class="rubric-dim-score">${d.raw_score.toFixed(1)} / 10 <small style="font-size: 0.75rem; color: var(--text-muted); font-weight: normal;">[${d.level}]</small></span>
      </div>
      <p style="font-size: 0.85rem; color: #cbd5e1; margin-bottom: 0.5rem; line-height: 1.5;">${d.feedback}</p>
      ${d.suggestions && d.suggestions.length ? `
        <div style="font-size: 0.78rem; color: var(--accent-amber); font-family: var(--font-mono); margin-top: 0.35rem;">
          Actionable Advice: ${d.suggestions.join(" | ")}
        </div>
      ` : ''}
    `;
    cardsContainer.appendChild(card);
  });

  drawRadarChart(dimScores);
}

// --- Canvas Radar Chart Generator ---
function drawRadarChart(dimScores) {
  const canvas = document.getElementById("radarChart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const width = canvas.width;
  const height = canvas.height;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(centerX, centerY) - 38;

  ctx.clearRect(0, 0, width, height);

  const keys = Object.keys(dimScores);
  const total = keys.length || 5;
  const labels = [
    "Correctness",
    "Complexity",
    "Code Quality",
    "Problem Solving",
    "Communication"
  ];

  // Draw concentric polygon rings
  const levels = 5;
  for (let l = 1; l <= levels; l++) {
    const r = (radius / levels) * l;
    ctx.beginPath();
    for (let i = 0; i < total; i++) {
      const angle = (Math.PI * 2 / total) * i - Math.PI / 2;
      const x = centerX + r * Math.cos(angle);
      const y = centerY + r * Math.sin(angle);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.closePath();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.08)";
    ctx.lineWidth = 1;
    ctx.stroke();
  }

  // Draw axis spokes and labels
  for (let i = 0; i < total; i++) {
    const angle = (Math.PI * 2 / total) * i - Math.PI / 2;
    const x = centerX + radius * Math.cos(angle);
    const y = centerY + radius * Math.sin(angle);

    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(x, y);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.15)";
    ctx.stroke();

    // Label positioning
    const labelX = centerX + (radius + 20) * Math.cos(angle);
    const labelY = centerY + (radius + 15) * Math.sin(angle);
    ctx.font = "11px Inter, sans-serif";
    ctx.fillStyle = "#94a3b8";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(labels[i] || `Dim ${i+1}`, labelX, labelY);
  }

  // Draw Candidate polygon
  ctx.beginPath();
  keys.forEach((k, i) => {
    const score = dimScores[k] ? dimScores[k].raw_score : 5.0;
    const ratio = Math.max(0.1, score / 10.0);
    const angle = (Math.PI * 2 / total) * i - Math.PI / 2;
    const x = centerX + (radius * ratio) * Math.cos(angle);
    const y = centerY + (radius * ratio) * Math.sin(angle);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.fillStyle = "rgba(6, 182, 212, 0.25)";
  ctx.fill();
  ctx.strokeStyle = "#06b6d4";
  ctx.lineWidth = 2.5;
  ctx.stroke();

  // Draw data point dots
  keys.forEach((k, i) => {
    const score = dimScores[k] ? dimScores[k].raw_score : 5.0;
    const ratio = Math.max(0.1, score / 10.0);
    const angle = (Math.PI * 2 / total) * i - Math.PI / 2;
    const x = centerX + (radius * ratio) * Math.cos(angle);
    const y = centerY + (radius * ratio) * Math.sin(angle);

    ctx.beginPath();
    ctx.arc(x, y, 4, 0, Math.PI * 2);
    ctx.fillStyle = "#10b981";
    ctx.fill();
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 1.5;
    ctx.stroke();
  });
}

// --- Transparent Hybrid RAG Inspector ---
async function inspectRAG(qId) {
  const container = document.getElementById("rag-chunks-container");
  if (!container) return;
  container.innerHTML = `<span style="color: var(--text-muted);">Querying Okapi BM25 index & Cosine vector embeddings...</span>`;

  try {
    const code = document.getElementById("code-editor")?.value || "";
    const res = await fetch("/api/rag-inspect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question_id: qId, query: code })
    });
    const data = await res.json();
    const chunks = data.retrieved_chunks || [];

    if (chunks.length === 0) {
      container.innerHTML = `<span style="color: var(--text-muted);">No rubric chunks retrieved for current query.</span>`;
      return;
    }

    container.innerHTML = chunks.map((c, i) => {
      const authBadge = c.is_authoritative
        ? `<span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16,185,129,0.3); font-size: 0.7rem;">Authoritative Grounding</span>`
        : `<span class="badge" style="background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245,158,11,0.3); font-size: 0.7rem;">Low Evidence Warning</span>`;

      return `
        <div class="rag-chunk-box">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
            <div>
              <strong style="color: var(--accent-cyan); font-size: 0.95rem;">[Chunk #${i+1}] ${c.title}</strong>
              <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.15rem;">Source Document: <code style="color: #94a3b8;">${c.source_document}</code> | Chunk ID: <code style="color: #cbd5e1;">${c.chunk_id}</code></div>
            </div>
            <div style="display: flex; align-items: center; gap: 0.5rem;">
              ${authBadge}
              <div style="text-align: right; font-family: var(--font-mono); font-size: 0.78rem;">
                <span style="color: var(--accent-cyan); font-weight: bold;">Hybrid Score: ${c.hybrid_score}</span>
                <span style="color: var(--text-muted); font-size: 0.72rem; display: block;">(BM25: ${c.raw_bm25_score} | Cosine: ${c.cosine_similarity})</span>
              </div>
            </div>
          </div>
          <p style="color: #cbd5e1; font-size: 0.82rem; margin-top: 0.4rem; line-height: 1.5; background: rgba(0,0,0,0.25); padding: 0.65rem; border-radius: 6px; border: 1px solid rgba(255,255,255,0.05);">${c.content}</p>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<span style="color: var(--accent-rose);">Failed to inspect RAG: ${err.message}</span>`;
  }
}

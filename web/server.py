"""
Lightweight, Zero-Dependency REST Server for AI Technical Interview Coach.
Built using standard library http.server, supporting real-time test execution,
AST analysis, RAG retrieval inspection, Socratic chat, and Rubric evaluation.
"""

import http.server
import socketserver
import json
import urllib.parse
import os
import sys
import time
from typing import Dict, Any

# Ensure core is importable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.ast_analyzer import analyze_python_code
from core.code_executor import execute_test_cases
from core.rag_engine import HybridRAGEngine
from core.llm_evaluator import LLMInterviewCoach

DATA_PATH = os.path.join(BASE_DIR, "data", "questions.json")
STATIC_DIR = os.path.join(BASE_DIR, "web", "static")

# Initialize global engines
rag_engine = HybridRAGEngine(DATA_PATH)
coach = LLMInterviewCoach()

# Pre-load questions lookup
with open(DATA_PATH, "r", encoding="utf-8") as f:
    QUESTIONS_LIST = json.load(f)
QUESTIONS_MAP = {q["id"]: q for q in QUESTIONS_LIST}


class InterviewCoachHTTPHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.path = "/index.html"
            return super().do_GET()

        if path == "/api/questions":
            summary = [
                {
                    "id": q["id"],
                    "title": q["title"],
                    "difficulty": q["difficulty"],
                    "category": q["category"],
                    "optimal_time": q["optimal_time"],
                    "optimal_space": q["optimal_space"]
                }
                for q in QUESTIONS_LIST
            ]
            return self._send_json({"questions": summary})

        if path.startswith("/api/questions/"):
            q_id = path.replace("/api/questions/", "").strip()
            q_data = QUESTIONS_MAP.get(q_id)
            if q_data:
                # Omit hidden test case answers in public listing for interview realism
                sanitized = dict(q_data)
                sanitized["public_test_cases"] = [tc for tc in q_data.get("test_cases", []) if not tc.get("hidden")]
                sanitized["total_test_cases_count"] = len(q_data.get("test_cases", []))
                return self._send_json(sanitized)
            return self._send_json({"error": "Question not found"}, status=404)

        if path == "/api/status":
            return self._send_json({
                "status": "online",
                "indexed_documents": rag_engine.doc_count,
                "has_gemini_api_key": bool(coach.api_key),
                "masked_key": coach.get_masked_key(),
                "model": coach.model,
                "provider_mode": coach.provider_mode,
                "ingested_documents": rag_engine.ingested_documents
            })

        # Static assets
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/config":
            api_key = body.get("api_key", "").strip()
            model = body.get("model", "gemini-2.5-flash").strip()
            mode = body.get("provider_mode", "").strip()

            if api_key:
                coach.set_api_key(api_key)
            if model:
                coach.model = model
            if mode:
                coach.set_provider_mode(mode)

            return self._send_json({
                "success": True,
                "has_key": bool(coach.api_key),
                "masked_key": coach.get_masked_key(),
                "model": coach.model,
                "provider_mode": coach.provider_mode
            })

        if path == "/api/test-connection":
            api_key = body.get("api_key", "").strip()
            model = body.get("model", "").strip()
            result = coach.test_connection(api_key=api_key or None, model=model or None)
            return self._send_json(result)

        if path == "/api/rag-upload":
            filename = body.get("filename", "interview_notes.txt").strip()
            content = body.get("content", "").strip()
            category = body.get("category", "Custom Material").strip()
            if not content:
                return self._send_json({"error": "Empty document content"}, status=400)

            ingest_meta = rag_engine.ingest_document(filename, content, category=category)
            return self._send_json({
                "success": True,
                "ingest_meta": ingest_meta,
                "total_indexed_chunks": rag_engine.doc_count
            })

        if path == "/api/rag-compare":
            q_id = body.get("question_id", "two-sum")
            code = body.get("code", "")
            q_data = QUESTIONS_MAP.get(q_id, {})
            comparison = rag_engine.simulate_rag_comparison(q_data, code)
            return self._send_json(comparison)

        if path == "/api/execute":
            code = body.get("code", "")
            q_id = body.get("question_id", "")
            q_data = QUESTIONS_MAP.get(q_id)
            if not q_data:
                return self._send_json({"error": "Invalid question_id"}, status=400)

            test_cases = q_data.get("test_cases", [])
            entrypoint = q_data.get("entrypoint", "solution")
            for tc in test_cases:
                if not tc.get("entrypoint"):
                    tc["entrypoint"] = entrypoint
            exec_res = execute_test_cases(code, test_cases, timeout_sec=3.0)
            return self._send_json(exec_res)

        if path == "/api/questions/add":
            new_q = body.get("question", {})
            q_id = new_q.get("id", "").strip() or f"custom_{int(time.time())}"
            new_q["id"] = q_id
            if "entrypoint" not in new_q:
                new_q["entrypoint"] = "solution"
            if "starter_code" not in new_q:
                new_q["starter_code"] = f"def {new_q['entrypoint']}():\n    # Implement solution here\n    pass\n"

            QUESTIONS_LIST.append(new_q)
            QUESTIONS_MAP[q_id] = new_q
            rag_engine.add_question(new_q)
            return self._send_json({"success": True, "question": new_q})

        if path == "/api/questions/reset":
            with open(DATA_PATH, "r", encoding="utf-8") as f:
                fresh_list = json.load(f)
            QUESTIONS_LIST.clear()
            QUESTIONS_LIST.extend(fresh_list)
            QUESTIONS_MAP.clear()
            for q in QUESTIONS_LIST:
                QUESTIONS_MAP[q["id"]] = q
            return self._send_json({"success": True, "count": len(QUESTIONS_LIST)})

        if path == "/api/analyze-ast":
            code = body.get("code", "")
            metrics = analyze_python_code(code)
            return self._send_json(metrics)

        if path == "/api/rag-inspect":
            q_id = body.get("question_id", "")
            query = body.get("query", "")
            grounded = rag_engine.build_grounded_context(q_id, query)
            return self._send_json(grounded)

        if path == "/api/chat":
            q_id = body.get("question_id", "")
            code = body.get("code", "")
            user_msg = body.get("message", "")
            history = body.get("history", [])

            q_data = QUESTIONS_MAP.get(q_id, {})
            grounded = rag_engine.build_grounded_context(q_id, f"{user_msg} {code}")
            chat_reply = coach.chat_turn(
                question_meta=q_data,
                candidate_code=code,
                chat_history=history,
                user_message=user_msg,
                rag_context=grounded["grounding_context"]
            )
            return self._send_json(chat_reply)

        if path == "/api/evaluate":
            q_id = body.get("question_id", "")
            code = body.get("code", "")
            q_data = QUESTIONS_MAP.get(q_id)
            if not q_data:
                return self._send_json({"error": "Invalid question_id"}, status=400)

            # 1. Run dynamic test suite
            test_cases = q_data.get("test_cases", [])
            entrypoint = q_data.get("entrypoint", "solution")
            for tc in test_cases:
                if not tc.get("entrypoint"):
                    tc["entrypoint"] = entrypoint
            test_results = execute_test_cases(code, test_cases, timeout_sec=3.0)

            # 2. Run static AST code analysis
            ast_metrics = analyze_python_code(code)

            # 3. Retrieve RAG benchmark chunks
            rag_payload = rag_engine.build_grounded_context(q_id, code)

            # 4. LLM Rubric Evaluation
            eval_result = coach.evaluate_submission(
                question_meta=q_data,
                candidate_code=code,
                test_results=test_results,
                ast_metrics=ast_metrics,
                rag_payload=rag_payload
            )

            response_data = eval_result.to_dict()
            response_data["rag_inspection"] = {
                "retrieved_chunks": rag_payload["retrieved_chunks"],
                "chunk_count": rag_payload["chunk_count"]
            }
            return self._send_json(response_data)

        return self._send_json({"error": "Endpoint not found"}, status=404)


def run_server(port: int = None, host: str = None):
    if port is None:
        port = int(os.environ.get("PORT", 8080))
    if host is None:
        host = os.environ.get("HOST", "0.0.0.0")

    server_address = (host, port)
    # Allow port reuse immediately
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(server_address, InterviewCoachHTTPHandler) as httpd:
        print(f"\n=======================================================")
        print(f"🚀 AI Technical Interview Coach Server Active!")
        print(f"📡 Serving at: http://{host}:{port}")
        print(f"📚 Indexed RAG Knowledge Chunks: {rag_engine.doc_count}")
        print(f"🎓 College Seminar Mode: Ready for 10-Minute Presentation")
        print(f"=======================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server gracefully...")
            httpd.shutdown()


if __name__ == "__main__":
    p = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8080))
    h = os.environ.get("HOST", "0.0.0.0")
    run_server(port=p, host=h)

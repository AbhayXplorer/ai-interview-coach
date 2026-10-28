"""
Automated Unit and Integration Tests for AI Interview Coach Core Engines.
"""

import unittest
import os
import sys

# Ensure root is in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from core.ast_analyzer import analyze_python_code
from core.code_executor import execute_test_cases, check_code_safety
from core.rag_engine import HybridRAGEngine
from core.rubric import DEFAULT_RUBRIC_DIMENSIONS, get_recommendation_band
from core.llm_evaluator import LLMInterviewCoach

class TestAIInterviewCoachCore(unittest.TestCase):

    def test_ast_analyzer_linear(self):
        code = '''
def two_sum(nums, target):
    seen = {}
    for i, n in enumerate(nums):
        diff = target - n
        if diff in seen:
            return [seen[diff], i]
        seen[n] = i
    return []
'''
        metrics = analyze_python_code(code)
        self.assertTrue(metrics["valid_syntax"])
        self.assertEqual(metrics["max_loop_nesting"], 1)
        self.assertFalse(metrics["recursion_detected"])
        self.assertEqual(metrics["heuristic_time_complexity"], "O(N) [Linear]")
        self.assertIn("two_sum", metrics["functions_defined"])

    def test_ast_analyzer_nested_loops(self):
        code = '''
def brute_force(nums, target):
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
    return []
'''
        metrics = analyze_python_code(code)
        self.assertTrue(metrics["valid_syntax"])
        self.assertEqual(metrics["max_loop_nesting"], 2)
        self.assertEqual(metrics["heuristic_time_complexity"], "O(N^2) [Quadratic]")

    def test_code_executor_success(self):
        code = '''
def solution(a, b):
    return a + b
'''
        test_cases = [
            {"id": 1, "entrypoint": "solution", "input_args": [2, 3], "expected": 5},
            {"id": 2, "entrypoint": "solution", "input_args": [-1, 1], "expected": 0}
        ]
        res = execute_test_cases(code, test_cases, timeout_sec=2.0)
        self.assertTrue(res["success"])
        self.assertTrue(res["all_passed"])
        self.assertEqual(res["passed_count"], 2)

    def test_code_executor_failure(self):
        code = '''
def solution(a, b):
    return a - b  # Buggy!
'''
        test_cases = [
            {"id": 1, "entrypoint": "solution", "input_args": [2, 3], "expected": 5}
        ]
        res = execute_test_cases(code, test_cases, timeout_sec=2.0)
        self.assertTrue(res["success"])
        self.assertFalse(res["all_passed"])
        self.assertEqual(res["passed_count"], 0)

    def test_code_executor_infinite_loop_timeout(self):
        code = '''
def solution():
    while True:
        pass
'''
        test_cases = [{"id": 1, "entrypoint": "solution", "input_args": [], "expected": 0}]
        res = execute_test_cases(code, test_cases, timeout_sec=0.5)
        self.assertFalse(res["success"])
        self.assertIn("Time Limit Exceeded", res["error"])

    def test_code_safety_block(self):
        malicious_code = '''
import os
os.system("ls")
'''
        violations = check_code_safety(malicious_code)
        self.assertTrue(len(violations) > 0)
        res = execute_test_cases(malicious_code, [], timeout_sec=1.0)
        self.assertTrue(res["security_blocked"])

    def test_rag_retrieval(self):
        questions_path = os.path.join(BASE_DIR, "data", "questions.json")
        rag = HybridRAGEngine(questions_path)
        self.assertGreater(rag.doc_count, 0)

        chunks = rag.retrieve("Two Sum hash map complement", question_id="two-sum", top_k=2)
        self.assertGreater(len(chunks), 0)
        self.assertEqual(chunks[0]["metadata"]["question_id"], "two-sum")
        # Verify transparent score breakdown exists
        self.assertIn("raw_bm25_score", chunks[0])
        self.assertIn("cosine_similarity", chunks[0])
        self.assertIn("hybrid_score", chunks[0])
        self.assertIn("source_document", chunks[0])

    def test_rag_document_ingestion_and_comparison(self):
        questions_path = os.path.join(BASE_DIR, "data", "questions.json")
        rag = HybridRAGEngine(questions_path)
        initial_count = rag.doc_count

        sample_doc = """
# System Design & Concurrency Guidelines
Candidate must demonstrate thread safety using mutex locks or concurrent queues.
Deduct points if race conditions or deadlock vulnerabilities are present.
"""
        meta = rag.ingest_document("guidelines.md", sample_doc, category="Staff Evaluation")
        self.assertEqual(meta["filename"], "guidelines.md")
        self.assertGreater(meta["chunks_created"], 0)
        self.assertGreater(rag.doc_count, initial_count)

        # Test RAG ON vs RAG OFF simulation
        comp = rag.simulate_rag_comparison({"id": "two-sum", "title": "Two Sum", "optimal_time": "O(N)"}, "def two_sum(): pass")
        self.assertTrue(comp["rag_on"]["context_injected"])
        self.assertFalse(comp["rag_off"]["context_injected"])
        self.assertGreater(len(comp["rag_on"]["citations"]), 0)

    def test_llm_evaluator_connection_test(self):
        coach = LLMInterviewCoach()
        # Testing with empty key should report cleanly
        res = coach.test_connection(api_key="")
        self.assertFalse(res["success"])
        self.assertEqual(res["status"], "No API Key Provided")

    def test_recommendation_band(self):
        self.assertIn("Strong Hire", get_recommendation_band(92.0))
        self.assertIn("Hire", get_recommendation_band(78.0))
        self.assertIn("Leaning Hire", get_recommendation_band(65.0))
        self.assertIn("No Hire", get_recommendation_band(30.0))

if __name__ == "__main__":
    unittest.main()

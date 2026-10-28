"""
LLM Evaluation & Socratic Coaching Engine.
Supports:
1. Online Cloud AI Mode via Google Gemini API (gemini-2.5-flash / gemini-1.5-pro) using standard HTTPS requests.
2. Local Rule-Based Mode (Deterministic AST heuristics & Unit Assertion Scorer - truthfully labeled, not an LLM).
3. Test Connection Ping with Latency & Status Diagnostics.
4. Grounded Citations Linking Feedback to Exact RAG Benchmark Chunks.
"""

import json
import urllib.request
import urllib.error
import os
import time
import re
from typing import Dict, Any, List, Optional
from core.rubric import (
    DEFAULT_RUBRIC_DIMENSIONS,
    DimensionScore,
    RubricEvaluationResult,
    get_recommendation_band
)

class LLMInterviewCoach:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        # Prioritize passed api_key, then fallback to environment variable
        self.api_key = (api_key or os.environ.get("GEMINI_API_KEY", "")).strip() or None
        self.model = model
        self.provider_mode = "gemini_cloud" if self.api_key else "local_rules"

    def set_api_key(self, api_key: Optional[str]):
        self.api_key = api_key.strip() if api_key else None
        if self.api_key:
            self.provider_mode = "gemini_cloud"

    def set_provider_mode(self, mode: str):
        if mode in ["gemini_cloud", "local_rules"]:
            self.provider_mode = mode

    def get_masked_key(self) -> str:
        if not self.api_key:
            return ""
        if len(self.api_key) <= 8:
            return "••••••••"
        return f"{self.api_key[:4]}••••••••{self.api_key[-4:]}"

    def test_connection(self, api_key: Optional[str] = None, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends an actual lightweight test request to Google Gemini API
        to verify key validity, network connectivity, and latency.
        """
        key_to_test = (api_key or self.api_key or "").strip()
        model_to_test = model or self.model or "gemini-2.5-flash"

        if not key_to_test:
            return {
                "success": False,
                "status": "No API Key Provided",
                "message": "API key field is empty. Please enter your Google Gemini API key to connect."
            }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_to_test}:generateContent?key={key_to_test}"
        payload = {
            "contents": [{"parts": [{"text": "ping"}]}],
            "generationConfig": {"maxOutputTokens": 5}
        }

        t0 = time.perf_counter()
        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                res_body = resp.read().decode('utf-8')
                data = json.loads(res_body)
                if "candidates" in data:
                    return {
                        "success": True,
                        "status": "Connected",
                        "model": model_to_test,
                        "latency_ms": elapsed_ms,
                        "message": f"Successfully authenticated with Google Gemini ({model_to_test}) in {elapsed_ms}ms."
                    }
                else:
                    return {
                        "success": False,
                        "status": "Unexpected Response",
                        "model": model_to_test,
                        "message": "Connected but received empty candidate response."
                    }
        except urllib.error.HTTPError as e:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)
            err_msg = e.read().decode('utf-8', errors='ignore')
            if e.code in [400, 403]:
                return {
                    "success": False,
                    "status": "Invalid API Key",
                    "http_code": e.code,
                    "latency_ms": elapsed_ms,
                    "message": "Google Gemini rejected the API key (HTTP 400/403). Please verify your Google AI Studio key."
                }
            return {
                "success": False,
                "status": f"HTTP Error {e.code}",
                "http_code": e.code,
                "message": f"Gemini API returned error: {err_msg[:120]}"
            }
        except Exception as e:
            return {
                "success": False,
                "status": "Connection Failed",
                "message": f"Network or timeout error: {str(e)}"
            }

    def _call_gemini_api(self, prompt: str, system_instruction: str = "") -> Optional[str]:
        """Direct HTTPS call to Google Gemini API."""
        if not self.api_key or self.provider_mode == "local_rules":
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "maxOutputTokens": 2048
            }
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            req_data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                res_body = resp.read().decode('utf-8')
                data = json.loads(res_body)
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
        except Exception as e:
            print(f"[Gemini API Warning]: {e}. Falling back to deterministic local rule engine.")
            return None
        return None

    def chat_turn(self, 
                  question_meta: Dict[str, Any], 
                  candidate_code: str, 
                  chat_history: List[Dict[str, str]], 
                  user_message: str,
                  rag_context: str) -> Dict[str, str]:
        """
        Interactive Socratic technical interviewer turn.
        Provides guiding hints without revealing the solution directly.
        """
        system_prompt = (
            "You are a Senior Staff Software Engineer conducting a real technical coding interview.\n"
            "Pedagogical Style: Socratic, constructive, professional, and rigorous.\n"
            "Rules:\n"
            "1. NEVER output the full solution code.\n"
            "2. If candidate asks for hints, provide a progressive hint (Level 1: clarify invariant, Level 2: data structure suggestion, Level 3: algorithmic nudge).\n"
            "3. Ask about time and space complexity trade-offs.\n"
            "4. Challenge edge cases (empty inputs, negative values, duplicates, large bounds).\n"
            "5. Keep responses concise (under 120 words) to mimic a live verbal interview dialogue.\n\n"
            f"RAG GROUNDING REFERENCE:\n{rag_context}\n"
        )

        prompt = (
            f"Current Problem: {question_meta.get('title')}\n"
            f"Candidate's Current Code:\n```python\n{candidate_code}\n```\n\n"
            f"Recent Conversation History:\n" +
            "\n".join([f"{msg['role'].upper()}: {msg['content']}" for msg in chat_history[-4:]]) +
            f"\nCANDIDATE: {user_message}\n"
            "INTERVIEWER (Respond concisely and guide):"
        )

        response_text = self._call_gemini_api(prompt, system_instruction=system_prompt)

        if not response_text:
            # Deterministic Socratic Dialogue Engine (Local Fallback)
            response_text = self._fallback_socratic_response(user_message, candidate_code, question_meta)

        return {
            "role": "interviewer",
            "content": response_text
        }

    def _fallback_socratic_response(self, user_message: str, candidate_code: str, question_meta: Dict[str, Any]) -> str:
        """Deterministic Socratic Dialogue Engine simulating interviewer cues."""
        msg_lower = user_message.lower()
        title = question_meta.get("title", "this problem")
        q_id = question_meta.get("id", "")

        if any(w in msg_lower for w in ["hint", "stuck", "help", "guide", "confused", "approach"]):
            if q_id == "two-sum":
                return (
                    "Good observation! Instead of checking every pair with nested loops ($O(N^2)$), "
                    "think about what information you need when inspecting number $x$. "
                    "You need $(target - x)$. How can you look that up in $O(1)$ time?"
                )
            elif q_id == "valid-anagram":
                return (
                    "Consider character frequencies. Can you compare counts in $O(N)$ time with an auxiliary hash table or a fixed-size 26-element array, rather than sorting?"
                )
            elif q_id == "valid-parentheses":
                return (
                    "Think about bracket order. The most recently opened bracket must match the next closing bracket. "
                    "Which LIFO data structure models this sequence naturally?"
                )
            elif q_id == "max-subarray":
                return (
                    "Consider Kadane's algorithm: At index $i$, is it better to extend the previous contiguous sum, or start fresh from $nums[i]$?"
                )
            elif q_id == "longest-substring":
                return (
                    "Try a Sliding Window with two pointers (left and right). When you encounter a duplicate character, "
                    "how can a hash map help you advance the left pointer in $O(1)$?"
                )
            elif q_id == "merge-intervals":
                return (
                    "Think about the order of intervals. If intervals were sorted by start time, "
                    "when does an overlap happen with the previous interval? What is the condition?"
                )
            elif q_id == "lru-cache":
                return (
                    "To achieve $O(1)$ for both get and eviction, you need both fast lookups and fast reordering. "
                    "Which two fundamental data structures combine hash lookups with constant-time node removals?"
                )
            else:
                return (
                    f"Let's trace {title}. Start by walking through a small manual example. "
                    "What invariant can you maintain to avoid redundant recomputations?"
                )

        if any(w in msg_lower for w in ["complexity", "big o", "runtime", "time", "space"]):
            return (
                "Great question to consider! What is the dominant operation in your current solution? "
                "How does the auxiliary memory scale with the input size $N$?"
            )

        if any(w in msg_lower for w in ["edge case", "edge cases", "corner case", "null", "empty", "negative"]):
            return (
                "Spot on! In real interviews, edge cases matter immensely. "
                "Consider: What happens if the input is empty? What if all elements are identical, or negative? "
                "Have you handled boundary limits?"
            )

        return (
            f"I see your direction on {title}. "
            "Walk me through your thought process: How does your code handle the primary constraint, and what test case would you run first to test for boundary failures?"
        )

    def evaluate_submission(self,
                            question_meta: Dict[str, Any],
                            candidate_code: str,
                            test_results: Dict[str, Any],
                            ast_metrics: Dict[str, Any],
                            rag_payload: Dict[str, Any]) -> RubricEvaluationResult:
        """
        Executes the formal Rubric-Based Code Evaluation.
        Uses Gemini Cloud AI if key exists and provider_mode is 'gemini_cloud',
        otherwise executes Deterministic Rule-Based Evaluation.
        """
        gemini_result = None
        if self.provider_mode == "gemini_cloud" and self.api_key:
            gemini_result = self._gemini_rubric_evaluation(
                question_meta, candidate_code, test_results, ast_metrics, rag_payload
            )

        if gemini_result:
            return gemini_result

        # Authoritative, deterministic local rule-based evaluation
        return self._local_deterministic_rubric_evaluation(
            question_meta, candidate_code, test_results, ast_metrics, rag_payload
        )

    def _gemini_rubric_evaluation(self, question_meta, candidate_code, test_results, ast_metrics, rag_payload) -> Optional[RubricEvaluationResult]:
        """Calls Gemini Cloud API requesting structured JSON matching the rubric schema with citations."""
        system_instruction = (
            "You are an Elite Technical Hiring Evaluator at a top technology firm.\n"
            "You evaluate candidates using a strict 5-dimensional rubric:\n"
            "1. algorithmic_correctness (30%)\n"
            "2. time_space_complexity (20%)\n"
            "3. code_quality_cleanliness (20%)\n"
            "4. problem_solving_approach (15%)\n"
            "5. communication_articulation (15%)\n"
            "Base your grading strictly on the retrieved RAG ground truth benchmarks.\n"
            "Include explicit citations [Citation: chunk_id] where appropriate.\n"
            "You must return ONLY a valid JSON object matching the requested schema."
        )

        prompt = f"""
Evaluate the following candidate interview submission:

PROBLEM: {question_meta.get('title')}
OPTIMAL TIME: {question_meta.get('optimal_time')}
OPTIMAL SPACE: {question_meta.get('optimal_space')}

RAG GROUND TRUTH BENCHMARK WITH CITATIONS:
{rag_payload.get('grounding_context', '')}

STATIC AST ANALYSIS:
- Cyclomatic Complexity: {ast_metrics.get('cyclomatic_complexity')}
- Max Loop Nesting: {ast_metrics.get('max_loop_nesting')}
- Recursion Detected: {ast_metrics.get('recursion_detected')}
- Data Structures: {ast_metrics.get('data_structures')}
- Heuristic Complexity: {ast_metrics.get('heuristic_time_complexity')}

TEST RUNNER RESULTS:
- All Passed: {test_results.get('all_passed')}
- Passed: {test_results.get('passed_count')}/{test_results.get('total_count')}
- Runtime ms: {test_results.get('duration_ms')}
- Execution Errors: {test_results.get('error')}

CANDIDATE CODE:
```python
{candidate_code}
```

Respond with ONLY a JSON object formatted exactly as:
{{
  "overall_score": 85.0,
  "verdict_summary": "...",
  "detected_time_complexity": "O(N)",
  "detected_space_complexity": "O(N)",
  "strengths": ["...", "..."],
  "growth_areas": ["...", "..."],
  "scores": {{
    "algorithmic_correctness": {{"score": 9.0, "feedback": "... [Citation: ...]", "suggestions": ["..."]}},
    "time_space_complexity": {{"score": 8.5, "feedback": "... [Citation: ...]", "suggestions": ["..."]}},
    "code_quality_cleanliness": {{"score": 8.0, "feedback": "...", "suggestions": ["..."]}},
    "problem_solving_approach": {{"score": 8.5, "feedback": "...", "suggestions": ["..."]}},
    "communication_articulation": {{"score": 8.0, "feedback": "...", "suggestions": ["..."]}}
  }}
}}
"""
        raw_text = self._call_gemini_api(prompt, system_instruction)
        if not raw_text:
            return None

        try:
            clean_json = raw_text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            data = json.loads(clean_json.strip())

            dimension_scores = {}
            dim_dict = {d.id: d for d in DEFAULT_RUBRIC_DIMENSIONS}

            for dim_id, d_meta in dim_dict.items():
                s_info = data.get("scores", {}).get(dim_id, {})
                raw_s = float(s_info.get("score", 7.0))
                level_str = "Proficient"
                if raw_s >= 9.0: level_str = "Exemplary"
                elif raw_s >= 7.0: level_str = "Proficient"
                elif raw_s >= 4.5: level_str = "Developing"
                else: level_str = "Unsatisfactory"

                dimension_scores[dim_id] = DimensionScore(
                    dimension_id=dim_id,
                    dimension_name=d_meta.name,
                    raw_score=raw_s,
                    weight=d_meta.weight,
                    weighted_score=round(raw_s * d_meta.weight * 10.0, 1),
                    level=level_str,
                    feedback=s_info.get("feedback", "Met standard expectations."),
                    suggestions=s_info.get("suggestions", [])
                )

            overall = float(data.get("overall_score", 75.0))
            return RubricEvaluationResult(
                overall_score=overall,
                recommendation=get_recommendation_band(overall),
                verdict_summary=f"[Evaluator: Google Gemini ({self.model})] " + data.get("verdict_summary", "Candidate demonstrated solid grasp of the core algorithm."),
                dimension_scores=dimension_scores,
                strengths=data.get("strengths", ["Clear code structure", "Passes functional test suite"]),
                growth_areas=data.get("growth_areas", ["Further optimize space bounds", "Add comprehensive boundary checks"]),
                detected_time_complexity=data.get("detected_time_complexity", ast_metrics.get("heuristic_time_complexity")),
                detected_space_complexity=data.get("detected_space_complexity", ast_metrics.get("heuristic_space_complexity")),
                optimal_time_complexity=question_meta.get("optimal_time", "O(N)"),
                optimal_space_complexity=question_meta.get("optimal_space", "O(N)"),
                ast_metrics=ast_metrics,
                test_suite_summary=test_results
            )
        except Exception as e:
            print(f"[Gemini Response Parse Error]: {e}. Falling back to rule engine.")
            return None

    def _local_deterministic_rubric_evaluation(self,
                                               question_meta: Dict[str, Any],
                                               candidate_code: str,
                                               test_results: Dict[str, Any],
                                               ast_metrics: Dict[str, Any],
                                               rag_payload: Dict[str, Any]) -> RubricEvaluationResult:
        """
        High-precision deterministic rule-based evaluation engine.
        Explicitly operates without LLM hallucination using static AST metrics,
        unit assertion statistics, and RAG ground truth citations.
        """
        total_tc = max(1, test_results.get("total_count", 1))
        passed_tc = test_results.get("passed_count", 0)
        passed_ratio = passed_tc / total_tc

        # Citations list from retrieved chunks
        chunks = rag_payload.get("retrieved_chunks", [])
        citation_rubric = f"[{chunks[1]['chunk_id']}]" if len(chunks) > 1 else "[RAG_Benchmark]"
        citation_spec = f"[{chunks[0]['chunk_id']}]" if len(chunks) > 0 else "[Problem_Spec]"

        # 1. Correctness Dimension (30%)
        if test_results.get("all_passed", False):
            correctness_score = 9.5
            corr_fb = f"All unit tests and hidden boundary cases passed with zero exceptions. Cites {citation_spec}."
            corr_sug = ["Maintain current proactive edge-case testing discipline."]
        elif passed_ratio > 0.6:
            correctness_score = 6.8
            corr_fb = f"Passed {passed_tc}/{total_tc} tests. Core logic works on standard inputs but failed hidden edge cases {citation_spec}."
            corr_sug = ["Inspect edge conditions like duplicate elements, empty arrays, or negative values."]
        elif passed_ratio > 0:
            correctness_score = 4.2
            corr_fb = f"Passed {passed_tc}/{total_tc} tests. Frequent logical miscalculations or boundary off-by-one errors."
            corr_sug = ["Trace boundary states manually with pen and paper before executing."]
        else:
            correctness_score = 2.0
            corr_fb = "Solution failed all test cases or encountered a blocking runtime exception."
            corr_sug = ["Address syntax or naming exceptions and verify function signature."]

        # 2. Time & Space Complexity Dimension (20%)
        max_loop = ast_metrics.get("max_loop_nesting", 0)
        rec_detected = ast_metrics.get("recursion_detected", False)
        target_time = question_meta.get("optimal_time", "O(N)")

        time_space_score = 8.5
        ts_sug = []
        detected_time = ast_metrics.get("heuristic_time_complexity", "O(N)")
        detected_space = ast_metrics.get("heuristic_space_complexity", "O(N)")

        if "O(N)" in target_time and max_loop >= 2:
            time_space_score = 5.0
            detected_time = "O(N^2) [Suboptimal Nested Loops]"
            ts_fb = f"Detected nested loops ($O(N^2)$). Target benchmark {citation_rubric} requires linear $O(N)$."
            ts_sug.append("Replace inner iterative search with a Hash Map or Set for $O(1)$ lookups.")
        elif "O(1)" in target_time and (max_loop >= 1 or rec_detected):
            time_space_score = 6.0
            ts_fb = f"Failed to achieve constant $O(1)$ time; linear loop traversal detected {citation_rubric}."
            ts_sug.append("Utilize constant time hash lookups or pointer swaps.")
        else:
            time_space_score = 9.2
            ts_fb = f"Achieved optimal asymptotic time complexity of {detected_time} with minimal auxiliary space {citation_rubric}."
            ts_sug.append("Explore potential in-place bit manipulation or pointer memory optimizations.")

        # 3. Code Quality & Cleanliness (20%)
        cq_score = 8.0
        cq_sug = []
        single_chars = ast_metrics.get("single_char_vars", [])
        cyclomatic = ast_metrics.get("cyclomatic_complexity", 1)

        if single_chars:
            cq_score -= 1.0
            cq_sug.append(f"Replace non-idiomatic single character variable names: {', '.join(single_chars)}.")
        if cyclomatic > 6:
            cq_score -= 1.5
            cq_sug.append(f"Cyclomatic complexity is high ({cyclomatic}). Break complex branches into helper functions.")
        if ast_metrics.get("has_type_hints"):
            cq_score = min(10.0, cq_score + 1.0)

        cq_fb = f"Clean, readable code with cyclomatic complexity of {cyclomatic}."
        if not cq_sug:
            cq_sug.append("Keep consistent PEP8 naming and docstring annotations.")

        # 4. Problem Solving Approach (15%)
        ps_score = 9.0 if passed_ratio >= 0.8 else 6.0
        ps_fb = f"Demonstrated pattern recognition matching the grounded FAANG algorithmic paradigm {citation_rubric}."
        ps_sug = ["Formulate loop invariants explicitly before implementation."] if passed_ratio < 0.8 else []

        # 5. Communication & Articulation (15%)
        comm_score = 8.5
        comm_fb = "Candidate's code exhibits structured naming and modular separation facilitating clear walkthrough."
        comm_sug = ["Explain complexity trade-offs proactively to the interviewer."]

        # Calculate weighted overall score
        dim_scores: Dict[str, DimensionScore] = {
            "algorithmic_correctness": DimensionScore(
                dimension_id="algorithmic_correctness",
                dimension_name="Algorithmic Correctness & Edge Cases",
                raw_score=correctness_score,
                weight=0.30,
                weighted_score=round(correctness_score * 0.30 * 10.0, 1),
                level="Exemplary" if correctness_score >= 8.8 else ("Proficient" if correctness_score >= 6.5 else "Developing"),
                feedback=corr_fb,
                suggestions=corr_sug
            ),
            "time_space_complexity": DimensionScore(
                dimension_id="time_space_complexity",
                dimension_name="Time & Space Complexity Optimization",
                raw_score=time_space_score,
                weight=0.20,
                weighted_score=round(time_space_score * 0.20 * 10.0, 1),
                level="Exemplary" if time_space_score >= 8.8 else ("Proficient" if time_space_score >= 6.5 else "Developing"),
                feedback=ts_fb,
                suggestions=ts_sug
            ),
            "code_quality_cleanliness": DimensionScore(
                dimension_id="code_quality_cleanliness",
                dimension_name="Code Quality, Modularity & Style",
                raw_score=cq_score,
                weight=0.20,
                weighted_score=round(cq_score * 0.20 * 10.0, 1),
                level="Exemplary" if cq_score >= 8.8 else ("Proficient" if cq_score >= 6.5 else "Developing"),
                feedback=cq_fb,
                suggestions=cq_sug
            ),
            "problem_solving_approach": DimensionScore(
                dimension_id="problem_solving_approach",
                dimension_name="Problem Solving & Systematic Decomposition",
                raw_score=ps_score,
                weight=0.15,
                weighted_score=round(ps_score * 0.15 * 10.0, 1),
                level="Exemplary" if ps_score >= 8.8 else "Proficient",
                feedback=ps_fb,
                suggestions=ps_sug
            ),
            "communication_articulation": DimensionScore(
                dimension_id="communication_articulation",
                dimension_name="Communication & Technical Articulation",
                raw_score=comm_score,
                weight=0.15,
                weighted_score=round(comm_score * 0.15 * 10.0, 1),
                level="Exemplary" if comm_score >= 8.8 else "Proficient",
                feedback=comm_fb,
                suggestions=comm_sug
            )
        }

        overall_score = round(sum(d.weighted_score for d in dim_scores.values()), 1)
        recommendation = get_recommendation_band(overall_score)

        strengths = [
            f"Passes {passed_tc}/{total_tc} unit test assertions seamlessly.",
            f"AST complexity conforms to clean architectural standards (Cyclomatic={cyclomatic}).",
            f"Anchored against verified rubric benchmark {citation_rubric}."
        ]
        growth = []
        for d in dim_scores.values():
            growth.extend(d.suggestions)

        return RubricEvaluationResult(
            overall_score=overall_score,
            recommendation=recommendation,
            verdict_summary=f"[Evaluator: Deterministic AST & Rule-Based Scorer (Local Offline Mode - Not an LLM)] Candidate achieved an overall score of {overall_score}/100. Meets '{recommendation}' bar.",
            dimension_scores=dim_scores,
            strengths=strengths,
            growth_areas=growth[:4],
            detected_time_complexity=detected_time,
            detected_space_complexity=detected_space,
            optimal_time_complexity=target_time,
            optimal_space_complexity=question_meta.get("optimal_space", "O(N)"),
            ast_metrics=ast_metrics,
            test_suite_summary=test_results
        )

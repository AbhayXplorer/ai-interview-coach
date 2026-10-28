"""
Sandboxed Code Execution Engine with Test Suite Runner.
Executes candidate code in an isolated subprocess with strict timeouts,
safety guardrails, and test case assertion evaluation.
"""

import sys
import json
import time
import subprocess
import tempfile
import os
from typing import Dict, Any, List

# Blocked dangerous keywords to prevent host machine compromise
DISALLOWED_PATTERNS = [
    "import os", "from os import",
    "import subprocess", "from subprocess import",
    "import socket", "from socket import",
    "import shutil", "from shutil import",
    "open(", "__import__", "eval(", "exec(",
    "fork", "kill", "system("
]

HARNESS_TEMPLATE = '''
import sys
import json
import time

# JSON literal compatibility aliases
true = True
false = False
null = None

# --- Candidate Code ---
{candidate_code}

# --- Test Runner Harness ---
def serialize_val(val):
    try:
        return json.dumps(val)
    except Exception:
        return str(val)

test_cases = json.loads({test_cases_json_literal})
results = []
all_passed = True


start_overall = time.perf_counter()

for idx, tc in enumerate(test_cases):
    test_id = tc.get("id", idx + 1)
    func_name = tc.get("entrypoint", "solution")
    args = tc.get("input_args", [])
    expected = tc.get("expected", None)
    is_hidden = tc.get("hidden", False)
    
    case_res = {{
        "id": test_id,
        "input_args": args,
        "expected": expected,
        "actual": None,
        "passed": False,
        "error": None,
        "duration_ms": 0.0,
        "hidden": is_hidden
    }}
    
    t0 = time.perf_counter()
    try:
        if func_name not in globals():
            candidates = [
                k for k, v in globals().items()
                if callable(v) and not k.startswith('_')
                and k not in {{'serialize_val', 'json', 'sys', 'time', 'test_cases', 'results', 'execute_test_cases', 'start_overall'}}
            ]
            if candidates:
                func_name = candidates[0]
            else:
                raise NameError(f"Entrypoint function '{{func_name}}' not found in candidate code.")
        
        func = globals()[func_name]
        actual = func(*args)
        t1 = time.perf_counter()
        
        case_res["duration_ms"] = round((t1 - t0) * 1000.0, 3)
        case_res["actual"] = actual
        
        # Comparison logic: handles lists, numbers, dicts
        if actual == expected:
            case_res["passed"] = True
        else:
            all_passed = False
    except Exception as e:
        t1 = time.perf_counter()
        case_res["duration_ms"] = round((t1 - t0) * 1000.0, 3)
        case_res["error"] = f"{{type(e).__name__}}: {{str(e)}}"
        all_passed = False
        
    results.append(case_res)

total_duration_ms = round((time.perf_counter() - start_overall) * 1000.0, 2)
output_payload = {{
    "all_passed": all_passed,
    "total_tests": len(test_cases),
    "passed_tests": sum(1 for r in results if r["passed"]),
    "failed_tests": sum(1 for r in results if not r["passed"]),
    "total_duration_ms": total_duration_ms,
    "test_results": results
}}

print("---TEST_RUNNER_START---")
print(json.dumps(output_payload))
print("---TEST_RUNNER_END---")
'''

def check_code_safety(code_str: str) -> List[str]:
    """Scan candidate code for malicious patterns or unauthorized operations."""
    warnings = []
    lines = code_str.splitlines()
    for lineno, line in enumerate(lines, 1):
        clean_line = line.strip()
        if clean_line.startswith("#"):
            continue
        for pattern in DISALLOWED_PATTERNS:
            if pattern in clean_line:
                warnings.append(f"Security Alert (line {lineno}): Disallowed pattern '{pattern}' detected.")
    return warnings


def execute_test_cases(candidate_code: str, test_cases: List[Dict[str, Any]], timeout_sec: float = 3.0) -> Dict[str, Any]:
    """
    Executes candidate code against test cases in an isolated subprocess.
    """
    # 1. Pre-execution safety check
    safety_violations = check_code_safety(candidate_code)
    if safety_violations:
        return {
            "success": False,
            "security_blocked": True,
            "error": "Execution blocked due to security policy violations.",
            "violations": safety_violations,
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "test_results": []
        }

    # 2. Build test harness
    full_script = HARNESS_TEMPLATE.format(
        candidate_code=candidate_code,
        test_cases_json_literal=json.dumps(json.dumps(test_cases))
    )

    # 3. Write temp file and execute
    tmp_file = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(full_script)
            tmp_file = f.name

        t_start = time.perf_counter()
        proc = subprocess.run(
            [sys.executable, tmp_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec
        )
        elapsed_ms = round((time.perf_counter() - t_start) * 1000.0, 2)

        stdout = proc.stdout
        stderr = proc.stderr

        if proc.returncode != 0:
            return {
                "success": False,
                "security_blocked": False,
                "error": f"Runtime Exception (code {proc.returncode}):\n{stderr.strip() or stdout.strip()}",
                "all_passed": False,
                "passed_count": 0,
                "total_count": len(test_cases),
                "duration_ms": elapsed_ms,
                "test_results": []
            }

        # Parse test results from stdout delimiter
        if "---TEST_RUNNER_START---" in stdout and "---TEST_RUNNER_END---" in stdout:
            part = stdout.split("---TEST_RUNNER_START---")[1].split("---TEST_RUNNER_END---")[0].strip()
            parsed = json.loads(part)
            return {
                "success": True,
                "security_blocked": False,
                "error": None,
                "all_passed": parsed["all_passed"],
                "passed_count": parsed["passed_tests"],
                "total_count": parsed["total_tests"],
                "duration_ms": parsed["total_duration_ms"],
                "test_results": parsed["test_results"],
                "stdout_logs": stdout.split("---TEST_RUNNER_START---")[0].strip()
            }
        else:
            return {
                "success": False,
                "security_blocked": False,
                "error": "Failed to parse runner output:\n" + stdout,
                "all_passed": False,
                "passed_count": 0,
                "total_count": len(test_cases),
                "duration_ms": elapsed_ms,
                "test_results": []
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "security_blocked": False,
            "error": f"Time Limit Exceeded (TLE): Code took longer than {timeout_sec}s. Check for infinite loops or non-terminating recursion.",
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "test_results": []
        }
    except Exception as e:
        return {
            "success": False,
            "security_blocked": False,
            "error": f"Runner harness error: {str(e)}",
            "all_passed": False,
            "passed_count": 0,
            "total_count": len(test_cases),
            "test_results": []
        }
    finally:
        if tmp_file and os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except Exception:
                pass

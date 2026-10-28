"""
Static Abstract Syntax Tree (AST) Code Analyzer for Python Submissions.
Performs deterministic static code analysis, detecting algorithmic patterns,
cyclomatic complexity, recursion, loop nesting, and code style issues.
"""

import ast
from typing import Dict, Any, List, Set

class ASTMetricsVisitor(ast.NodeVisitor):
    def __init__(self):
        self.function_defs: List[str] = []
        self.loop_count: int = 0
        self.max_loop_nesting: int = 0
        self.current_loop_nesting: int = 0
        self.if_count: int = 0
        self.recursion_detected: bool = False
        self.data_structures_used: Set[str] = set()
        self.variable_names: Set[str] = set()
        self.single_char_vars: Set[str] = set()
        self.node_count: int = 0
        self.cyclomatic_complexity: int = 1  # Base complexity = 1
        self.has_docstring: bool = False
        self.has_type_hints: bool = False
        self.imported_modules: Set[str] = set()

    def generic_visit(self, node):
        self.node_count += 1
        super().generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.function_defs.append(node.name)
        # Check docstring
        if (node.body and isinstance(node.body[0], ast.Expr) and 
            isinstance(node.body[0].value, (ast.Str, ast.Constant))):
            self.has_docstring = True
            
        # Check return annotations or arg annotations
        if node.returns or any(arg.annotation for arg in node.args.args):
            self.has_type_hints = True

        # Check for recursive call within body
        for subnode in ast.walk(node):
            if isinstance(subnode, ast.Call):
                if isinstance(subnode.func, ast.Name) and subnode.func.id == node.name:
                    self.recursion_detected = True
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.loop_count += 1
        self.cyclomatic_complexity += 1
        self.current_loop_nesting += 1
        if self.current_loop_nesting > self.max_loop_nesting:
            self.max_loop_nesting = self.current_loop_nesting
        self.generic_visit(node)
        self.current_loop_nesting -= 1

    def visit_While(self, node: ast.While):
        self.loop_count += 1
        self.cyclomatic_complexity += 1
        self.current_loop_nesting += 1
        if self.current_loop_nesting > self.max_loop_nesting:
            self.max_loop_nesting = self.current_loop_nesting
        self.generic_visit(node)
        self.current_loop_nesting -= 1

    def visit_If(self, node: ast.If):
        self.if_count += 1
        self.cyclomatic_complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        # 'and' or 'or' adds to cyclomatic complexity
        self.cyclomatic_complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imported_modules.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imported_modules.add(node.module)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Store):
            self.variable_names.add(node.id)
            if len(node.id) == 1 and node.id not in {'i', 'j', 'k', '_', 'n'}:
                self.single_char_vars.add(node.id)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if func_name in {'dict', 'set', 'list', 'tuple', 'deque', 'defaultdict'}:
                self.data_structures_used.add(func_name)
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in {'append', 'pop', 'add', 'get', 'heappush', 'heappop'}:
                self.data_structures_used.add(node.func.attr)
        self.generic_visit(node)

    def visit_Dict(self, node: ast.Dict):
        self.data_structures_used.add('dict_literal')
        self.generic_visit(node)

    def visit_Set(self, node: ast.Set):
        self.data_structures_used.add('set_literal')
        self.generic_visit(node)

    def visit_List(self, node: ast.List):
        self.data_structures_used.add('list_literal')
        self.generic_visit(node)


def analyze_python_code(code_str: str) -> Dict[str, Any]:
    """Parse and statically analyze Python code."""
    result: Dict[str, Any] = {
        "valid_syntax": True,
        "syntax_error": None,
        "loc": len([line for line in code_str.splitlines() if line.strip() and not line.strip().startswith('#')]),
        "total_lines": len(code_str.splitlines()),
        "cyclomatic_complexity": 1,
        "max_loop_nesting": 0,
        "loop_count": 0,
        "if_count": 0,
        "recursion_detected": False,
        "functions_defined": [],
        "single_char_vars": [],
        "data_structures": [],
        "has_docstring": False,
        "has_type_hints": False,
        "imported_modules": [],
        "heuristic_time_complexity": "O(1)",
        "heuristic_space_complexity": "O(1)"
    }

    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        result["valid_syntax"] = False
        result["syntax_error"] = f"SyntaxError at line {e.lineno}, col {e.offset}: {e.msg}"
        return result
    except Exception as e:
        result["valid_syntax"] = False
        result["syntax_error"] = f"Parse error: {str(e)}"
        return result

    visitor = ASTMetricsVisitor()
    visitor.visit(tree)

    result["cyclomatic_complexity"] = visitor.cyclomatic_complexity
    result["max_loop_nesting"] = visitor.max_loop_nesting
    result["loop_count"] = visitor.loop_count
    result["if_count"] = visitor.if_count
    result["recursion_detected"] = visitor.recursion_detected
    result["functions_defined"] = visitor.function_defs
    result["single_char_vars"] = sorted(list(visitor.single_char_vars))
    result["data_structures"] = sorted(list(visitor.data_structures_used))
    result["has_docstring"] = visitor.has_docstring
    result["has_type_hints"] = visitor.has_type_hints
    result["imported_modules"] = sorted(list(visitor.imported_modules))

    # Heuristic Time Complexity Estimation from AST
    if visitor.recursion_detected:
        if visitor.loop_count > 0:
            result["heuristic_time_complexity"] = "O(N * 2^N) or O(N log N)"
        else:
            result["heuristic_time_complexity"] = "O(2^N) or O(N) depending on recurrence"
    elif visitor.max_loop_nesting >= 3:
        result["heuristic_time_complexity"] = "O(N^3) [Cubic]"
    elif visitor.max_loop_nesting == 2:
        result["heuristic_time_complexity"] = "O(N^2) [Quadratic]"
    elif visitor.max_loop_nesting == 1:
        result["heuristic_time_complexity"] = "O(N) [Linear]"
    else:
        result["heuristic_time_complexity"] = "O(1) [Constant]"

    # Heuristic Space Complexity
    if visitor.recursion_detected:
        result["heuristic_space_complexity"] = "O(N) [Recursion Call Stack]"
    elif any(ds in visitor.data_structures_used for ds in ['dict_literal', 'dict', 'set_literal', 'set', 'list_literal', 'list']):
        result["heuristic_space_complexity"] = "O(N) [Auxiliary Hash Table / Array]"
    else:
        result["heuristic_space_complexity"] = "O(1) [Constant In-Place]"

    return result

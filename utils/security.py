"""
Code security validation and sandboxing utilities.

This module provides security checks for generated code:
- AST-based code analysis
- Dangerous import detection
- Dangerous function call detection
- Resource limits for code execution
"""

import ast
import logging
import resource
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional

from config import config

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Custom exception for security violations."""
    pass


class CodeSecurityValidator:
    """Validator for generated code security."""

    # Dangerous imports that could be used maliciously
    DANGEROUS_IMPORTS = {
        "os",  # File system access
        "subprocess",  # Command execution
        "sys",  # System access
        "shutil",  # File operations
        "glob",  # File system traversal
        "pathlib",  # File system access
        "importlib",  # Dynamic imports
        "eval",  # Code evaluation
        "exec",  # Code execution
        "compile",  # Code compilation
        "__import__",  # Dynamic imports
        "open",  # File access (builtin)
        "input",  # User input (could hang)
        "pickle",  # Arbitrary code execution
        "shelve",  # Pickle-based storage
        "socket",  # Network access
        "urllib",  # Network access
        "requests",  # Network access (though might be needed)
        "ftplib",  # Network access
        "telnetlib",  # Network access
        "smtplib",  # Network access
        "ctypes",  # Low-level memory access
        "multiprocessing",  # Process creation
        "threading",  # Thread creation
        "asyncio",  # Async operations (might be needed for Shiny)
    }

    # Allowed imports for Shiny apps
    ALLOWED_IMPORTS = {
        "pandas",
        "numpy",
        "plotly",
        "plotly.express",
        "plotly.graph_objects",
        "shiny",
        "shiny.ui",
        "shiny.render",
        "shiny.reactive",
        "pygwalker",
        "matplotlib",
        "matplotlib.pyplot",
        "seaborn",
        "scipy",
        "sklearn",
        "datetime",
        "json",
        "csv",
        "re",
        "math",
        "statistics",
        "collections",
        "itertools",
        "functools",
        "typing",
    }

    # Dangerous function calls
    DANGEROUS_FUNCTIONS = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "open",  # Direct file access
        "input",  # Could hang
        "exit",
        "quit",
        "help",
    }

    def __init__(self, strict: bool = False):
        """
        Initialize code security validator.

        Args:
            strict: If True, only allow explicitly whitelisted imports
        """
        self.strict = strict

    def validate_code(self, code: str) -> Tuple[bool, List[str]]:
        """
        Validate generated code for security issues.

        Args:
            code: Python code to validate

        Returns:
            Tuple of (is_safe, list_of_issues)

        Example:
            >>> validator = CodeSecurityValidator()
            >>> is_safe, issues = validator.validate_code("import os\\nos.system('ls')")
            >>> print(is_safe, issues)
            False ['Dangerous import: os', 'Dangerous function call: system']
        """
        issues = []

        try:
            # Parse code into AST
            tree = ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            return False, issues

        # Check imports
        import_issues = self._check_imports(tree)
        issues.extend(import_issues)

        # Check function calls
        function_issues = self._check_function_calls(tree)
        issues.extend(function_issues)

        # Check for dangerous patterns
        pattern_issues = self._check_dangerous_patterns(tree)
        issues.extend(pattern_issues)

        is_safe = len(issues) == 0
        return is_safe, issues

    def _check_imports(self, tree: ast.AST) -> List[str]:
        """Check for dangerous imports."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module_name = alias.name
                    if self._is_dangerous_import(module_name):
                        issues.append(f"Dangerous import: {module_name}")

            elif isinstance(node, ast.ImportFrom):
                module_name = node.module or ""
                if self._is_dangerous_import(module_name):
                    issues.append(f"Dangerous import: {module_name}")

                # Check individual imported names
                for alias in node.names:
                    name = alias.name
                    if name in self.DANGEROUS_FUNCTIONS:
                        issues.append(f"Dangerous import: {module_name}.{name}")

        return issues

    def _is_dangerous_import(self, module_name: str) -> bool:
        """Check if an import is dangerous."""
        # Get the root module name
        root_module = module_name.split(".")[0]

        if self.strict:
            # In strict mode, only allow whitelisted imports
            return root_module not in self.ALLOWED_IMPORTS
        else:
            # In normal mode, block dangerous imports
            return root_module in self.DANGEROUS_IMPORTS

    def _check_function_calls(self, tree: ast.AST) -> List[str]:
        """Check for dangerous function calls."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                # Get function name
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in self.DANGEROUS_FUNCTIONS:
                    issues.append(f"Dangerous function call: {func_name}")

        return issues

    def _check_dangerous_patterns(self, tree: ast.AST) -> List[str]:
        """Check for other dangerous patterns."""
        issues = []

        for node in ast.walk(tree):
            # Check for infinite loops (basic check)
            if isinstance(node, ast.While):
                if isinstance(node.test, ast.Constant) and node.test.value is True:
                    issues.append("Potential infinite loop: while True")

            # Check for large allocations
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in {"range", "list", "dict", "set"}:
                        # Check if arguments are too large
                        for arg in node.args:
                            if isinstance(arg, ast.Constant):
                                if isinstance(arg.value, int) and arg.value > 1000000:
                                    issues.append(
                                        f"Potentially large allocation: "
                                        f"{node.func.id}({arg.value})"
                                    )

        return issues


def set_resource_limits(
    max_memory_mb: Optional[int] = None,
    max_cpu_time: Optional[int] = None
):
    """
    Set resource limits for code execution (Unix only).

    Args:
        max_memory_mb: Maximum memory in MB
        max_cpu_time: Maximum CPU time in seconds

    Note:
        This only works on Unix-like systems.
        Windows does not support resource limits this way.
    """
    if sys.platform == "win32":
        logger.warning("Resource limits not supported on Windows")
        return

    try:
        # Set memory limit
        if max_memory_mb is None:
            max_memory_mb = config.max_memory_mb

        max_memory_bytes = max_memory_mb * 1024 * 1024
        resource.setrlimit(
            resource.RLIMIT_AS,
            (max_memory_bytes, max_memory_bytes)
        )
        logger.debug(f"Set memory limit to {max_memory_mb}MB")

        # Set CPU time limit
        if max_cpu_time is None:
            max_cpu_time = config.code_execution_timeout

        resource.setrlimit(
            resource.RLIMIT_CPU,
            (max_cpu_time, max_cpu_time)
        )
        logger.debug(f"Set CPU time limit to {max_cpu_time}s")

    except Exception as e:
        logger.warning(f"Failed to set resource limits: {e}")


def execute_code_sandboxed(
    code_file: Path,
    timeout: Optional[int] = None,
    capture_output: bool = True
) -> Tuple[int, str, str]:
    """
    Execute Python code in a sandboxed subprocess.

    Args:
        code_file: Path to Python file to execute
        timeout: Execution timeout in seconds
        capture_output: Whether to capture stdout/stderr

    Returns:
        Tuple of (return_code, stdout, stderr)

    Raises:
        TimeoutError: If execution exceeds timeout
        subprocess.SubprocessError: If execution fails
    """
    if timeout is None:
        timeout = config.code_execution_timeout

    logger.info(f"Executing code: {code_file} (timeout: {timeout}s)")

    try:
        # Execute in subprocess
        result = subprocess.run(
            [sys.executable, str(code_file)],
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            # Prevent subprocess from accessing parent's resources
            env={
                "PYTHONPATH": "",  # Isolate Python path
                "PATH": os.environ.get("PATH", ""),  # Keep PATH for Python
            },
        )

        logger.info(
            f"Code execution completed: return_code={result.returncode}"
        )

        return result.returncode, result.stdout, result.stderr

    except subprocess.TimeoutExpired as e:
        logger.error(f"Code execution timeout after {timeout}s")
        raise TimeoutError(
            f"Code execution exceeded {timeout}s timeout"
        ) from e

    except Exception as e:
        logger.error(f"Code execution failed: {e}")
        raise


# Import os for environment variables in execute_code_sandboxed
import os

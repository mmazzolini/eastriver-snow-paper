"""Compare the code of a repository script with its original, ignoring comments and docstrings.

Both files are parsed with the Python ast module; docstrings and other bare string
statements (the triple-quoted blocks used in the originals to switch code off) are
removed, the trees are printed back with ast.unparse (this drops comments and
normalises formatting) and leading indentation is stripped, so that moving code
into an if/else branch is not reported. The remaining line differences are printed
as a unified diff (lines starting with '-' are only in the original, '+' only in
the new script). All repository scripts are also byte-compiled (py_compile).

Inputs:  pairs of files given on the command line.
Outputs: text on stdout.
Environment: Python >= 3.9 (ast.unparse).
Run:     python checks/check_code_diff.py <original.py> <new.py> [<original2.py> <new2.py> ...]
Original: new check script.
"""
import ast
import difflib
import glob
import os
import py_compile
import sys
import tempfile

# ---- paths and settings ------------------------------------------------------
REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DropStrings(ast.NodeTransformer):
    """Remove bare string statements (docstrings, commented-out blocks)."""

    def generic_visit(self, node):
        super().generic_visit(node)
        for field in ('body', 'orelse', 'finalbody'):
            stmts = getattr(node, field, None)
            if isinstance(stmts, list):
                kept = [s for s in stmts if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                                                 and isinstance(s.value.value, str))]
                if not kept and stmts and field == 'body' and not isinstance(node, ast.Module):
                    kept = [ast.Pass()]
                setattr(node, field, kept)
        return node


def normalised_lines(path):
    tree = DropStrings().visit(ast.parse(open(path).read()))
    return [ln.strip() for ln in ast.unparse(tree).splitlines() if ln.strip()]


print('== py_compile of the repository scripts')
for p in sorted(glob.glob(os.path.join(REPO_DIR, '*.py')) + glob.glob(os.path.join(REPO_DIR, 'checks', '*.py'))):
    try:
        with tempfile.TemporaryDirectory() as tmp:  # do not write __pycache__ into the repository
            py_compile.compile(p, doraise=True, cfile=os.path.join(tmp, 'x.pyc'))
        print('  OK  ', os.path.relpath(p, REPO_DIR))
    except py_compile.PyCompileError as err:
        print('  FAIL', os.path.relpath(p, REPO_DIR), err)

pairs = sys.argv[1:]
for orig, new in zip(pairs[0::2], pairs[1::2]):
    a, b = normalised_lines(orig), normalised_lines(new)
    diff = list(difflib.unified_diff(a, b, fromfile=orig, tofile=new, lineterm='', n=0))
    n_minus = sum(1 for d in diff if d.startswith('-') and not d.startswith('---'))
    n_plus = sum(1 for d in diff if d.startswith('+') and not d.startswith('+++'))
    print(f'\n== {orig}  ->  {new}')
    print(f'   code lines: original {len(a)}, new {len(b)}; only in original {n_minus}, only in new {n_plus}')
    for d in diff:
        print('   ' + d)

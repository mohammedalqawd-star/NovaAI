import ast
import operator as op
import re
from dataclasses import dataclass

@dataclass
class Intent:
    kinds: list[str]
    query: str

async def route(text: str, ai=None) -> Intent:
    t = text.lower().strip()
    kinds = []
    if re.search(r"(?:\d|\))\s*[+\-*/%^]\s*(?:\d|\()", t) and not re.search(r"[a-zA-Z]{3,}", t):
        kinds.append("CALCULATOR")
    if any(x in t for x in ["ابحث", "آخر الأخبار", "اخر الاخبار", "latest", "news", "سعر اليوم", "حاليًا", "حاليا"]):
        kinds.append("SEARCH")
    if any(x in t for x in ["ترجم", "translate", "translation"]):
        kinds.append("TRANSLATION")
    if any(x in t for x in ["لخص", "تلخيص", "summarize", "summary"]):
        kinds.append("SUMMARY")
    if any(x in t for x in ["اكتب", "إعلان", "اعلان", "منشور", "سيناريو", "write", "copywriting"]):
        kinds.append("WRITING")
    if any(x in t for x in ["كود", "برمج", "python", "javascript", "debug", "code"]):
        kinds.append("CODE")
    if not kinds:
        kinds = ["GENERAL_AI"]
    return Intent(kinds=kinds, query=text)

_ALLOWED = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv, ast.Mod: op.mod, ast.Pow: op.pow, ast.USub: op.neg}

def safe_calculate(expression: str):
    expression = expression.replace("^", "**")
    tree = ast.parse(expression, mode="eval")
    def calc(node):
        if isinstance(node, ast.Expression): return calc(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED: return _ALLOWED[type(node.op)](calc(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED:
            a, b = calc(node.left), calc(node.right)
            if isinstance(node.op, ast.Pow) and abs(b) > 100: raise ValueError("exponent too large")
            return _ALLOWED[type(node.op)](a, b)
        raise ValueError("unsupported expression")
    result = calc(tree)
    if abs(result) > 10**100: raise ValueError("result too large")
    return result

from __future__ import annotations
from pathlib import Path
import io

MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TEXT_CHARS = 50000


def extract_text(filename: str, data: bytes) -> str:
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("الملف أكبر من الحد المسموح (8MB).")
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md", ".py", ".js", ".ts", ".json", ".csv", ".log"}:
        text = data.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("نوع الملف غير مدعوم. المدعوم: PDF, DOCX, TXT, MD, CSV, JSON والكود.")
    return text[:MAX_TEXT_CHARS]


def analyze_csv(data: bytes) -> str:
    import pandas as pd
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("الملف أكبر من الحد المسموح (8MB).")
    df = pd.read_csv(io.BytesIO(data))
    lines = [f"الصفوف: {len(df)}", f"الأعمدة: {len(df.columns)}", "الأعمدة: " + ", ".join(map(str, df.columns))]
    missing = df.isna().sum()
    missing = missing[missing > 0]
    if not missing.empty:
        lines.append("القيم الناقصة: " + ", ".join(f"{k}={v}" for k, v in missing.items()))
    numeric = df.select_dtypes(include="number")
    if not numeric.empty:
        lines.append("المتوسطات الرقمية:")
        lines.extend(f"- {col}: {numeric[col].mean():.4g}" for col in numeric.columns)
    return "\n".join(lines)

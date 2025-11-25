# backend/routers/dev.py
import io
import os
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

# reuse existing parsing utilities if available
try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import docx
except Exception:
    docx = None

router = APIRouter(prefix="/api/dev", tags=["dev"])

def extract_text_from_pdf_bytes(file_bytes: bytes) -> str:
    text = ""
    if not PyPDF2:
        return ""
    try:
        reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
        pages = []
        for p in reader.pages:
            try:
                t = p.extract_text() or ""
                pages.append(t)
            except Exception:
                continue
        text = "\n\n".join(pages)
    except Exception:
        text = ""
    return text

@router.get("/sample-resume")
def sample_resume(path: str = Query(..., description="Absolute path on server to resume file")):
    """
    DEV route: read a local file and return parsed text.
    Usage: GET /api/dev/sample-resume?path=/mnt/data/web-developer-resume-example.pdf
    """
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found on server")

    try:
        with open(path, "rb") as f:
            b = f.read()

        content = ""
        if path.lower().endswith(".pdf"):
            content = extract_text_from_pdf_bytes(b)
        elif path.lower().endswith(".docx"):
            if docx:
                try:
                    doc = docx.Document(io.BytesIO(b))
                    content = "\n".join([p.text for p in doc.paragraphs])
                except Exception:
                    content = ""
        else:
            # try simple decode fallback
            try:
                content = b.decode("utf-8", errors="ignore")
            except Exception:
                content = ""

        # if extraction is too small, return a helpful message instead of blank
        if not content or len(content.strip()) < 20:
            return JSONResponse({"status": "partial", "data": {"content": "", "message": "Extraction empty; consider enabling OCR on backend"}}, status_code=200)

        return {"status": "success", "data": {"content": content}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")


import os
import time
from typing import List

from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
import pdfplumber
import docx
from openai import OpenAI
from dotenv import load_dotenv

# -----------------------------
# Setup
# -----------------------------
load_dotenv()


client = OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI(title="Course Guide Generator (Single File)")
router = APIRouter()

# -----------------------------
# Utils (merged from utils.py)
# -----------------------------
def extract_text_from_file(file_path: str) -> str:
    if file_path.lower().endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    elif file_path.lower().endswith(".docx"):
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        raise ValueError("Unsupported file type. Only PDF and DOCX are allowed.")

def generate_course_guide(text: str) -> str:
    prompt = f"""
You are an expert university lecturer and curriculum designer.

Given the following course descriptor, generate a detailed weekly course guide.
Each week should include:
- Week number
- Topic(s)
- Learning objectives
- Teaching activities (lectures, labs, assignments)
- Assessment (if any)

Course Descriptor:
\"\"\"{text}\"\"\""""
    resp = client.chat.completions.create(
        model="gpt-4o-mini",  # or "gpt-4o" / another current model available to your account
        messages=[
            {"role": "system", "content": "You generate structured university course content from raw input."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.5,
        timeout=60,  # per-request timeout (supported by the SDK)
    )
    return resp.choices[0].message.content

# -----------------------------
# API (merged from api.py)
# -----------------------------
@router.post("/generate/")
async def generate(files: List[UploadFile] = File(...)):
    start_time = time.time()
    print("Received files:", [file.filename for file in files])

    full_text = ""

    for file in files:
        if not (file.filename.endswith(".pdf") or file.filename.endswith(".docx")):
            raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

        contents = await file.read()
        temp_path = f"temp_{file.filename}"

        with open(temp_path, "wb") as f:
            f.write(contents)
        print(f"Saved: {temp_path}")

        try:
            extracted_text = extract_text_from_file(temp_path)
            print(f"Extracted {len(extracted_text)} characters from {file.filename}")
            full_text += extracted_text + "\n"
        finally:
            try:
                os.remove(temp_path)
                print(f"Deleted: {temp_path}")
            except FileNotFoundError:
                pass

    if not full_text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in uploaded files.")

    print("Calling OpenAI to generate course guide...")
    generated_guide = generate_course_guide(full_text)
    elapsed_time = round(time.time() - start_time, 2)
    print(f"Course guide generated in {elapsed_time} seconds.")

    return {
        "status": "success",
        "duration_seconds": elapsed_time,
        "generated_course_guide": generated_guide
    }

# -----------------------------
# App wiring (merged from main.py)
# -----------------------------
app.include_router(router)

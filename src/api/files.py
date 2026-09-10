import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from pypdf import PdfReader
from src.api.auth import get_current_user
from src.services.db import get_connection

router = APIRouter()

UPLOAD_DIR = "data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

@router.post("/upload")
async def upload_file(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dosya adı yok.")
        
    ext = file.filename.split('.')[-1].lower()
    if ext not in ['txt', 'pdf', 'md']:
        raise HTTPException(status_code=400, detail="Sadece PDF, TXT ve MD dosyaları desteklenir.")

    content = await file.read()
    size = len(content)
    if size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Dosya boyutu en fazla 10 MB olabilir.")
        
    file_id = str(uuid.uuid4())
    safe_filename = f"{file_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_path, "wb") as f:
        f.write(content)

    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Check if project belongs to user
        cursor.execute("SELECT id FROM projects WHERE id = ? AND user_id = ?", (project_id, user["id"]))
        if not cursor.fetchone():
            raise HTTPException(status_code=403, detail="Projeye erişim izniniz yok.")
            
        cursor.execute('''
            INSERT INTO files (id, user_id, project_id, filename, file_type, size)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (file_id, user["id"], project_id, file.filename, ext, size))
        
        # Parse and chunk
        chunks_to_insert = []
        if ext == 'pdf':
            reader = PdfReader(file_path)
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    page_chunks = split_text_into_chunks(text)
                    for idx, chunk in enumerate(page_chunks):
                        chunks_to_insert.append((page_num + 1, idx, chunk))
        else:
            text = content.decode('utf-8', errors='ignore')
            text_chunks = split_text_into_chunks(text)
            for idx, chunk in enumerate(text_chunks):
                chunks_to_insert.append((1, idx, chunk))
                
        for page_num, chunk_index, chunk_text in chunks_to_insert:
            chunk_id = str(uuid.uuid4())
            cursor.execute('''
                INSERT INTO document_chunks (id, user_id, project_id, file_id, page_number, chunk_index, content)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (chunk_id, user["id"], project_id, file_id, page_num, chunk_index, chunk_text))
            
            # Insert into FTS
            cursor.execute('''
                INSERT INTO document_chunks_fts (rowid, content, chunk_id)
                VALUES (last_insert_rowid(), ?, ?)
            ''', (chunk_text, chunk_id))
            
        conn.commit()
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Dosya işlenirken hata oluştu: {str(e)}")
    finally:
        conn.close()
        
    return {"status": "success", "file_id": file_id, "message": "Dosya başarıyla yüklendi ve indekslendi."}

@router.get("/project/{project_id}")
async def list_project_files(project_id: str, user: dict = Depends(get_current_user)):
    conn = get_connection()
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    cursor.execute("SELECT id, filename, file_type, size, created_at FROM files WHERE project_id = ? AND user_id = ?", (project_id, user["id"]))
    rows = cursor.fetchall()
    conn.close()
    return rows

@router.delete("/{file_id}")
async def delete_file(file_id: str, user: dict = Depends(get_current_user)):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT filename, file_type FROM files WHERE id = ? AND user_id = ?", (file_id, user["id"]))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
        
    # Delete from FTS first using chunk IDs
    cursor.execute("SELECT id FROM document_chunks WHERE file_id = ?", (file_id,))
    chunk_ids = [c["id"] for c in cursor.fetchall()]
    for cid in chunk_ids:
        cursor.execute("DELETE FROM document_chunks_fts WHERE chunk_id = ?", (cid,))
        
    # Delete from main tables
    cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
    
    conn.commit()
    conn.close()
    
    # Delete file from disk
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}.{row['file_type']}")
    if os.path.exists(file_path):
        os.remove(file_path)
        
    return {"status": "success"}

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

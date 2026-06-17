import os, io, shutil
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Response, Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
from database import get_conn
from auth import hash_password, verify_password, create_token, get_current_user, require_admin, decode_token

router = APIRouter()

UPLOAD_DIR = os.environ.get("UPLOAD_DIR", "/home/claude/ardiyamidly/static/uploads")
VIDEO_DIR  = os.path.join(UPLOAD_DIR, "videos")
PHOTO_DIR  = os.path.join(UPLOAD_DIR, "photos")
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(PHOTO_DIR, exist_ok=True)

# ─────────────── AUTH ───────────────
class LoginBody(BaseModel):
    nama: str
    sandi: str

@router.post("/api/login")
def login(body: LoginBody, response: Response):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE nama=%s", (body.nama,))
    user = cur.fetchone()
    cur.close(); conn.close()
    if not user or not verify_password(body.sandi, user["sandi_hash"]):
        raise HTTPException(400, "Nama atau sandi salah")
    token = create_token(user["id"], user["nama"], user["role"])
    response.set_cookie("token", token, httponly=True, max_age=86400)
    return {"role": user["role"], "nama": user["nama"]}

@router.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("token")
    return {"ok": True}

@router.get("/api/me")
def me(user=Depends(get_current_user)):
    return user

class RegisterBody(BaseModel):
    nama: str
    sandi: str
    role: str = "viewer"

@router.post("/api/users")
def add_user(body: RegisterBody, user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE nama=%s", (body.nama,))
    if cur.fetchone():
        cur.close(); conn.close()
        raise HTTPException(400, "Nama sudah digunakan")
    hashed = hash_password(body.sandi)
    cur.execute("INSERT INTO users (nama, sandi_hash, role) VALUES (%s,%s,%s) RETURNING id",
                (body.nama, hashed, body.role))
    new_id = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()
    return {"id": new_id, "nama": body.nama, "role": body.role}

@router.get("/api/users")
def list_users(user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT id, nama, role, created_at FROM users ORDER BY id")
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@router.delete("/api/users/{uid}")
def delete_user(uid: int, user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE id=%s AND role!='admin' RETURNING id", (uid,))
    row = cur.fetchone(); conn.commit(); cur.close(); conn.close()
    if not row:
        raise HTTPException(404, "User tidak ditemukan atau tidak bisa dihapus")
    return {"ok": True}

# ─────────────── RESEARCH DATA ───────────────
@router.get("/api/research")
def list_research(user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM research_data ORDER BY id")
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@router.post("/api/research")
def add_research(
    nama_ibu: str = Form(...),
    pekerjaan: str = Form(""),
    yang_dirasakan: str = Form(""),
    user=Depends(require_admin)
):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO research_data (nama_ibu, pekerjaan, yang_dirasakan) VALUES (%s,%s,%s) RETURNING id",
        (nama_ibu, pekerjaan, yang_dirasakan)
    )
    new_id = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()
    return {"id": new_id}

@router.put("/api/research/{rid}")
def update_research(
    rid: int,
    nama_ibu: str = Form(...),
    pekerjaan: str = Form(""),
    yang_dirasakan: str = Form(""),
    user=Depends(require_admin)
):
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "UPDATE research_data SET nama_ibu=%s, pekerjaan=%s, yang_dirasakan=%s, updated_at=NOW() WHERE id=%s",
        (nama_ibu, pekerjaan, yang_dirasakan, rid)
    )
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

@router.delete("/api/research/{rid}")
def delete_research(rid: int, user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM research_data WHERE id=%s", (rid,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

# ─────────────── FEEDBACK ───────────────
@router.get("/api/feedback")
def list_feedback(user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM feedback ORDER BY created_at DESC")
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@router.post("/api/feedback")
async def add_feedback(request: Request):
    # Viewer & admin boleh submit feedback — cek token optional
    form = await request.form()
    nama_ibu = form.get("nama_ibu","")
    pengalaman = form.get("pengalaman","")
    perasaan_setelah = form.get("perasaan_setelah","")
    if not nama_ibu:
        raise HTTPException(400, "Nama ibu wajib diisi")
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO feedback (nama_ibu, pengalaman, perasaan_setelah) VALUES (%s,%s,%s) RETURNING id",
        (nama_ibu, pengalaman, perasaan_setelah)
    )
    new_id = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()
    return {"id": new_id}

@router.delete("/api/feedback/{fid}")
def delete_feedback(fid: int, user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("DELETE FROM feedback WHERE id=%s", (fid,))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

# ─────────────── GALLERY ───────────────
@router.get("/api/gallery")
def list_gallery(user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM gallery_photos ORDER BY created_at DESC")
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@router.post("/api/gallery")
async def upload_photo(
    foto: UploadFile = File(...),
    deskripsi: str = Form(""),
    user=Depends(require_admin)
):
    ext = foto.filename.rsplit(".", 1)[-1].lower()
    if ext not in ["jpg","jpeg","png","gif","webp","pdf"]:
        raise HTTPException(400, "Format tidak didukung")
    import uuid
    fname = f"{uuid.uuid4().hex}.{ext}"
    fpath = os.path.join(PHOTO_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(foto.file, f)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO gallery_photos (filename, deskripsi, uploaded_by) VALUES (%s,%s,%s) RETURNING id",
        (fname, deskripsi, user["nama"])
    )
    new_id = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()
    return {"id": new_id, "filename": fname}

@router.put("/api/gallery/{gid}")
def update_gallery(
    gid: int,
    deskripsi: str = Form(""),
    user=Depends(require_admin)
):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("UPDATE gallery_photos SET deskripsi=%s WHERE id=%s", (deskripsi, gid))
    conn.commit(); cur.close(); conn.close()
    return {"ok": True}

@router.delete("/api/gallery/{gid}")
def delete_gallery(gid: int, user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT filename FROM gallery_photos WHERE id=%s", (gid,))
    row = cur.fetchone()
    if row:
        fpath = os.path.join(PHOTO_DIR, row["filename"])
        if os.path.exists(fpath):
            os.remove(fpath)
        cur.execute("DELETE FROM gallery_photos WHERE id=%s", (gid,))
        conn.commit()
    cur.close(); conn.close()
    return {"ok": True}

@router.get("/uploads/photos/{filename}")
def serve_photo(filename: str):
    fpath = os.path.join(PHOTO_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(404, "File tidak ditemukan")
    return FileResponse(fpath)

# ─────────────── VIDEO ───────────────
@router.get("/api/videos")
def list_videos(user=Depends(get_current_user)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT * FROM videos ORDER BY fitur_id, urutan")
    rows = cur.fetchall(); cur.close(); conn.close()
    return rows

@router.post("/api/videos")
async def upload_video(
    fitur_id: int = Form(...),
    judul: str = Form(...),
    judul_en: str = Form(""),
    durasi: str = Form(""),
    urutan: int = Form(1),
    video: UploadFile = File(...),
    user=Depends(require_admin)
):
    ext = video.filename.rsplit(".",1)[-1].lower()
    if ext not in ["mp4","webm","mov"]:
        raise HTTPException(400, "Format video tidak didukung (mp4/webm/mov)")
    import uuid
    fname = f"{uuid.uuid4().hex}.{ext}"
    fpath = os.path.join(VIDEO_DIR, fname)
    with open(fpath, "wb") as f:
        shutil.copyfileobj(video.file, f)
    conn = get_conn(); cur = conn.cursor()
    cur.execute(
        "INSERT INTO videos (fitur_id, judul, judul_en, durasi, filename, urutan) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
        (fitur_id, judul, judul_en, durasi, fname, urutan)
    )
    new_id = cur.fetchone()["id"]
    conn.commit(); cur.close(); conn.close()
    return {"id": new_id, "filename": fname}

@router.delete("/api/videos/{vid}")
def delete_video(vid: int, user=Depends(require_admin)):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT filename FROM videos WHERE id=%s", (vid,))
    row = cur.fetchone()
    if row:
        fpath = os.path.join(VIDEO_DIR, row["filename"])
        if os.path.exists(fpath):
            os.remove(fpath)
        cur.execute("DELETE FROM videos WHERE id=%s", (vid,))
        conn.commit()
    cur.close(); conn.close()
    return {"ok": True}

@router.get("/stream/video/{filename}")
def stream_video(filename: str, request: Request, user=Depends(get_current_user)):
    fpath = os.path.join(VIDEO_DIR, filename)
    if not os.path.exists(fpath):
        raise HTTPException(404, "Video tidak ditemukan")
    file_size = os.path.getsize(fpath)
    range_header = request.headers.get("range")
    chunk = 1024 * 1024  # 1MB chunks

    if range_header:
        start_str, end_str = range_header.replace("bytes=", "").split("-")
        start = int(start_str)
        end = int(end_str) if end_str else min(start + chunk - 1, file_size - 1)
        length = end - start + 1

        def gen():
            with open(fpath, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining:
                    data = f.read(min(8192, remaining))
                    if not data:
                        break
                    remaining -= len(data)
                    yield data

        return StreamingResponse(
            gen(),
            status_code=206,
            media_type="video/mp4",
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(length),
            }
        )

    def gen_full():
        with open(fpath, "rb") as f:
            while True:
                data = f.read(8192)
                if not data:
                    break
                yield data

    return StreamingResponse(
        gen_full(),
        media_type="video/mp4",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
        }
    )

# ─────────────── QR CODE ───────────────
@router.get("/api/qr")
def generate_qr(request: Request, user=Depends(get_current_user)):
    import qrcode
    base_url = str(request.base_url).rstrip("/")
    img = qrcode.make(base_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

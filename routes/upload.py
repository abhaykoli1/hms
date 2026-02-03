# import os
# import uuid
# from fastapi import APIRouter, UploadFile, File, HTTPException

# router = APIRouter(prefix="/upload", tags=["File Upload"])

# # ✅ PROJECT ROOT
# BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

# ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}

# @router.post("/file")
# async def upload_file(
#     file: UploadFile = File(...),
#     folder: str = "documents"
# ):
#     try:
#         print("👉 Upload API hit")
#         print("Filename:", file.filename)

#         upload_dir = os.path.join(UPLOAD_ROOT, folder)
#         os.makedirs(upload_dir, exist_ok=True)

#         # 🔥 TEMP: allow all extensions
#         ext = "bin"
#         if file.filename and "." in file.filename:
#             ext = file.filename.rsplit(".", 1)[-1].lower()

#         unique_name = f"{uuid.uuid4()}.{ext}"
#         file_path = os.path.join(upload_dir, unique_name)

#         data = await file.read()
#         print("FILE SIZE:", len(data))

#         with open(file_path, "wb") as f:
#             f.write(data)

#         return {
#             "success": True,
#             "path": f"/uploads/{folder}/{unique_name}"
#         }

#     except Exception as e:
#         print("🔥 UPLOAD ERROR:", repr(e))
#         raise HTTPException(status_code=500, detail=str(e))
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(prefix="/upload", tags=["File Upload"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_ROOT = os.path.join(BASE_DIR, "uploads")

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    folder: str = "documents"
):
    try:
        if not file.filename:
            raise HTTPException(400, "No file selected")

        # ✅ extension check
        ext = file.filename.rsplit(".", 1)[-1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                400,
                "Only PDF, JPG, JPEG, PNG files are allowed"
            )

        # ✅ read file
        data = await file.read()

        # ✅ size check
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(400, "File size must be under 5MB")

        # ✅ safe folder
        upload_dir = os.path.join(UPLOAD_ROOT, folder)
        os.makedirs(upload_dir, exist_ok=True)

        # ✅ unique filename
        unique_name = f"{uuid.uuid4()}.{ext}"
        file_path = os.path.join(upload_dir, unique_name)

        with open(file_path, "wb") as f:
            f.write(data)

        return {
            "success": True,
            "path": f"/uploads/{folder}/{unique_name}"
        }

    except HTTPException:
        raise
    except Exception as e:
        print("🔥 UPLOAD ERROR:", repr(e))
        raise HTTPException(500, "File upload failed")

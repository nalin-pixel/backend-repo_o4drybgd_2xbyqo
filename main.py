import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from passlib.hash import pbkdf2_sha256

from database import db, create_document, get_documents, update_document, delete_document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}

@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}

# ---------------- Startup Bootstrap ----------------

@app.on_event("startup")
def bootstrap_admin():
    try:
        email = os.getenv("ADMIN_EMAIL")
        if not email:
            return
        docs = get_documents("user", {"email": email}, limit=1)
        if not docs:
            return
        user_id = docs[0]["_id"]
        update_document("user", user_id, {"is_admin": True, "is_verified": True})
    except Exception:
        # Silently continue to avoid blocking server start
        pass

# ---------------- Helpers ----------------

def serialize(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d

# Simple session-based auth using DB-backed tokens
class AuthSession(BaseModel):
    token: str
    user_id: str
    is_admin: bool
    is_verified: bool
    created_at: datetime
    expires_at: datetime


def _get_token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


def get_current_user(request: Request):
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    sess_docs = get_documents("session", {"token": token}, limit=1)
    if not sess_docs:
        raise HTTPException(status_code=401, detail="Invalid token")
    sess = serialize(sess_docs[0])
    # Check expiry
    try:
        if sess.get("expires_at") and datetime.fromisoformat(str(sess["expires_at"])) < datetime.utcnow():
            raise HTTPException(status_code=401, detail="Session expired")
    except Exception:
        pass
    # Load user
    user_docs = get_documents("user", {"_id": sess_docs[0]["user_id"]}, limit=1) if "user_id" in sess_docs[0] else []
    # Fallback by id string
    if not user_docs:
        user_docs = get_documents("user", {"_id": sess.get("user_id")}, limit=1)
    if not user_docs:
        raise HTTPException(status_code=401, detail="User not found")
    user = serialize(user_docs[0])
    user.pop("password_hash", None)
    return user


def get_current_admin(request: Request):
    user = get_current_user(request)
    if not (user.get("is_admin") and user.get("is_verified")):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

# ---------------- Portfolio CMS Models ----------------

class CategoryIn(BaseModel):
    key: str
    title: str
    description: Optional[str] = None

class ClientIn(BaseModel):
    name: str
    category_key: str
    description: Optional[str] = None
    logo_url: Optional[str] = None

class ProjectIn(BaseModel):
    client_name: str
    title: str
    tag: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[str]] = None
    link: Optional[str] = None

class TestimonialIn(BaseModel):
    name: str
    role: Optional[str] = None
    quote: str
    company: Optional[str] = None
    rating: Optional[int] = None
    logo_url: Optional[str] = None
    status: Optional[str] = None  # admin may set status directly

class PublicTestimonialIn(BaseModel):
    name: str
    role: Optional[str] = None
    company: Optional[str] = None
    rating: Optional[int] = None
    quote: str

class SettingIn(BaseModel):
    key: str
    marquee_a_seconds: Optional[float] = 30.0
    marquee_b_seconds: Optional[float] = 28.0
    glow_intensity: Optional[float] = 0.25
    parallax_intensity: Optional[float] = 8.0

# ---------------- Auth & Users ----------------

class SignupIn(BaseModel):
    name: str
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
    is_admin: bool
    is_verified: bool
    created_at: datetime

@app.post("/api/auth/signup", response_model=UserOut)
def signup(user: SignupIn):
    existing = get_documents("user", {"email": user.email}, limit=1)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    # Use PBKDF2-SHA256 to avoid bcrypt backend/version issues & 72-byte limit
    hashed = pbkdf2_sha256.hash(user.password)
    doc = {
        "name": user.name,
        "email": user.email,
        "password_hash": hashed,
        "is_admin": False,
        "is_verified": False,
        "created_at": datetime.utcnow(),
    }
    _id = create_document("user", doc)
    return UserOut(id=_id, name=doc["name"], email=doc["email"], is_admin=False, is_verified=False, created_at=doc["created_at"])  # type: ignore

@app.post("/api/auth/login")
def login(payload: LoginIn):
    docs = get_documents("user", {"email": payload.email}, limit=1)
    if not docs:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    user = docs[0]
    # Verify using PBKDF2-SHA256
    if not pbkdf2_sha256.verify(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = uuid.uuid4().hex
    now = datetime.utcnow()
    session_doc = {
        "token": token,
        "user_id": user["_id"],
        "is_admin": bool(user.get("is_admin")),
        "is_verified": bool(user.get("is_verified")),
        "created_at": now,
        "expires_at": now + timedelta(days=7),
    }
    create_document("session", session_doc)
    safe_user = serialize(user)
    safe_user.pop("password_hash", None)
    return {"token": token, "user": safe_user}

@app.get("/api/auth/me")
def me(user: Dict[str, Any] = Depends(get_current_user)):
    return user

@app.get("/api/users")
def list_users(_: Dict[str, Any] = Depends(get_current_admin)):
    docs = [serialize(d) for d in get_documents("user")]
    for d in docs:
        d.pop("password_hash", None)
    return docs

@app.patch("/api/users/{doc_id}/verify-admin")
def set_admin(doc_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_current_admin)):
    allowed: Dict[str, Any] = {}
    if "is_admin" in payload:
        allowed["is_admin"] = bool(payload["is_admin"])
    if "is_verified" in payload:
        allowed["is_verified"] = bool(payload["is_verified"])
    if not allowed:
        raise HTTPException(status_code=400, detail="No fields to update")
    ok = update_document("user", doc_id, allowed)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found or not modified")
    return {"ok": True}

# ---------------- Seed (admin-only) ----------------

@app.post("/api/seed")
def seed_data(_: Dict[str, Any] = Depends(get_current_admin)):
    existing_categories = {c.get("key"): c for c in get_documents("category")}
    cat_items = [
      {"key": "uiux", "title": "UI/UX", "description": "Interfaces and flows"},
      {"key": "brand", "title": "Brand", "description": "Identity and guidelines"},
    ]
    for c in cat_items:
        if c["key"] not in existing_categories:
            create_document("category", c)

    existing_clients = {c.get("name"): c for c in get_documents("client")}
    client_items = [
      {"name": "VoltPay", "category_key": "uiux", "description": "Fintech payments", "logo_url": "https://logo.clearbit.com/visa.com"},
      {"name": "BloomCo", "category_key": "brand", "description": "D2C beauty", "logo_url": "https://logo.clearbit.com/glossier.com"},
      {"name": "Secura", "category_key": "uiux", "description": "Security SaaS", "logo_url": "https://logo.clearbit.com/okta.com"},
      {"name": "Vitality", "category_key": "uiux", "description": "HealthTech", "logo_url": "https://logo.clearbit.com/fitbit.com"},
      {"name": "Northbeam", "category_key": "brand", "description": "SaaS analytics", "logo_url": "https://logo.clearbit.com/datadog.com"},
    ]
    for cl in client_items:
        if cl["name"] not in existing_clients:
            create_document("client", cl)

    existing_testimonials = {(t.get("name"), t.get("company")): t for t in get_documents("testimonial")}
    testimonial_items = [
      {"name": "A. Santoso", "role": "Product Manager", "company": "VoltPay", "rating": 5, "quote": "Raffi quickly translated complex requirements into clean, intuitive flows. The sprint velocity went up 20%.", "status": "approved"},
      {"name": "N. Wijaya", "role": "Marketing Lead", "company": "BloomCo", "rating": 5, "quote": "Our campaign hit record CTR thanks to a cohesive visual system and analytics-driven adjustments.", "status": "approved"},
      {"name": "J. Park", "role": "Security Lead", "company": "Secura", "rating": 4, "quote": "His blue-team mindset and SIEM knowledge helped us tighten detections without slowing delivery.", "status": "approved"},
      {"name": "M. Rivera", "role": "CTO", "company": "Vitality", "rating": 5, "quote": "From idea to production in three weeks. Clear communication and thoughtful trade-offs throughout.", "status": "approved"},
      {"name": "K. Nguyen", "role": "Founder", "company": "Northbeam", "rating": 5, "quote": "The design system and motion guidelines elevated our brand and sped up feature delivery for the team.", "status": "approved"},
    ]
    for t in testimonial_items:
        key = (t["name"], t["company"])  # type: ignore
        if key not in existing_testimonials:
            create_document("testimonial", t)

    existing_settings = {s.get("key"): s for s in get_documents("setting")}
    if "ui" not in existing_settings:
        create_document("setting", {"key": "ui", "marquee_a_seconds": 30.0, "marquee_b_seconds": 28.0, "glow_intensity": 0.25, "parallax_intensity": 8.0})

    return {"ok": True}

# ---------------- Public Read & Submit Endpoints ----------------

@app.get("/api/categories")
def list_categories():
    docs = get_documents("category")
    return [serialize(d) for d in docs]

@app.get("/api/clients")
def list_clients(category_key: Optional[str] = None):
    filt = {"category_key": category_key} if category_key else {}
    docs = get_documents("client", filt)
    return [serialize(d) for d in docs]

@app.get("/api/projects")
def list_projects(client_name: Optional[str] = None):
    filt = {"client_name": client_name} if client_name else {}
    docs = get_documents("project", filt)
    return [serialize(d) for d in docs]

@app.get("/api/testimonials")
def list_testimonials(client_name: Optional[str] = None, include_all: bool = False, request: Request = None):
    # Public: only show approved by default
    filt: Dict[str, Any] = {"status": "approved"}
    if client_name:
        filt["company"] = client_name

    # If include_all requested, verify admin
    if include_all and request is not None:
        try:
            user = get_current_admin(request)
            if user:
                filt.pop("status", None)
        except Exception:
            # ignore, remain filtered
            pass

    docs = get_documents("testimonial", filt)
    return [serialize(d) for d in docs]

@app.post("/api/testimonials/submit")
def submit_testimonial(payload: PublicTestimonialIn):
    # Clamp rating 0-5
    rating = payload.rating if payload.rating is not None else 5
    try:
        rating = max(0, min(5, int(rating)))
    except Exception:
        rating = 5
    doc = {
        "name": payload.name,
        "role": payload.role,
        "company": payload.company,
        "rating": rating,
        "quote": payload.quote,
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    _id = create_document("testimonial", doc)
    return {"id": _id, "status": "pending"}

@app.get("/api/settings")
def get_settings(key: str = "ui"):
    docs = get_documents("setting", {"key": key}, limit=1)
    return serialize(docs[0]) if docs else {"key": key}

# ---------------- Admin Mutations (protected) ----------------

@app.post("/api/categories")
def create_category(payload: CategoryIn, _: Dict[str, Any] = Depends(get_current_admin)):
    _id = create_document("category", payload.model_dump())
    return {"id": _id}

@app.post("/api/clients")
def create_client(payload: ClientIn, _: Dict[str, Any] = Depends(get_current_admin)):
    _id = create_document("client", payload.model_dump())
    return {"id": _id}

@app.post("/api/projects")
def create_project(payload: ProjectIn, _: Dict[str, Any] = Depends(get_current_admin)):
    _id = create_document("project", payload.model_dump())
    return {"id": _id}

@app.post("/api/testimonials")
def create_testimonial(payload: TestimonialIn, _: Dict[str, Any] = Depends(get_current_admin)):
    data = payload.model_dump()
    if not data.get("status"):
        data["status"] = "approved"  # admin-created are approved by default
    _id = create_document("testimonial", data)
    return {"id": _id}

@app.post("/api/settings")
def create_setting(payload: SettingIn, _: Dict[str, Any] = Depends(get_current_admin)):
    _id = create_document("setting", payload.model_dump())
    return {"id": _id}

@app.patch("/api/categories/{doc_id}")
def update_category(doc_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_current_admin)):
    if not update_document("category", doc_id, payload):
        raise HTTPException(status_code=404, detail="Category not found or not modified")
    return {"ok": True}

@app.patch("/api/clients/{doc_id}")
def update_client(doc_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_current_admin)):
    if not update_document("client", doc_id, payload):
        raise HTTPException(status_code=404, detail="Client not found or not modified")
    return {"ok": True}

@app.patch("/api/projects/{doc_id}")
def update_project(doc_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_current_admin)):
    if not update_document("project", doc_id, payload):
        raise HTTPException(status_code=404, detail="Project not found or not modified")
    return {"ok": True}

@app.patch("/api/testimonials/{doc_id}")
def update_testimonial(doc_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_current_admin)):
    if not update_document("testimonial", doc_id, payload):
        raise HTTPException(status_code=404, detail="Testimonial not found or not modified")
    return {"ok": True}

@app.patch("/api/settings/{doc_id}")
def update_setting(doc_id: str, payload: Dict[str, Any], _: Dict[str, Any] = Depends(get_current_admin)):
    if not update_document("setting", doc_id, payload):
        raise HTTPException(status_code=404, detail="Setting not found or not modified")
    return {"ok": True}

@app.delete("/api/categories/{doc_id}")
def delete_category(doc_id: str, _: Dict[str, Any] = Depends(get_current_admin)):
    if not delete_document("category", doc_id):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"ok": True}

@app.delete("/api/clients/{doc_id}")
def delete_client(doc_id: str, _: Dict[str, Any] = Depends(get_current_admin)):
    if not delete_document("client", doc_id):
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}

@app.delete("/api/projects/{doc_id}")
def delete_project(doc_id: str, _: Dict[str, Any] = Depends(get_current_admin)):
    if not delete_document("project", doc_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}

@app.delete("/api/testimonials/{doc_id}")
def delete_testimonial(doc_id: str, _: Dict[str, Any] = Depends(get_current_admin)):
    if not delete_document("testimonial", doc_id):
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"ok": True}

# ---------------- Diagnostics ----------------

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

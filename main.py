import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

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

# ---------------- Portfolio CMS Endpoints ----------------

# Helper to coerce _id

def serialize(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d

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

# Create routes
@app.post("/api/categories")
def create_category(payload: CategoryIn):
    _id = create_document("category", payload.model_dump())
    return {"id": _id}

@app.post("/api/clients")
def create_client(payload: ClientIn):
    _id = create_document("client", payload.model_dump())
    return {"id": _id}

@app.post("/api/projects")
def create_project(payload: ProjectIn):
    _id = create_document("project", payload.model_dump())
    return {"id": _id}

@app.post("/api/testimonials")
def create_testimonial(payload: TestimonialIn):
    _id = create_document("testimonial", payload.model_dump())
    return {"id": _id}

# Read routes
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
def list_testimonials(client_name: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if client_name:
        filt["company"] = client_name
    docs = get_documents("testimonial", filt)
    return [serialize(d) for d in docs]

# Update routes
@app.patch("/api/categories/{doc_id}")
def update_category(doc_id: str, payload: Dict[str, Any]):
    if not update_document("category", doc_id, payload):
        raise HTTPException(status_code=404, detail="Category not found or not modified")
    return {"ok": True}

@app.patch("/api/clients/{doc_id}")
def update_client(doc_id: str, payload: Dict[str, Any]):
    if not update_document("client", doc_id, payload):
        raise HTTPException(status_code=404, detail="Client not found or not modified")
    return {"ok": True}

@app.patch("/api/projects/{doc_id}")
def update_project(doc_id: str, payload: Dict[str, Any]):
    if not update_document("project", doc_id, payload):
        raise HTTPException(status_code=404, detail="Project not found or not modified")
    return {"ok": True}

@app.patch("/api/testimonials/{doc_id}")
def update_testimonial(doc_id: str, payload: Dict[str, Any]):
    if not update_document("testimonial", doc_id, payload):
        raise HTTPException(status_code=404, detail="Testimonial not found or not modified")
    return {"ok": True}

# Delete routes
@app.delete("/api/categories/{doc_id}")
def delete_category(doc_id: str):
    if not delete_document("category", doc_id):
        raise HTTPException(status_code=404, detail="Category not found")
    return {"ok": True}

@app.delete("/api/clients/{doc_id}")
def delete_client(doc_id: str):
    if not delete_document("client", doc_id):
        raise HTTPException(status_code=404, detail="Client not found")
    return {"ok": True}

@app.delete("/api/projects/{doc_id}")
def delete_project(doc_id: str):
    if not delete_document("project", doc_id):
        raise HTTPException(status_code=404, detail="Project not found")
    return {"ok": True}

@app.delete("/api/testimonials/{doc_id}")
def delete_testimonial(doc_id: str):
    if not delete_document("testimonial", doc_id):
        raise HTTPException(status_code=404, detail="Testimonial not found")
    return {"ok": True}

# Test DB connectivity
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

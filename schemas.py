"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.

Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogpost" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# ---------------------- Core Portfolio CMS Schemas ----------------------

class Category(BaseModel):
    """
    Portfolio categories like UI/UX, Graphic, Photography, etc.
    Collection name: "category"
    """
    key: str = Field(..., description="Unique key slug, e.g. 'uiux'")
    title: str = Field(..., description="Display title")
    description: Optional[str] = Field(None, description="Short summary")

class Client(BaseModel):
    """
    Clients associated to a category
    Collection name: "client"
    """
    name: str = Field(..., description="Client name")
    category_key: str = Field(..., description="Key of related Category")
    description: Optional[str] = Field(None, description="Client summary")
    logo_url: Optional[str] = Field(None, description="Logo URL")

class Project(BaseModel):
    """
    Projects associated to a client
    Collection name: "project"
    """
    client_name: str = Field(..., description="Client name reference")
    title: str = Field(..., description="Project title")
    tag: Optional[str] = Field(None, description="Type tag, e.g. UI/UX, Graphic")
    description: Optional[str] = Field(None, description="Short description")
    images: Optional[List[str]] = Field(default=None, description="Image URLs")
    link: Optional[str] = Field(default=None, description="External link or case study URL")

class Testimonial(BaseModel):
    """
    Client testimonials
    Collection name: "testimonial"
    """
    name: str
    role: Optional[str] = None
    quote: str
    company: Optional[str] = Field(default=None, description="Company or client name")
    rating: Optional[int] = Field(default=None, ge=1, le=5, description="Star rating 1-5")
    logo_url: Optional[str] = Field(default=None, description="Optional explicit logo URL")

class Setting(BaseModel):
    """
    UI/animation settings (singleton document)
    Collection name: "setting"
    """
    key: str = Field(..., description="settings key, e.g. 'ui'")
    marquee_a_seconds: Optional[float] = Field(30.0, ge=5, le=120)
    marquee_b_seconds: Optional[float] = Field(28.0, ge=5, le=120)
    glow_intensity: Optional[float] = Field(0.25, ge=0.0, le=1.0)
    parallax_intensity: Optional[float] = Field(8.0, ge=0.0, le=40.0, description="Max px drift per card")

# ---------------------- Examples (kept for reference) ----------------------

class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = Field(None, ge=0, le=120)
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    in_stock: bool = True

# The Flames database viewer will read these via GET /schema

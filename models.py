import os
import hashlib
import hmac
from typing import Optional, List, Any, Union, Dict
from pydantic import BaseModel, EmailStr, field_validator
from beanie import Document

# ====================== PASSWORD UTILS ======================
def hash_password(password: str, salt: bytes = None):
    if salt is None:
        salt = os.urandom(16)
    if isinstance(salt, str):
        try:
            salt = bytes.fromhex(salt)
        except ValueError:
            salt = salt.encode('latin-1')
        
    password_bytes = str(password).encode('utf-8')
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password_bytes, salt, 100000)
    return hash_bytes.hex(), salt if isinstance(salt, bytes) else salt.hex()


def verify_password(stored_hash: str, salt: Any, provided_password: str) -> bool:
    if isinstance(salt, str):
        try:
            salt = bytes.fromhex(salt)
        except ValueError:
            salt = salt.encode('latin-1')
            
    new_hash, _ = hash_password(provided_password, salt)
    return hmac.compare_digest(new_hash, stored_hash)



# ====================== USER MODEL ======================
class User(Document):
    email: EmailStr
    password: str
    salt: Any
    username: str
    fullName: str = ""
    mobile: str = ""
    birthDate: str = ""
    gender: str = "Other"
    facebook: str = ""
    avatar: str = ""
    age: str = "N/A"
    membershipTier: str = "CC Prime"
    status: str = "Active"
    isVerified: bool = False
    is_admin: bool = False
    created_at: str

    class Settings:
        name = "ecom_users"

    @field_validator('age', mode='before')
    @classmethod
    def ensure_age_is_string(cls, v):
        if v is None:
            return "N/A"
        if isinstance(v, (int, float)):
            return str(v)
        return str(v).strip() if str(v).strip() else "N/A"


# ====================== ADMIN USER MODEL ======================
class AdminUser(Document):
    fullName: str
    birthday: str
    habits: str
    email: str
    password: str
    salt: str
    created_at: str

    class Settings:
        name = "admin_users"


# ====================== PRODUCT MODEL ======================
class Product(Document):
    name: str
    description: str = ""
    price: float = 0.0
    compare_at_price: Optional[float] = None
    sku: str = ""
    inventory: int = 0
    category: str = "lifestyle"
    
    badge: Optional[str] = None
    sizes: List[str] = []
    colors: List[str] = []
    
    images: List[str] = []
    specifications: dict = {}
    status: str = "active"
    created_at: str 
    updated_at: str 

    class Settings:
        name = "products"

    @field_validator('category', mode='before')
    @classmethod
    def normalize_category(cls, v: Any) -> str:
        if isinstance(v, str):
            lowercased = v.strip().lower()
            if lowercased in ["clothes", "perfume", "lifestyle"]:
                return lowercased
        return v or "lifestyle"


# ====================== ORDER MODELS ======================
class OrderItem(BaseModel):
    id: Optional[Union[str, int]] = None
    product_id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    price: float = 0.0
    quantity: int = 1
    image: Optional[str] = ""
    category: Optional[str] = ""
    sku: Optional[str] = ""


class ShippingAddress(BaseModel):
    fullName: Optional[str] = ""
    mobileNumber: Optional[str] = ""
    street: Optional[str] = ""
    city: Optional[str] = ""
    region: Optional[str] = ""
    barangay: Optional[str] = ""
    zipCode: Optional[str] = ""
    landmark: Optional[str] = ""
    country: Optional[str] = "Philippines"


class Order(Document):
    user_id: str = "guest"
    order_number: Optional[str] = None
    items: List[OrderItem] = []
    
    total_amount: float = 0.0
    subtotal: float = 0.0
    total: Optional[float] = None
    
    shipping_full_name: Optional[str] = ""
    shipping_email: Optional[str] = ""
    shipping_mobile_number: Optional[str] = ""
    shipping_street: Optional[str] = ""
    shipping_barangay: Optional[str] = ""
    shipping_city: Optional[str] = ""
    shipping_region: Optional[str] = ""
    shipping_zip_code: Optional[str] = ""
    shipping_landmark: Optional[str] = ""
    shipping_country: Optional[str] = "Philippines"
    
    shippingAddress: Optional[Union[ShippingAddress, Dict[str, Any]]] = None
    shipping_address: Optional[Union[ShippingAddress, Dict[str, Any]]] = None
    
    status: str = "pending"
    payment_method: str = "cash_on_delivery"
    payment_status: str = "pending"
    
    notes: Optional[str] = ""
    estimated_delivery: Optional[str] = ""
    
    date: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Settings:
        name = "orders"


# ====================== COUPON MODEL ======================
class Coupon(Document):
    code: str
    discount: float
    type: str = "percent"
    minSpend: Optional[float] = 0
    maxDiscount: Optional[float] = None
    description: str
    created_at: Optional[str] = None

    class Settings:
        name = "coupons"


# ====================== TAX SETTING MODEL ======================
class TaxSettingDocument(Document):
    key: str = "store_tax_rate"
    taxRate: float = 0.08
    updated_at: Optional[str] = None

    class Settings:
        name = "tax_settings"


# ====================== STORE PARTS MODEL ======================
class BannerItem(BaseModel):
    sticker: str
    text: str

class ThemeConfig(BaseModel):
    bg: str
    border: str
    text: str
    separator: str
    items: List[BannerItem]

class BannerConfig(BaseModel):
    activeMode: str = "auto"
    forcedTheme: str = "default"
    themes: Dict[str, ThemeConfig] = {}

class FooterContact(BaseModel):
    phone: str = "09770074715"
    email: str = "ccecom.com"
    address: str = "Dumanjug, Cebu"

class FooterSocials(BaseModel):
    facebook: str = "#"
    twitter: str = "#"
    instagram: str = "#"
    youtube: str = "#"

class FooterConfig(BaseModel):
    contact: FooterContact = FooterContact()
    socials: FooterSocials = FooterSocials()
    copyrightText: str = "© 2026 CC Ecom. All Rights Reserved."

class StorePartsDocument(Document):
    key: str = "store_parts_config"
    banner: BannerConfig
    footer: FooterConfig
    updated_at: Optional[str] = None

    class Settings:
        name = "store_parts"


# ====================== EVENT MODEL ======================
class Event(Document):
    title: str
    description: str = ""
    event_type: str = "sale"
    discount_amount: float = 0.0  
    start_date: str
    end_date: str
    banner_image: Optional[str] = ""
    link_url: Optional[str] = ""
    status: str = "upcoming"
    is_featured: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Settings:
        name = "events"

# Compatibility alias for routes importing EventDocument
EventDocument = Event


# ====================== HOME PAGE CUSTOMIZATION MODEL ======================
class BackgroundConfig(BaseModel):
    type: str = "video"
    source: str = ""
    fallbackImage: str = ""


class HeroConfig(BaseModel):
    badgeText: str = "We Made Your Comforts"
    badgeFontFamily: Optional[str] = "Inter, sans-serif"
    titleTop: str = "COUNCI"
    titleTopFontFamily: Optional[str] = "Inter, sans-serif"
    titleBottom: str = "CROFF"
    titleBottomFontFamily: Optional[str] = "Inter, sans-serif"
    heading: str = "Luxury Crafted For Modern Elegance"
    headingFontFamily: Optional[str] = "Inter, sans-serif"
    narrative: str = "Discover premium fashion, signature fragrances, and refined accessories engineered to elevate your daily presence."
    narrativeFontFamily: Optional[str] = "Inter, sans-serif"
    ctaText: str = "Explore Collection"
    ctaPath: str = "/shop"
    background: BackgroundConfig


class CategoryCard(BaseModel):
    id: int
    title: str
    titleFontFamily: Optional[str] = "Inter, sans-serif"
    subtitle: str = ""
    subtitleFontFamily: Optional[str] = "Inter, sans-serif"
    description: str = ""
    descriptionFontFamily: Optional[str] = "Inter, sans-serif"
    image: str = ""
    path: str = ""


class CarouselConfig(BaseModel):
    eyebrow: str = "Curated Collections"
    eyebrowFontFamily: Optional[str] = "Inter, sans-serif"
    title: str = "Signature Worlds"
    titleFontFamily: Optional[str] = "Inter, sans-serif"
    cards: List[CategoryCard] = []


class StatItem(BaseModel):
    number: str
    numberFontFamily: Optional[str] = "Inter, sans-serif"
    label: str
    labelFontFamily: Optional[str] = "Inter, sans-serif"


class StatsConfig(BaseModel):
    eyebrow: str = "Excellence In Numbers"
    eyebrowFontFamily: Optional[str] = "Inter, sans-serif"
    heading: str = "Trusted By Thousands Globally"
    headingFontFamily: Optional[str] = "Inter, sans-serif"
    items: List[StatItem] = []


class HomeContent(Document):
    hero: HeroConfig
    carousel: CarouselConfig
    stats: StatsConfig

    class Settings:
        name = "home_content"

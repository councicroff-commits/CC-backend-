import datetime
import logging
from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from models import Product 

logger = logging.getLogger("CommercePrime_Products")
router = APIRouter()

ALLOWED_CATEGORIES = ["clothes", "perfume", "lifestyle"]

# =====================================================================
# INPUT SCHEMAS (Validation)
# =====================================================================
class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2)
    description: Optional[str] = ""
    price: float = Field(..., ge=0)
    compare_at_price: Optional[float] = None
    sku: Optional[str] = ""
    inventory: int = Field(default=0, ge=0)
    category: str
    badge: Optional[str] = None
    sizes: Optional[List[str]] = []
    colors: Optional[List[str]] = []
    images: Optional[List[str]] = []
    specifications: Optional[Dict[str, Any]] = {}
    status: Optional[str] = "active"

class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2)
    description: Optional[str] = None
    price: Optional[float] = Field(None, ge=0)
    compare_at_price: Optional[float] = None
    sku: Optional[str] = None
    inventory: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    badge: Optional[str] = None
    sizes: Optional[List[str]] = None
    colors: Optional[List[str]] = None
    images: Optional[List[str]] = None
    specifications: Optional[Dict[str, Any]] = None
    status: Optional[str] = None

# =====================================================================
# 1. HELPERS
# =====================================================================
def format_product_dto(doc: Product, is_list_view: bool = False) -> dict:
    if is_list_view and doc.images and len(doc.images) > 0:
        optimized_images = [doc.images[0]]
    else:
        optimized_images = doc.images or []

    return {
        "_id": str(doc.id),
        "id": str(doc.id), 
        "name": doc.name,
        "description": doc.description,
        "price": doc.price,
        "compare_at_price": doc.compare_at_price,
        "sku": doc.sku,
        "inventory": doc.inventory,
        "category": doc.category,
        "badge": doc.badge,     
        "sizes": doc.sizes,     
        "colors": doc.colors,   
        "images": optimized_images, 
        "specifications": doc.specifications,
        "status": doc.status,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at
    }

# =====================================================================
# 2. ENDPOINTS
# =====================================================================

@router.get('')
async def list_products(
    category: Optional[str] = None, 
    status: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100)
):
    query = {}
    if category: 
        query["category"] = category
    if status: 
        query["status"] = status
    
    try:
        # Added skip and limit for pagination to prevent memory overflow
        products = await Product.find(query).sort("-_id").skip(skip).limit(limit).to_list()
        return [format_product_dto(p, is_list_view=True) for p in products]
        
    except Exception as e:
        logger.error(f"Error fetching products list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while fetching products.")


@router.get('/{product_id}')
async def get_single_product(product_id: str):
    try:
        product = await Product.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return format_product_dto(product)
    except Exception as e:
        logger.error(f"Error fetching product {product_id}: {e}")
        raise HTTPException(status_code=400, detail="Invalid product ID format.")


@router.post('/')
async def create_product(data: ProductCreate):
    if data.category.lower() not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {ALLOWED_CATEGORIES}")

    current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    product_dict = data.model_dump()
    product_dict["created_at"] = current_time
    product_dict["updated_at"] = current_time
    
    try:
        new_product = Product(**product_dict)
        await new_product.insert()
        return format_product_dto(new_product)
    except Exception as e:
        logger.error(f"Database error creating product: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create product.")


@router.put('/{product_id}')
async def edit_product(product_id: str, data: ProductUpdate):
    if data.category and data.category.lower() not in ALLOWED_CATEGORIES:
        return JSONResponse(status_code=400, content={"error": "Invalid category."})

    try:
        product = await Product.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Only update fields that were actually provided in the request
        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            update_data['updated_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await product.set(update_data)
        
        return format_product_dto(product)
    except Exception as e:
        logger.error(f"Error updating product {product_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update product.")


@router.delete('/{product_id}')
async def remove_product(product_id: str):
    try:
        product = await Product.get(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
            
        await product.delete()
        return {"message": "Product deleted"}
    except Exception as e:
        logger.error(f"Error deleting product {product_id}: {e}")
        raise HTTPException(status_code=400, detail="Invalid product ID format or deletion failed.")

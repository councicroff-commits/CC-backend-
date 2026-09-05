import datetime
import logging
from typing import Optional, List, Union, Any, Dict
from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from beanie import PydanticObjectId

from models import Order

logger = logging.getLogger("CommercePrime_Orders")
router = APIRouter(tags=["Orders"])

# =====================================================================
# 1. SCHEMAS
# =====================================================================
class OrderItemSchema(BaseModel):
    id: Optional[Union[str, int]] = None
    product_id: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    price: float = Field(0, ge=0)
    quantity: int = Field(1, ge=1)
    image: Optional[str] = ""
    category: Optional[str] = ""
    sku: Optional[str] = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_item(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if not data.get("name") and data.get("title"):
                data["name"] = data["title"]
            if "price" not in data:
                data["price"] = 0
            if "quantity" not in data:
                data["quantity"] = 1
        return data


class OrderCreate(BaseModel):
    user_id: Optional[str] = "guest"
    order_number: Optional[str] = None
    total_amount: Optional[float] = None
    subtotal: Optional[float] = None
    total: Optional[float] = None
    items: List[OrderItemSchema] = []

    # Flat shipping fields
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

    # Nested shipping
    shipping_address: Optional[Dict[str, Any]] = None
    shippingAddress: Optional[Dict[str, Any]] = None

    payment_method: Optional[str] = "cash_on_delivery"
    notes: Optional[str] = ""
    estimated_delivery: Optional[str] = ""
    date: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        if data.get("total_amount") is None and data.get("total") is not None:
            data["total_amount"] = data["total"]
        if data.get("total_amount") is None:
            data["total_amount"] = 0

        addr = data.get("shipping_address") or data.get("shippingAddress")
        if isinstance(addr, dict):
            mapping = {
                "full_name": "shipping_full_name",
                "fullName": "shipping_full_name",
                "name": "shipping_full_name",
                "email": "shipping_email",
                "phone": "shipping_mobile_number",
                "mobile": "shipping_mobile_number",
                "mobileNumber": "shipping_mobile_number",
                "mobile_number": "shipping_mobile_number",
                "address_line1": "shipping_street",
                "street": "shipping_street",
                "address": "shipping_street",
                "address_line2": "shipping_barangay",
                "barangay": "shipping_barangay",
                "city": "shipping_city",
                "state": "shipping_region",
                "region": "shipping_region",
                "province": "shipping_region",
                "postal_code": "shipping_zip_code",
                "zipCode": "shipping_zip_code",
                "zip_code": "shipping_zip_code",
                "zip": "shipping_zip_code",
                "landmark": "shipping_landmark",
                "country": "shipping_country",
            }
            for src, dest in mapping.items():
                if addr.get(src) and not data.get(dest):
                    data[dest] = addr[src]

        return data


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., description="pending, processing, shipped, delivered, cancelled")


class OrderETAUpdate(BaseModel):
    estimated_delivery: str = Field(..., description="Estimated delivery date e.g. August 7-8")


class OrderUpdateSchema(BaseModel):
    status: Optional[str] = None
    estimated_delivery: Optional[str] = None
    estimatedDelivery: Optional[str] = None
    notes: Optional[str] = None
    delivery_note: Optional[str] = None
    payment_status: Optional[str] = None


# =====================================================================
# 2. HELPERS
# =====================================================================
def format_order(order: Order) -> dict:
    user_id_val = "guest"
    if hasattr(order, "user_id") and order.user_id:
        user_id_val = str(order.user_id)

    total_val = float(getattr(order, "total_amount", 0.0) or getattr(order, "total", 0.0) or 0.0)
    subtotal_val = float(getattr(order, "subtotal", total_val) or total_val)

    s_addr = getattr(order, "shippingAddress", None) or getattr(order, "shipping_address", None)
    if not isinstance(s_addr, dict):
        if hasattr(s_addr, "model_dump"):
            s_addr = s_addr.model_dump()
        else:
            s_addr = {
                "fullName": getattr(order, "shipping_full_name", ""),
                "email": getattr(order, "shipping_email", ""),
                "mobileNumber": getattr(order, "shipping_mobile_number", ""),
                "street": getattr(order, "shipping_street", ""),
                "barangay": getattr(order, "shipping_barangay", ""),
                "city": getattr(order, "shipping_city", ""),
                "region": getattr(order, "shipping_region", ""),
                "zipCode": getattr(order, "shipping_zip_code", ""),
                "landmark": getattr(order, "shipping_landmark", ""),
                "country": getattr(order, "shipping_country", "Philippines"),
            }

    order_str_id = str(order.id)
    order_num = getattr(order, "order_number", None) or f"ORD-{order_str_id[-8:].upper()}"

    return {
        "_id": order_str_id,
        "id": order_str_id,
        "order_id": order_str_id,
        "order_number": order_num,
        "user_id": user_id_val,
        "items": getattr(order, "items", []) or [],
        "total_amount": total_val,
        "total": total_val,
        "subtotal": subtotal_val,
        "shipping_full_name": getattr(order, "shipping_full_name", s_addr.get("fullName") or s_addr.get("full_name", "")),
        "shipping_email": getattr(order, "shipping_email", s_addr.get("email", "")),
        "shipping_mobile_number": getattr(order, "shipping_mobile_number", s_addr.get("mobileNumber") or s_addr.get("phone", "")),
        "shipping_street": getattr(order, "shipping_street", s_addr.get("street") or s_addr.get("address_line1", "")),
        "shipping_barangay": getattr(order, "shipping_barangay", s_addr.get("barangay") or s_addr.get("address_line2", "")),
        "shipping_city": getattr(order, "shipping_city", s_addr.get("city", "")),
        "shipping_region": getattr(order, "shipping_region", s_addr.get("region") or s_addr.get("state", "")),
        "shipping_zip_code": getattr(order, "shipping_zip_code", s_addr.get("zipCode") or s_addr.get("postal_code", "")),
        "shipping_landmark": getattr(order, "shipping_landmark", s_addr.get("landmark", "")),
        "shipping_country": getattr(order, "shipping_country", s_addr.get("country", "Philippines")),
        "shipping_address": s_addr,
        "shippingAddress": s_addr,
        "customer_name": getattr(order, "shipping_full_name", s_addr.get("fullName", "")),
        "customer_email": getattr(order, "shipping_email", s_addr.get("email", "")),
        "customer_phone": getattr(order, "shipping_mobile_number", s_addr.get("mobileNumber", "")),
        "payment_method": getattr(order, "payment_method", "cash_on_delivery"),
        "payment_status": getattr(order, "payment_status", "pending"),
        "status": getattr(order, "status", "pending"),
        "estimated_delivery": getattr(order, "estimated_delivery", "") or "",
        "notes": getattr(order, "notes", "") or "",
        "date": getattr(order, "date", getattr(order, "created_at", "")),
        "created_at": getattr(order, "created_at", ""),
        "updated_at": getattr(order, "updated_at", ""),
    }


# =====================================================================
# 3. ENDPOINTS
# =====================================================================

@router.get("")
@router.get("/")
async def list_orders(status: Optional[str] = None):
    try:
        query = {}
        if status:
            query["status"] = status

        orders = await Order.find(query).sort("-_id").to_list()
        return [format_order(o) for o in orders]
    except Exception as e:
        logger.error(f"Error fetching orders list: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch orders from database.")


@router.get("/user/{user_id}")
async def get_user_orders(user_id: str):
    try:
        orders = await Order.find(Order.user_id == user_id).sort("-_id").to_list()
        return [format_order(o) for o in orders]
    except Exception as e:
        logger.error(f"Error fetching orders for user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch user orders.")


@router.get("/{order_id}")
async def get_order_by_id(order_id: str):
    try:
        obj_id = PydanticObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Order ID format")

    try:
        order = await Order.get(obj_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return format_order(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching order {order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve order.")


@router.post("", status_code=status.HTTP_201_CREATED)
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order(order_data: OrderCreate):
    try:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        items_data = [item.model_dump() for item in order_data.items]
        final_total = float(order_data.total_amount or order_data.total or 0)
        subtotal = float(order_data.subtotal or final_total)
        order_date = order_data.date or now

        shipping_addr_dict = {
            "fullName": order_data.shipping_full_name or "",
            "email": order_data.shipping_email or "",
            "mobileNumber": order_data.shipping_mobile_number or "",
            "street": order_data.shipping_street or "",
            "barangay": order_data.shipping_barangay or "",
            "city": order_data.shipping_city or "",
            "region": order_data.shipping_region or "",
            "zipCode": order_data.shipping_zip_code or "",
            "landmark": order_data.shipping_landmark or "",
            "country": order_data.shipping_country or "Philippines",
        }

        new_order = Order(
            user_id=str(order_data.user_id) if order_data.user_id else "guest",
            order_number=order_data.order_number,
            items=items_data,
            total_amount=final_total,
            subtotal=subtotal,
            total=final_total,
            shipping_full_name=order_data.shipping_full_name or "",
            shipping_email=order_data.shipping_email or "",
            shipping_mobile_number=order_data.shipping_mobile_number or "",
            shipping_street=order_data.shipping_street or "",
            shipping_barangay=order_data.shipping_barangay or "",
            shipping_city=order_data.shipping_city or "",
            shipping_region=order_data.shipping_region or "",
            shipping_zip_code=order_data.shipping_zip_code or "",
            shipping_landmark=order_data.shipping_landmark or "",
            shipping_country=order_data.shipping_country or "Philippines",
            shippingAddress=shipping_addr_dict,
            shipping_address=shipping_addr_dict,
            payment_method=order_data.payment_method or "cash_on_delivery",
            payment_status="pending",
            status="pending",
            estimated_delivery=order_data.estimated_delivery or "",
            notes=order_data.notes or "",
            date=order_date,
            created_at=now,
            updated_at=now,
        )

        await new_order.insert()

        if not new_order.order_number:
            new_order.order_number = f"ORD-{str(new_order.id)[-8:].upper()}"
            await new_order.save()

        return {
            "success": True,
            "message": "Order created successfully",
            "order_id": str(new_order.id),
            "_id": str(new_order.id),
            "order": format_order(new_order),
        }

    except Exception as e:
        logger.error(f"Error processing checkout: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to process checkout due to server error."
        )


@router.patch("/{order_id}/status")
@router.put("/{order_id}/status")
async def update_order_status(order_id: str, status_payload: OrderStatusUpdate):
    try:
        obj_id = PydanticObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Order ID format")

    try:
        order = await Order.get(obj_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        order.status = status_payload.status
        order.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await order.save()

        return format_order(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status for order {order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update order status.")


@router.put("/{order_id}/eta")
async def update_order_eta(order_id: str, eta_payload: OrderETAUpdate):
    try:
        obj_id = PydanticObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Order ID format")

    try:
        order = await Order.get(obj_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        order.estimated_delivery = eta_payload.estimated_delivery
        order.updated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        await order.save()

        return format_order(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ETA for order {order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update order ETA.")


@router.put("/{order_id}")
async def update_order(order_id: str, payload: OrderUpdateSchema):
    try:
        obj_id = PydanticObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Order ID format")

    try:
        order = await Order.get(obj_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        update_dict = payload.model_dump(exclude_unset=True)
        
        # Normalize potential alias inputs
        if "estimatedDelivery" in update_dict and not update_dict.get("estimated_delivery"):
            update_dict["estimated_delivery"] = update_dict.pop("estimatedDelivery")
        if "delivery_note" in update_dict and not update_dict.get("notes"):
            update_dict["notes"] = update_dict.pop("delivery_note")

        update_dict["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

        await order.set(update_dict)
        return format_order(order)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fully updating order {order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update order.")


@router.delete("/{order_id}")
async def delete_order(order_id: str):
    try:
        obj_id = PydanticObjectId(order_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Order ID format")

    try:
        order = await Order.get(obj_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        await order.delete()
        return {"success": True, "message": "Order deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting order {order_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to delete order.")

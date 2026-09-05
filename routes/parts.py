import logging
from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
from typing import Dict, Any

from models import (
    StorePartsDocument, 
    BannerConfig, 
    ThemeConfig, 
    BannerItem, 
    FooterConfig,
    FooterContact,
    FooterSocials
)

logger = logging.getLogger("CommercePrime_StoreParts")
router = APIRouter(tags=["Store Parts"])

@router.get("/", response_model=Dict[str, Any])
async def get_store_parts():
    """Fetch store parts configuration (banner & footer), auto-seeding defaults if not found."""
    try:
        doc = await StorePartsDocument.find_one(StorePartsDocument.key == "store_parts_config")
        
        if not doc:
            # Auto-seed default configuration if it doesn't exist yet in MongoDB
            default_banner = BannerConfig(
                activeMode="auto",
                forcedTheme="default",
                themes={
                    "default": ThemeConfig(
                        bg="#09090b",
                        border="#27272a",
                        text="#f4f4f5",
                        separator="#0ea5e9",
                        items=[
                            BannerItem(sticker="🚀", text="FREE SHIPPING ON ORDERS OVER $50"),
                            BannerItem(sticker="🔥", text="NEW WINTER COLLECTION DROPPED")
                        ]
                    ),
                    "christmas": ThemeConfig(
                        bg="#064e3b",
                        border="#065f46",
                        text="#ecfdf5",
                        separator="#f59e0b",
                        items=[
                            BannerItem(sticker="🎄", text="HOLIDAY SALE - UP TO 40% OFF"),
                            BannerItem(sticker="❄️", text="HAPPY HOLIDAYS FROM OUR TEAM")
                        ]
                    ),
                    "halloween": ThemeConfig(
                        bg="#451a03",
                        border="#78350f",
                        text="#fff7ed",
                        separator="#f97316",
                        items=[
                            BannerItem(sticker="🎃", text="SPOOKY SEASON DEALS LIVE NOW"),
                            BannerItem(sticker="👻", text="USE CODE SPOOKY FOR 20% OFF")
                        ]
                    )
                }
            )
            
            default_footer = FooterConfig(
                contact=FooterContact(
                    phone="09770074715",
                    email="support@ccecom.com",
                    address="Dumanjug, Cebu"
                ),
                socials=FooterSocials(
                    facebook="https://facebook.com",
                    twitter="https://twitter.com",
                    instagram="https://instagram.com",
                    youtube="https://youtube.com"
                ),
                copyrightText="© 2026 CC Ecom. All Rights Reserved."
            )
            
            doc = StorePartsDocument(
                key="store_parts_config",
                banner=default_banner,
                footer=default_footer,
                updated_at=datetime.now(timezone.utc).isoformat()
            )
            await doc.insert()
            
        return {
            "config": doc.model_dump() if hasattr(doc, 'model_dump') else doc.dict()
        }
    
    except Exception as e:
        logger.error(f"Error fetching store parts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while fetching store configuration.")

@router.put("/", response_model=Dict[str, Any])
async def update_store_parts(payload: Dict[str, Any]):
    """Update store parts configuration (banner & footer settings)."""
    banner_data = payload.get("banner")
    footer_data = payload.get("footer")
    
    if not banner_data or not footer_data:
        raise HTTPException(
            status_code=400, 
            detail="Invalid payload structure: missing banner or footer fields."
        )

    try:
        doc = await StorePartsDocument.find_one(StorePartsDocument.key == "store_parts_config")
        
        now_str = datetime.now(timezone.utc).isoformat()
        if not doc:
            doc = StorePartsDocument(
                key="store_parts_config",
                banner=banner_data,
                footer=footer_data,
                updated_at=now_str
            )
            await doc.insert()
        else:
            doc.banner = banner_data
            doc.footer = footer_data
            doc.updated_at = now_str
            await doc.save()

        return {
            "message": "Store configuration successfully updated",
            "config": doc.model_dump() if hasattr(doc, 'model_dump') else doc.dict()
        }
        
    except Exception as e:
        logger.error(f"Error updating store parts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while updating store configuration.")

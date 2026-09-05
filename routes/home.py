import logging
from fastapi import APIRouter, HTTPException
from models import HomeContent, HeroConfig, CarouselConfig, StatsConfig, BackgroundConfig, CategoryCard, StatItem

logger = logging.getLogger("CommercePrime_Home")
router = APIRouter(tags=["home"])

@router.get("", response_model=HomeContent)
async def get_home_content():
    try:
        content = await HomeContent.find_one({})
        if not content:
            content = HomeContent(
                hero=HeroConfig(
                    badgeText="We Made Your Comforts",
                    titleTop="COUNCI",
                    titleBottom="CROFF",
                    heading="Luxury Crafted For Modern Elegance",
                    narrative="Discover premium fashion, signature fragrances, and refined accessories engineered to elevate your daily presence.",
                    ctaText="Explore Collection",
                    ctaPath="/shop",
                    fontFamily="Inter, sans-serif",
                    background=BackgroundConfig(
                        type="video",
                        source="https://videos.pexels.com/video-files/28936530/12529770_1920_1080_30fps.mp4",
                        fallbackImage="https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=1920&q=80"
                    )
                ),
                carousel=CarouselConfig(
                    eyebrow="Curated Collections",
                    title="Signature Worlds",
                    cards=[
                        CategoryCard(id=1, title="Fashion", subtitle="Premium Wear", description="Exquisite craftsmanship built for distinction.", image="https://images.unsplash.com/photo-1529139574466-a303027c1d8b?auto=format&fit=crop&w=1200&q=80", path="/clothes", fontFamily="Inter, sans-serif"),
                        CategoryCard(id=2, title="Perfume", subtitle="Luxury Scents", description="Exquisite craftsmanship built for distinction.", image="https://images.unsplash.com/photo-1541643600914-78b084683601?auto=format&fit=crop&w=1200&q=80", path="/perfume", fontFamily="Inter, sans-serif"),
                        CategoryCard(id=3, title="Accessories", subtitle="Signature Style", description="Exquisite craftsmanship built for distinction.", image="https://images.unsplash.com/photo-1523170335258-f5ed11844a49?auto=format&fit=crop&w=1200&q=80", path="/lifestyle", fontFamily="Inter, sans-serif")
                    ]
                ),
                stats=StatsConfig(
                    eyebrow="Excellence In Numbers",
                    heading="Trusted By Thousands Globally",
                    items=[
                        StatItem(number="12K+", label="Global Customers"),
                        StatItem(number="680+", label="Luxury Products"),
                        StatItem(number="99%", label="Customer Satisfaction")
                    ]
                )
            )
            await content.insert()
        return content
    except Exception as e:
        logger.error(f"Database error fetching home content: {e}", exc_info=True)
        # Sanitized error message: Do not expose str(e) to the frontend in production
        raise HTTPException(status_code=500, detail="Internal server error while fetching content.")

@router.put("", response_model=HomeContent)
async def update_home_content(payload: HomeContent):
    try:
        existing = await HomeContent.find_one({})
        if existing:
            existing.hero = payload.hero
            existing.carousel = payload.carousel
            existing.stats = payload.stats
            await existing.save()
            return existing
        else:
            await payload.insert()
            return payload
    except Exception as e:
        logger.error(f"Database error updating home content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while updating content.")

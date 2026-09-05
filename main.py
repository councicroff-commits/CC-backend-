import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from database import init_db, get_db_status
from routes import (
    auth, 
    products, 
    analytics, 
    orders, 
    cart, 
    home, 
    parts
)

# ── Environment & Logging ─────────────────────────────────
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()

logging.basicConfig(
    level=logging.INFO if ENVIRONMENT == "production" else logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s"
)
logger = logging.getLogger("CommercePrime_Main")

# ── Local File Storage ────────────────────────────────────
os.makedirs('static/uploads/avatars', exist_ok=True)
os.makedirs('static/uploads/products', exist_ok=True)
os.makedirs('static/uploads/events', exist_ok=True)

# ── Lifespan Manager ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting Commerce Prime API Engine [{ENVIRONMENT.upper()}]...")
    try:
        await init_db()
        logger.info("📦 Database connection pool initialized successfully.")
    except Exception as e:
        logger.critical(f"💥 Critical database initialization failure: {e}")
        raise
    
    yield
    
    logger.info("🛑 Shutting down Commerce Prime API Engine gracefully...")

# ── Application Initialization ────────────────────────────
app = FastAPI(
    title="Commerce Prime API Engine",
    version="1.0.0",
    description="High-performance backend API services for Commerce Prime Admin & Storefront.",
    lifespan=lifespan,
    docs_url="/docs" if ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if ENVIRONMENT != "production" else None,
    openapi_url="/openapi.json" if ENVIRONMENT != "production" else None
)

# ── Production Security & Performance Middlewares ─────────
app.add_middleware(GZipMiddleware, minimum_size=1000)

if ENVIRONMENT == "production":
    raw_hosts = os.getenv("ALLOWED_HOSTS", "*")
    allowed_hosts = [h.strip() for h in raw_hosts.split(",")]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

if ENVIRONMENT == "development":
    allowed_origins = ["*"]
    allow_credentials = False
else:
    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    allowed_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With"],
)

# ── Global Exception Handler ──────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"🔥 Unhandled server error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

# ── Mount Static Files ────────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")

# ── Register API Routers ──────────────────────────────────
app.include_router(home.router, prefix="/api/v1/home", tags=["Home Content"])
app.include_router(parts.router, prefix="/api/v1/parts", tags=["Store Parts"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(products.router, prefix="/api/v1/products", tags=["Products"])
app.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(cart.router, prefix="/api/v1", tags=["Settings, Promos & Events"])

# ── Root & Telemetry Endpoints ────────────────────────────
@app.get("/", tags=["Telemetry"])
async def root():
    return {
        "app": "Commerce Prime API Engine",
        "environment": ENVIRONMENT,
        "status": "online"
    }

@app.get("/health", tags=["Telemetry"])
async def health_check():
    db_status = await get_db_status()
    is_healthy = db_status == "CONNECTED"
    
    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if is_healthy else "unhealthy",
            "database": db_status
        }
    )

# ── Execution Block ───────────────────────────────────────
if __name__ == "__main__":
    PORT = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=PORT,
        reload=(ENVIRONMENT != "production"),
        workers=int(os.getenv("WEB_CONCURRENCY", 1))
    )

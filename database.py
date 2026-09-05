import os
import sys
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

# ── Logging Setup ─────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("CC_Database_Layer")

# ── Environment Configuration ─────────────────────────────
load_dotenv()

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
DB_NAME = os.getenv("MONGO_DB_NAME", "cc_telemetry")
MONGO_URI = os.getenv("MONGODB_URI")

if not MONGO_URI:
    logger.critical("💥 CRITICAL ERROR: MONGODB_URI is not set in your environment variables!")
    sys.exit(1)

# ── Import document models ────────────────────────────────
try:
    from models import (
        User, 
        Product, 
        Order, 
        Coupon, 
        TaxSettingDocument, 
        HomeContent, 
        StorePartsDocument, 
        EventDocument, 
        AdminUser
    )
except ImportError:
    # Fallback in case the model is named 'Event' instead of 'EventDocument' in models.py
    try:
        from models import (
            User, 
            Product, 
            Order, 
            Coupon, 
            TaxSettingDocument, 
            HomeContent, 
            StorePartsDocument, 
            Event as EventDocument, 
            AdminUser
        )
    except ImportError as err:
        logger.critical(f"❌ Critical Import Error: Could not locate models. Details: {err}", exc_info=True)
        sys.exit(1)

# ── Android / Termux DNS Patch (Local Development Only) ───
if ENVIRONMENT == "development":
    try:
        import dns.resolver
        dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
        dns.resolver.default_resolver.nameservers = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
        logger.info("⚡ Local Environment detected: Android DNS resolver patches applied.")
    except ImportError:
        logger.warning("⚠️ dns.resolver not installed. Skipping DNS patch.")
    except Exception as dns_err:
        logger.warning(f"⚠️ DNS resolution override warning (Non-fatal): {dns_err}")

# ── Motor Client Initialization ───────────────────────────
try:
    # In production, tlsInsecure MUST be False to prevent MITM attacks
    is_insecure = (ENVIRONMENT == "development")
    
    client = AsyncIOMotorClient(
        MONGO_URI,
        tls=True,
        tlsInsecure=is_insecure,
        serverSelectionTimeoutMS=30000,
        connectTimeoutMS=30000,
    )
    db = client[DB_NAME]
    
    security_status = "Insecure (Dev)" if is_insecure else "Secure (Prod)"
    logger.info(f"✅ AsyncIOMotorClient initialized [{security_status}].")
except Exception as init_err:
    logger.critical(f"💥 Failed to create AsyncIOMotorClient: {init_err}")
    sys.exit(1)

# ── Database Lifecycle Functions ──────────────────────────
async def init_db():
    """Called from main.py lifespan"""
    logger.info(f"🔄 Initializing Beanie ODM → database '{DB_NAME}'")
    try:
        await db.command("ping")
        await init_beanie(
            database=db,
            document_models=[
                User, 
                Product, 
                Order, 
                Coupon, 
                TaxSettingDocument, 
                HomeContent, 
                StorePartsDocument, 
                EventDocument,
                AdminUser
            ]
        )
        logger.info("✅ Beanie ODM initialized successfully.")
    except Exception as e:
        logger.error(f"❌ Beanie initialization failed: {e}", exc_info=True)
        raise

async def get_db_status() -> str:
    """Active network ping to verify database connection."""
    try:
        await db.command("ping")
        return "CONNECTED"
    except Exception as e:
        logger.error(f"⚠️ Heartbeat failed: {e}")
        return f"CONNECTION_FAILED: {str(e)}"

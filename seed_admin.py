import asyncio
from datetime import datetime, timezone

from database import init_db
from models import AdminUser, hash_password

async def inject_admin():
    print("🔄 Initializing database connection via project module...")
    await init_db()
    
    print("🧹 Clearing old admin records...")
    await AdminUser.find({"email": "SoarHarleyAndTeam"}).delete()
    
    print("🔐 Hashing password...")
    hashed_pw, salt = hash_password("Harley YC")
    
    # FIXED: Convert raw salt bytes into a hexadecimal string representation
    if isinstance(salt, bytes):
        salt = salt.hex()
        
    now = datetime.now(timezone.utc).isoformat()
    
    print("📥 Injecting new admin...")
    new_admin = AdminUser(
        fullName="Harley YC",
        birthday="Yelrah CY",
        habits="Crying,Burning Peso",
        email="SoarHarleyAndTeam",
        password=hashed_pw,
        salt=salt,
        created_at=now
    )
    
    await new_admin.insert()
    print("✅ Success! Admin credentials successfully injected into MongoDB Atlas.")

if __name__ == "__main__":
    asyncio.run(inject_admin())

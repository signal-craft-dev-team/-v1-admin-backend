import os
 
class Settings:
    # 운영자 origin. 스테이징 배포 시 실제 주소로 잠그세요.
    #   ADMIN_ORIGINS="https://admin.signalcraft.io,http://localhost:5173"
    ADMIN_ORIGINS: list[str] = os.getenv("ADMIN_ORIGINS", "*").split(",")
 
settings = Settings()
from sqlalchemy.engine import make_url
from app.core.config import settings

url = make_url(settings.database_url)
print("Environment: HOST")
print(f"Driver: {url.drivername}")
print(f"Host: {url.host}")
print(f"Port: {url.port}")
print(f"Database: {url.database}")
print(f"Username: {url.username}")

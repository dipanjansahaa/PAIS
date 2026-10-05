from datetime import datetime, timedelta, timezone
import jwt
from app.core.config import settings

def generate_local_jwt():
    """
    Generates a local HS256 JWT token for development purposes.
    """
    now = datetime.now(timezone.utc)
    
    payload = {
        'sub': 'dev-user-local-001',
        'iat': now,
        'exp': now + timedelta(hours=12)
    }
    
    # Encode the token using the secret and algorithm from settings
    token = jwt.encode(
        payload, 
        settings.auth_jwt_secret, 
        algorithm='HS256'
    )
    
    return token

if __name__ == "__main__":
    jwt_token = generate_local_jwt()
    print(jwt_token)

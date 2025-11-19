"""
Authentication middleware for HTTP Basic Auth
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import secrets
import os
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize HTTP Basic Auth
security = HTTPBasic()

# Get authentication credentials from environment variables
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "changeme123")


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Verify HTTP Basic Authentication credentials
    
    Args:
        credentials: HTTPBasicCredentials from FastAPI security
        
    Returns:
        str: The authenticated username
        
    Raises:
        HTTPException: 401 Unauthorized if credentials are invalid
    """
    # Use secrets.compare_digest to prevent timing attacks
    username_match = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        AUTH_USERNAME.encode("utf-8")
    )
    password_match = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        AUTH_PASSWORD.encode("utf-8")
    )
    
    if not (username_match and password_match):
        logger.warning(f"Failed authentication attempt for user: {credentials.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    logger.debug(f"Successful authentication for user: {credentials.username}")
    return credentials.username


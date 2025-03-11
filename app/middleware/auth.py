# app/middleware/auth.py

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth import verify_token
import logging

# Security scheme
security = HTTPBearer()

class AuthMiddleware:
    """Middleware to verify JWT tokens and enforce authentication"""
    
    async def __call__(self, request: Request, call_next):
        """Process each request to check authentication"""
        
        # Skip auth for login endpoint and OPTIONS requests
        if request.url.path == "/token" or request.method == "OPTIONS":
            return await call_next(request)
            
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header or not auth_header.startswith("Bearer "):
            if request.url.path.startswith("/api/"):
                # Only require auth for API endpoints
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            # Let non-API requests continue
            return await call_next(request)
            
        # Extract token
        token = auth_header.replace("Bearer ", "")
        
        # Verify token for API endpoints
        if request.url.path.startswith("/api/"):
            is_valid, user_data = verify_token(token)
            
            if not is_valid:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"}
                )
                
            # Attach user data to request state
            request.state.user = user_data
            
        # Continue with request
        return await call_next(request)

# Auth dependency for routes that need it
async def get_current_user(credentials: HTTPAuthorizationCredentials = security):
    """Extract user from token for dependency injection in routes"""
    is_valid, user_data = verify_token(credentials.credentials)
    
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return user_data

# Function to verify specific permissions
def verify_permission(permission: str):
    """Create a dependency to check for specific permissions"""
    
    async def check_permission(user_data: dict = get_current_user):
        if permission not in user_data.get("role", {}):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized: missing {permission} permission"
            )
        return user_data
        
    return check_permission
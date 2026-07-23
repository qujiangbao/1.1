"""Auth API"""
from fastapi import APIRouter, HTTPException, status
from app.core.security import authenticate_admin, create_access_token
from app.schemas.agent import LoginRequest

router = APIRouter()


@router.post("/auth/login")
async def login(request: LoginRequest):
    if not authenticate_admin(request.username, request.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": request.username, "role": "park_manager"})
    return {"access_token": token, "token_type": "bearer"}

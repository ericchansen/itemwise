"""FastAPI REST API for inventory management."""

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import openai
from pydantic import BaseModel, EmailStr, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy import text

# Load environment variables from .env file (find it relative to this file)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

from .database.crud import (
    create_item,
    create_location,
    create_lot,
    create_user,
    delete_item,
    delete_user,
    get_expiring_items,
    get_item,
    get_lots_for_item,
    get_or_create_location,
    get_user_by_email,
    get_user_default_inventory,
    is_inventory_member,
    list_items,
    list_locations,
    log_transaction,
    reduce_lot,
    search_items_by_embedding,
    search_items_by_text,
    update_item,
    get_oldest_items as get_oldest_items_crud,
)
from .database.engine import AsyncSessionLocal, close_db, init_db
from .embeddings import generate_embedding
from .auth import (
    AccessTokenResponse,
    DUMMY_HASH,
    RefreshTokenRequest,
    Token,
    TokenData,
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    validate_password,
    verify_password,
    verify_reset_token,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the frontend directory path
FRONTEND_DIR = Path(__file__).parent.parent.parent / "frontend"

# Check if Azure OpenAI is configured
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_ENABLED = bool(AZURE_OPENAI_ENDPOINT)
logger.info(f"Azure OpenAI enabled: {AZURE_OPENAI_ENABLED}")
if AZURE_OPENAI_ENABLED:
    logger.info(f"  Endpoint: {AZURE_OPENAI_ENDPOINT}")
    logger.info(f"  Deployment: {os.getenv('AZURE_OPENAI_DEPLOYMENT')}")
else:
    logger.warning("Azure OpenAI NOT configured - chat will use fallback mode")


# Pydantic models for API
class ItemCreate(BaseModel):
    name: str = Field(..., description="Name of the item")
    quantity: int = Field(..., ge=1, description="Quantity of items")
    category: str = Field(..., description="Category (e.g., meat, electronics)")
    location: Optional[str] = Field(None, description="Storage location name")
    description: Optional[str] = Field(None, description="Optional description")


class ItemUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = Field(None, ge=1)
    category: Optional[str] = None
    location: Optional[str] = None
    description: Optional[str] = None


class LocationCreate(BaseModel):
    name: str = Field(..., description="Name of the location")
    description: Optional[str] = Field(None, description="Optional description")


class UserRegister(BaseModel):
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password (min 8 characters)")


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)


class ChatMessage(BaseModel):
    message: str = Field(..., description="User's natural language message")


class ChatResponse(BaseModel):
    response: str
    action: Optional[str] = None
    data: Optional[dict[str, Any]] = None


def _get_item_text_for_embedding(
    name: str, description: Optional[str] = None, category: Optional[str] = None
) -> str:
    """Build text representation of item for embedding generation."""
    parts = [name]
    if category:
        parts.append(f"category: {category}")
    if description:
        parts.append(description)
    return " | ".join(parts)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database and model lifecycle."""
    logger.info("Starting Inventory Assistant API...")
    await init_db()
    logger.info("Database initialized")
    
    # Note: Embedding model loads lazily on first search request
    # Skip preloading to speed up startup - the LLM can handle most queries
    # without embeddings (it calls search_items which generates embeddings on demand)
    logger.info("Server ready (embedding model will load on first search)")
    
    yield
    logger.info("Shutting down...")
    await close_db()


# Create FastAPI app
app = FastAPI(
    title="Inventory Assistant API",
    description="REST API for managing inventory across multiple locations",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS configuration from environment
_cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
ALLOWED_ORIGINS = [origin.strip() for origin in _cors_origins.split(",") if origin.strip()]

# Security check: don't allow wildcard with credentials in production
_is_production = os.getenv("ENV", "development").lower() in ("production", "prod")
if _is_production and "*" in ALLOWED_ORIGINS:
    raise ValueError("CORS_ORIGINS cannot be '*' in production when credentials are enabled")

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return JSON 429 with Retry-After header."""
    retry_after = exc.detail.split(" ")[-1] if exc.detail else "60"
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
        headers={"Retry-After": retry_after},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint - verifies DB connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "dependencies": {"database": "healthy"},
        }
    except (SQLAlchemyError, OSError) as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "dependencies": {"database": "unhealthy"},
            },
        )


# ===== Authentication =====

# API router for versioned endpoints — mounted at both /api and /api/v1
api_router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)]
) -> TokenData:
    """Dependency to get the current authenticated user from JWT token."""
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token_data = decode_access_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return token_data


async def get_active_inventory_id(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    x_inventory_id: Annotated[int | None, Header()] = None,
) -> int:
    """Resolve the active inventory ID for the current request.

    Uses X-Inventory-Id header if provided, otherwise falls back to
    the user's default inventory.
    """
    if x_inventory_id is not None:
        async with AsyncSessionLocal() as session:
            if not await is_inventory_member(session, x_inventory_id, current_user.user_id):
                raise HTTPException(status_code=403, detail="Not a member of this inventory")
        return x_inventory_id

    async with AsyncSessionLocal() as session:
        inventory = await get_user_default_inventory(session, current_user.user_id)
        if not inventory:
            raise HTTPException(status_code=500, detail="Could not resolve default inventory")
        return inventory.id


# ===== Auth Endpoints =====


@api_router.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserRegister):
    """Register a new user account.

    Returns access and refresh tokens on successful registration.
    """
    # Validate password complexity
    is_valid, error_msg = validate_password(user_data.password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)
    
    async with AsyncSessionLocal() as session:
        hashed_password = hash_password(user_data.password)
        try:
            user = await create_user(session, user_data.email, hashed_password)
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=400, detail="Email already registered")

        access_token = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id, user.email)

        return Token(access_token=access_token, refresh_token=refresh_token)


@api_router.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(request: Request, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    """Login and get access/refresh tokens.

    Uses constant-time comparison to prevent timing attacks.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, form_data.username)
        
        # Use dummy hash if user doesn't exist to prevent timing attacks
        password_hash = user.hashed_password if user else DUMMY_HASH
        password_valid = verify_password(form_data.password, password_hash)
        
        if not user or not password_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token = create_access_token(user.id, user.email)
        refresh_token = create_refresh_token(user.id, user.email)
        
        return Token(access_token=access_token, refresh_token=refresh_token)


@api_router.post("/auth/refresh", response_model=AccessTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Get a new access token using a refresh token."""
    token_data = decode_refresh_token(request.refresh_token)
    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(token_data.user_id, token_data.email)
    return AccessTokenResponse(access_token=access_token)


@api_router.get("/auth/me")
async def get_current_user_info(
    current_user: Annotated[TokenData, Depends(get_current_user)]
):
    """Get current authenticated user info."""
    return {
        "user_id": current_user.user_id,
        "email": current_user.email,
    }


@api_router.put("/auth/password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """Change the authenticated user's password."""
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, current_user.email)
        if not user or not verify_password(body.current_password, user.hashed_password):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        is_valid, error_msg = validate_password(body.new_password)
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        user.hashed_password = hash_password(body.new_password)
        await session.commit()

    return {"message": "Password updated successfully"}


@api_router.post("/auth/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    """Request a password reset email.

    Always returns 200 to prevent email enumeration.
    """
    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, body.email)
        if user:
            token = create_reset_token(body.email)
            from .email_service import send_password_reset_email, APP_URL
            send_password_reset_email(body.email, token, APP_URL)

    return {"message": "If an account exists with that email, a reset link has been sent."}


@api_router.post("/auth/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """Reset password using a valid reset token."""
    email = verify_reset_token(body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    is_valid, error_msg = validate_password(body.new_password)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    async with AsyncSessionLocal() as session:
        user = await get_user_by_email(session, email)
        if not user:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")
        user.hashed_password = hash_password(body.new_password)
        await session.commit()

    return {"message": "Password has been reset successfully"}


@api_router.delete("/auth/account")
@limiter.limit("5/hour")
async def delete_account(
    request: Request,
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """Delete the currently authenticated user's account."""
    async with AsyncSessionLocal() as session:
        deleted = await delete_user(session, current_user.user_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="User not found")
    return {"message": "Account deleted successfully"}


# ===== Item Endpoints =====


@api_router.get("/items")
async def get_items(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    category: Optional[str] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location name"),
):
    """List all inventory items with optional filters."""
    async with AsyncSessionLocal() as session:
        items = await list_items(
            session,
            inventory_id=inventory_id,
            category=category,
            location_name=location,
        )
        return {
            "count": len(items),
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "category": item.category,
                    "location": item.location.name if item.location else None,
                    "description": item.description,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                }
                for item in items
            ],
        }


@api_router.post("/items")
async def create_new_item(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    item: ItemCreate,
):
    """Add a new item to inventory."""
    async with AsyncSessionLocal() as session:
        # Get or create location if specified
        location_id = None
        location_name = None
        if item.location:
            loc = await get_or_create_location(session, inventory_id, item.location.strip())
            location_id = loc.id
            location_name = loc.name

        # Generate embedding
        item_text = _get_item_text_for_embedding(item.name, item.description, item.category)
        embedding = generate_embedding(item_text)

        # Log transaction
        await log_transaction(
            session,
            operation="CREATE",
            data={
                "name": item.name,
                "quantity": item.quantity,
                "category": item.category,
                "location": location_name,
            },
        )

        # Create item
        new_item = await create_item(
            session,
            inventory_id=inventory_id,
            name=item.name,
            quantity=item.quantity,
            category=item.category,
            description=item.description,
            location_id=location_id,
            embedding=embedding,
        )

        return {
            "status": "success",
            "message": f"Added {item.quantity} {item.name} to {location_name or 'inventory'}",
            "item": {
                "id": new_item.id,
                "name": new_item.name,
                "quantity": new_item.quantity,
                "category": new_item.category,
                "location": location_name,
                "description": new_item.description,
            },
        }


@api_router.get("/items/expiring")
async def get_expiring_items_endpoint(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    days: int = Query(7, ge=1, le=365, description="Number of days to look ahead"),
):
    """Get items expiring within N days."""
    async with AsyncSessionLocal() as session:
        items = await get_expiring_items(session, inventory_id, days=days)
        return {
            "count": len(items),
            "days_window": days,
            "items": items,
        }


@api_router.post("/notifications/expiration-digest")
async def send_expiration_digest(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    days: int = Query(7, ge=1, le=365, description="Number of days to look ahead"),
):
    """Send an email digest of items expiring within N days."""
    async with AsyncSessionLocal() as session:
        items = await get_expiring_items(session, inventory_id, days=days)
        if not items:
            return {"status": "no_items"}

        from .email_service import send_expiration_digest_email, APP_URL
        sent = send_expiration_digest_email(current_user.email, items, APP_URL)
        if not sent:
            raise HTTPException(status_code=500, detail="Failed to send digest email")
        return {"status": "sent", "item_count": len(items)}


@api_router.get("/items/{item_id}")
async def get_single_item(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    item_id: int,
):
    """Get a single item by ID."""
    async with AsyncSessionLocal() as session:
        item = await get_item(session, inventory_id, item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")
        return {
            "id": item.id,
            "name": item.name,
            "quantity": item.quantity,
            "category": item.category,
            "location": item.location.name if item.location else None,
            "description": item.description,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }


@api_router.put("/items/{item_id}")
async def update_existing_item(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    item_id: int,
    item: ItemUpdate,
):
    """Update an existing item."""
    async with AsyncSessionLocal() as session:
        existing = await get_item(session, inventory_id, item_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

        # Handle location update
        location_id = None
        if item.location is not None:
            if item.location:
                loc = await get_or_create_location(session, inventory_id, item.location.strip())
                location_id = loc.id

        # Generate new embedding if needed
        embedding = None
        if item.name is not None or item.description is not None or item.category is not None:
            new_name = item.name if item.name is not None else existing.name
            new_desc = item.description if item.description is not None else existing.description
            new_cat = item.category if item.category is not None else existing.category
            item_text = _get_item_text_for_embedding(new_name, new_desc, new_cat)
            embedding = generate_embedding(item_text)

        # Log transaction
        await log_transaction(
            session,
            operation="UPDATE",
            item_id=item_id,
            data=item.model_dump(exclude_none=True),
        )

        # Update item
        updated = await update_item(
            session,
            inventory_id=inventory_id,
            item_id=item_id,
            name=item.name,
            quantity=item.quantity,
            category=item.category,
            description=item.description,
            location_id=location_id,
            embedding=embedding,
        )

        return {
            "status": "success",
            "message": f"Updated {updated.name}",
            "item": {
                "id": updated.id,
                "name": updated.name,
                "quantity": updated.quantity,
                "category": updated.category,
                "location": updated.location.name if updated.location else None,
                "description": updated.description,
            },
        }


@api_router.delete("/items/{item_id}")
async def delete_existing_item(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    item_id: int,
):
    """Delete an item from inventory."""
    async with AsyncSessionLocal() as session:
        item = await get_item(session, inventory_id, item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

        item_name = item.name
        location_name = item.location.name if item.location else None

        await log_transaction(
            session,
            operation="DELETE",
            item_id=item_id,
            data={"name": item_name},
        )

        deleted = await delete_item(session, inventory_id, item_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete item")

        return {
            "status": "success",
            "message": f"Removed {item_name}" + (f" from {location_name}" if location_name else ""),
        }


# ===== Search Endpoint =====


@api_router.get("/search")
async def search_items(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    q: str = Query(..., description="Search query"),
    location: Optional[str] = Query(None, description="Filter by location"),
):
    """Search inventory using natural language."""
    async with AsyncSessionLocal() as session:
        # Log search
        await log_transaction(
            session,
            operation="SEARCH",
            data={"query": q, "location": location},
        )

        # Generate query embedding
        query_embedding = generate_embedding(q)

        # Semantic search
        semantic_results = await search_items_by_embedding(
            session, inventory_id, query_embedding, location_name=location, limit=10
        )

        # Text search fallback
        text_results = await search_items_by_text(
            session, inventory_id, q, location_name=location, limit=10
        )

        # Combine results
        seen_ids = set()
        results = []

        for item, distance in semantic_results:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                similarity = max(0, 1 - (distance / 2))
                results.append({
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "category": item.category,
                    "location": item.location.name if item.location else None,
                    "description": item.description,
                    "relevance": round(similarity, 3),
                })

        for item in text_results:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                results.append({
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "category": item.category,
                    "location": item.location.name if item.location else None,
                    "description": item.description,
                    "relevance": 0.5,
                })

        return {
            "query": q,
            "location": location,
            "count": len(results),
            "results": results,
        }


# ===== Location Endpoints =====


@api_router.get("/locations")
async def get_all_locations(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
):
    """List all storage locations."""
    async with AsyncSessionLocal() as session:
        locations = await list_locations(session, inventory_id)
        return {
            "count": len(locations),
            "locations": [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "description": loc.description,
                }
                for loc in locations
            ],
        }


@api_router.post("/locations")
async def create_new_location(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    location: LocationCreate,
):
    """Create a new storage location."""
    async with AsyncSessionLocal() as session:
        # Generate embedding
        loc_text = f"{location.name} | {location.description}" if location.description else location.name
        embedding = generate_embedding(loc_text)

        new_loc = await create_location(
            session,
            inventory_id=inventory_id,
            name=location.name,
            description=location.description,
            embedding=embedding,
        )

        await log_transaction(
            session,
            operation="CREATE_LOCATION",
            data={"name": location.name},
        )

        return {
            "status": "success",
            "message": f"Created location: {location.name}",
            "location": {
                "id": new_loc.id,
                "name": new_loc.name,
                "description": new_loc.description,
            },
        }


# ===== Inventory Sharing Endpoints =====


@api_router.get("/inventories")
async def get_inventories(
    current_user: Annotated[TokenData, Depends(get_current_user)],
):
    """List all inventories the current user is a member of."""
    async with AsyncSessionLocal() as session:
        from .database.crud import list_inventories
        inventories = await list_inventories(session, current_user.user_id)
        return {
            "count": len(inventories),
            "inventories": [
                {
                    "id": inv.id,
                    "name": inv.name,
                    "created_at": inv.created_at.isoformat() if inv.created_at else None,
                    "member_count": len(inv.members) if inv.members else 0,
                }
                for inv in inventories
            ],
        }


@api_router.get("/inventories/{inv_id}/members")
async def get_inventory_members(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inv_id: int,
):
    """List members of an inventory."""
    async with AsyncSessionLocal() as session:
        from .database.crud import list_inventory_members
        if not await is_inventory_member(session, inv_id, current_user.user_id):
            raise HTTPException(status_code=403, detail="Not a member of this inventory")
        members = await list_inventory_members(session, inv_id)
        return {
            "count": len(members),
            "members": [
                {
                    "id": m.id,
                    "user_id": m.user_id,
                    "email": m.user.email if m.user else None,
                    "joined_at": m.joined_at.isoformat() if m.joined_at else None,
                }
                for m in members
            ],
        }


class AddMemberRequest(BaseModel):
    email: EmailStr


@api_router.post("/inventories/{inv_id}/members")
async def add_inventory_member_endpoint(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inv_id: int,
    request: AddMemberRequest,
):
    """Add a member to an inventory by email, or send an invite if they don't have an account."""
    async with AsyncSessionLocal() as session:
        from .database.crud import add_member_by_email, get_inventory
        if not await is_inventory_member(session, inv_id, current_user.user_id):
            raise HTTPException(status_code=403, detail="Not a member of this inventory")

        # Get inventory name and inviter email for the email
        inventory = await get_inventory(session, inv_id)
        inventory_name = inventory.name if inventory else "Shared Inventory"
        inviter_email = current_user.email

        member = await add_member_by_email(session, inv_id, request.email)
        if member is not None:
            # User exists and was added — send notification email
            from .email_service import send_added_email
            email_sent = send_added_email(request.email, inviter_email, inventory_name)
            response = {
                "status": "added",
                "message": f"Added {request.email} to inventory",
                "member": {
                    "id": member.id,
                    "user_id": member.user_id,
                    "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                },
            }
            if not email_sent:
                response["email_warning"] = "Member added but notification email failed to send"
            return response
        else:
            # User doesn't exist — send invite email
            from .email_service import send_invite_email
            email_sent = send_invite_email(request.email, inviter_email, inventory_name)
            if not email_sent:
                return {
                    "status": "invite_failed",
                    "detail": "Could not send invite email. Please check the email address and try again.",
                }
            return {
                "status": "invited",
                "message": f"Invite sent to {request.email}",
            }


@api_router.delete("/inventories/{inv_id}/members/{member_user_id}")
async def remove_inventory_member_endpoint(
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inv_id: int,
    member_user_id: int,
):
    """Remove a member from an inventory."""
    async with AsyncSessionLocal() as session:
        from .database.crud import remove_inventory_member
        if not await is_inventory_member(session, inv_id, current_user.user_id):
            raise HTTPException(status_code=403, detail="Not a member of this inventory")
        removed = await remove_inventory_member(session, inv_id, member_user_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Member not found")
        return {"status": "success", "message": "Member removed"}


# ===== Chat Endpoint =====


@api_router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat(
    request: Request,
    current_user: Annotated[TokenData, Depends(get_current_user)],
    inventory_id: Annotated[int, Depends(get_active_inventory_id)],
    message: ChatMessage,
):
    """Process a natural language message about inventory.
    
    Uses Azure OpenAI with tool calling if configured, otherwise
    falls back to simple pattern matching.
    """
    if AZURE_OPENAI_ENABLED:
        return await _chat_with_ai(message.message, current_user.user_id, inventory_id)
    else:
        return await _chat_fallback(message.message, inventory_id)


async def _chat_with_ai(user_message: str, user_id: int, inventory_id: int) -> ChatResponse:
    """Process chat using Azure OpenAI with tool calling."""
    from .ai_client import process_chat_with_tools, generate_display_name

    # Define tool handlers that the AI can call
    async def handle_add_item(
        name: str,
        quantity: int,
        category: str,
        location: str,
        description: str | None = None,
    ) -> dict:
        async with AsyncSessionLocal() as session:
            # Try to generate a nice display name for new locations
            display_name = None
            try:
                display_name = generate_display_name(location.strip())
                logger.info(f"Generated display name: '{location}' -> '{display_name}'")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Failed to generate display name: {e}")
            
            # Get or create location
            loc = await get_or_create_location(session, inventory_id, location.strip(), display_name=display_name)
            
            # Generate embedding
            item_text = _get_item_text_for_embedding(name, description, category)
            embedding = generate_embedding(item_text)
            
            # Log transaction
            await log_transaction(
                session,
                operation="CREATE",
                data={"name": name, "quantity": quantity, "category": category, "location": loc.name},
            )
            
            # Create item (quantity starts at 0, create_lot will set it)
            new_item = await create_item(
                session,
                inventory_id=inventory_id,
                name=name,
                quantity=0,
                category=category,
                description=description,
                location_id=loc.id,
                embedding=embedding,
            )
            
            # Create a lot for tracking (this adds to item.quantity)
            await create_lot(
                session,
                item_id=new_item.id,
                quantity=quantity,
                added_by_user_id=user_id,
            )

            return {
                "success": True,
                "item": {
                    "id": new_item.id,
                    "name": new_item.name,
                    "quantity": new_item.quantity,
                    "category": new_item.category,
                    "location": loc.name,
                },
            }

    async def handle_remove_item(item_id: int, quantity: int | None = None, lot_id: int | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            item = await get_item(session, inventory_id, item_id)
            if not item:
                return {"success": False, "error": f"Item {item_id} not found"}

            item_name = item.name
            lots = await get_lots_for_item(session, item_id)

            if lot_id is not None:
                # Remove from specific lot
                lot = next((lt for lt in lots if lt.id == lot_id), None)
                if not lot:
                    return {"success": False, "error": f"Lot {lot_id} not found for item {item_name}"}

                remove_qty = quantity if quantity else lot.quantity
                txn_data = {"lot_id": lot_id, "quantity_removed": remove_qty}
                await log_transaction(session, operation="UPDATE", item_id=item_id, data=txn_data)
                await reduce_lot(session, lot_id, remove_qty)
                date_str = lot.added_at.strftime('%b %d, %Y') if lot.added_at else 'unknown'
                return {"success": True, "message": f"Removed {remove_qty} {item_name} from batch dated {date_str}"}

            elif lots:
                # Remove from oldest lot first
                remove_qty = quantity if quantity else item.quantity
                remaining = remove_qty
                removed_from = []
                for lot in lots:  # already sorted oldest first
                    if remaining <= 0:
                        break
                    take = min(remaining, lot.quantity)
                    await reduce_lot(session, lot.id, take)
                    removed_from.append(f"{take} from batch {lot.added_at.strftime('%b %d, %Y') if lot.added_at else 'unknown'}")
                    remaining -= take

                actual_removed = remove_qty - remaining
                txn_data = {"name": item_name, "quantity_removed": actual_removed}
                await log_transaction(session, operation="DELETE", item_id=item_id, data=txn_data)
                lots_detail = [
                    {"lot_id": lt.id, "quantity": lt.quantity, "added_at": lt.added_at.isoformat() if lt.added_at else None}
                    for lt in lots
                ] if len(lots) > 1 else None
                return {
                    "success": True,
                    "message": f"Removed {actual_removed} {item_name}: {', '.join(removed_from)}",
                    "lots": lots_detail,
                }
            else:
                # No lots (legacy item), fall back to direct quantity management
                current_qty = item.quantity
                if quantity is None or quantity >= current_qty:
                    await log_transaction(session, operation="DELETE", item_id=item_id, data={"name": item_name})
                    await delete_item(session, inventory_id, item_id)
                    return {"success": True, "message": f"Removed all {current_qty} {item_name}"}
                else:
                    new_qty = current_qty - quantity
                    await log_transaction(session, operation="UPDATE", item_id=item_id, data={"quantity_removed": quantity})
                    await update_item(session, inventory_id, item_id, quantity=new_qty)
                    return {"success": True, "message": f"Removed {quantity} {item_name}, {new_qty} remaining"}

    async def handle_search_items(query: str, location: str | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            query_embedding = generate_embedding(query)
            results = await search_items_by_embedding(session, inventory_id, query_embedding, location_name=location, limit=10)
            
            if not results:
                return {"success": True, "count": 0, "items": []}
            
            return {
                "success": True,
                "count": len(results),
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "location": item.location.name if item.location else None,
                    }
                    for item, _ in results
                ],
            }

    async def handle_list_items(location: str | None = None, category: str | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            items = await list_items(session, inventory_id, location_name=location, category=category)
            result_items = []
            for item in items:
                lots = await get_lots_for_item(session, item.id)
                result_items.append({
                    "id": item.id,
                    "name": item.name,
                    "quantity": item.quantity,
                    "category": item.category,
                    "location": item.location.name if item.location else None,
                    "lots": [
                        {"lot_id": lt.id, "quantity": lt.quantity, "added_at": lt.added_at.isoformat() if lt.added_at else None}
                        for lt in lots
                    ] if lots else None,
                })
            return {
                "success": True,
                "count": len(result_items),
                "items": result_items,
            }

    async def handle_list_locations() -> dict:
        async with AsyncSessionLocal() as session:
            locations = await list_locations(session, inventory_id)
            return {
                "success": True,
                "count": len(locations),
                "locations": [{"id": loc.id, "name": loc.name} for loc in locations],
            }

    async def handle_get_oldest_items(location: str | None = None, limit: int = 10) -> dict:
        async with AsyncSessionLocal() as session:
            oldest = await get_oldest_items_crud(session, inventory_id, location_name=location, limit=limit)
            return {
                "success": True,
                "count": len(oldest),
                "items": oldest,
            }

    tool_handlers = {
        "add_item": handle_add_item,
        "remove_item": handle_remove_item,
        "search_items": handle_search_items,
        "list_items": handle_list_items,
        "list_locations": handle_list_locations,
        "get_oldest_items": handle_get_oldest_items,
    }

    try:
        response_text = await process_chat_with_tools(user_message, tool_handlers)
        return ChatResponse(response=response_text, action="ai_response")
    except (openai.OpenAIError, ValueError, json.JSONDecodeError) as e:
        logger.exception("AI chat error")
        error_str = str(e)
        if "DefaultAzureCredential" in error_str or "authentication" in error_str.lower():
            user_msg = (
                "Azure OpenAI is not reachable — the server may need to be "
                "configured with valid Azure credentials. Check the logs for details."
            )
        else:
            user_msg = "I had trouble processing that request. Try rephrasing or use the manual interface."
        return ChatResponse(response=user_msg, action="error")


async def _chat_fallback(user_message: str, inventory_id: int) -> ChatResponse:
    """Simple pattern-matching fallback when Azure OpenAI is not configured."""
    text = user_message.lower().strip()
    
    async with AsyncSessionLocal() as session:
        # Simple intent detection
        if any(word in text for word in ["what's in", "show", "list", "what do i have"]):
            # List items - try to extract location
            location = None
            for loc_word in ["freezer", "garage", "pantry", "closet", "bin", "shelf"]:
                if loc_word in text:
                    location = loc_word.title()
                    break
            
            items = await list_items(session, inventory_id, location_name=location)
            
            if not items:
                return ChatResponse(
                    response=f"No items found{' in ' + location if location else ''}.",
                    action="list",
                    data={"count": 0, "items": []},
                )
            
            item_list = ", ".join([f"{i.quantity}x {i.name}" for i in items[:5]])
            more = f" and {len(items) - 5} more" if len(items) > 5 else ""
            
            return ChatResponse(
                response=f"Found {len(items)} items{' in ' + location if location else ''}: {item_list}{more}",
                action="list",
                data={
                    "count": len(items),
                    "items": [{"id": i.id, "name": i.name, "quantity": i.quantity} for i in items],
                },
            )
        
        elif any(word in text for word in ["find", "search", "do i have", "any"]):
            # Search - extract the search term
            search_terms = text
            for word in ["find", "search", "for", "do", "i", "have", "any", "?"]:
                search_terms = search_terms.replace(word, "")
            search_terms = search_terms.strip()
            
            if not search_terms:
                return ChatResponse(response="What would you like to search for?")
            
            query_embedding = generate_embedding(search_terms)
            raw_results = await search_items_by_embedding(session, inventory_id, query_embedding, limit=5)
            
            # Filter by similarity threshold (distance < 1.0 means reasonably similar)
            results = [(item, dist) for item, dist in raw_results if dist < 1.0]
            
            if not results:
                return ChatResponse(
                    response=f"No items found matching '{search_terms}'.",
                    action="search",
                    data={"query": search_terms, "results": []},
                )
            
            item_list = ", ".join([f"{item.quantity}x {item.name}" for item, _ in results])
            return ChatResponse(
                response=f"Found: {item_list}",
                action="search",
                data={
                    "query": search_terms,
                    "results": [{"id": i.id, "name": i.name, "quantity": i.quantity} for i, _ in results],
                },
            )
        
        else:
            # Default response
            return ChatResponse(
                response="I can help you manage your inventory! Try asking:\n"
                "- 'What's in the freezer?'\n"
                "- 'Do I have any batteries?'\n"
                "- 'Show all items'\n\n"
                "Note: Azure OpenAI is not configured. Set AZURE_OPENAI_ENDPOINT to enable "
                "full natural language understanding including adding/removing items.",
            )


# ===== Mount API router at both /api (backward compat) and /api/v1 =====
app.include_router(api_router, prefix="/api/v1")
app.include_router(api_router, prefix="/api")


# ===== Frontend Serving =====


@app.get("/manifest.json")
async def serve_manifest():
    """Serve the PWA manifest."""
    manifest_path = FRONTEND_DIR / "manifest.json"
    if manifest_path.exists():
        return FileResponse(manifest_path, media_type="application/manifest+json")
    raise HTTPException(status_code=404, detail="Manifest not found")


@app.get("/sw.js")
async def serve_service_worker():
    """Serve the service worker from root scope."""
    sw_path = FRONTEND_DIR / "sw.js"
    if sw_path.exists():
        return FileResponse(sw_path, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="Service worker not found")


@app.get("/icons/{icon_name}")
async def serve_icon(icon_name: str):
    """Serve PWA icon files."""
    icons_dir = FRONTEND_DIR / "icons"
    icon_path = (icons_dir / icon_name).resolve()
    if icon_path.exists() and icon_path.parent == icons_dir.resolve():
        media_type = "image/svg+xml" if icon_name.endswith(".svg") else "image/png"
        return FileResponse(icon_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Icon not found")


@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend not found")


def run_api():
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # nosec B104


if __name__ == "__main__":
    run_api()

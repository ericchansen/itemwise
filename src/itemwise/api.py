"""FastAPI REST API for inventory management."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError

# Load environment variables from .env file (find it relative to this file)
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

from .database.crud import (
    create_item,
    create_location,
    create_user,
    delete_item,
    get_item,
    get_or_create_location,
    list_items,
    list_locations,
    log_transaction,
    search_items_by_embedding,
    search_items_by_text,
    update_item,
)
from .database.engine import AsyncSessionLocal, close_db, init_db
from .embeddings import generate_embedding
from .auth import hash_password, create_access_token, create_refresh_token, Token

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

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Auth Endpoints =====


@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserRegister):
    """Register a new user account.

    Returns access and refresh tokens on successful registration.
    """
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


# ===== Item Endpoints =====


@app.get("/api/items")
async def get_items(
    category: Optional[str] = Query(None, description="Filter by category"),
    location: Optional[str] = Query(None, description="Filter by location name"),
):
    """List all inventory items with optional filters."""
    async with AsyncSessionLocal() as session:
        items = await list_items(
            session,
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


@app.post("/api/items")
async def create_new_item(item: ItemCreate):
    """Add a new item to inventory."""
    async with AsyncSessionLocal() as session:
        # Get or create location if specified
        location_id = None
        location_name = None
        if item.location:
            loc = await get_or_create_location(session, item.location.strip())
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


@app.get("/api/items/{item_id}")
async def get_single_item(item_id: int):
    """Get a single item by ID."""
    async with AsyncSessionLocal() as session:
        item = await get_item(session, item_id)
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


@app.put("/api/items/{item_id}")
async def update_existing_item(item_id: int, item: ItemUpdate):
    """Update an existing item."""
    async with AsyncSessionLocal() as session:
        existing = await get_item(session, item_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Item {item_id} not found")

        # Handle location update
        location_id = None
        if item.location is not None:
            if item.location:
                loc = await get_or_create_location(session, item.location.strip())
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


@app.delete("/api/items/{item_id}")
async def delete_existing_item(item_id: int):
    """Delete an item from inventory."""
    async with AsyncSessionLocal() as session:
        item = await get_item(session, item_id)
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

        deleted = await delete_item(session, item_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete item")

        return {
            "status": "success",
            "message": f"Removed {item_name}" + (f" from {location_name}" if location_name else ""),
        }


# ===== Search Endpoint =====


@app.get("/api/search")
async def search_items(
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
            session, query_embedding, location_name=location, limit=10
        )

        # Text search fallback
        text_results = await search_items_by_text(
            session, q, location_name=location, limit=10
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


@app.get("/api/locations")
async def get_all_locations():
    """List all storage locations."""
    async with AsyncSessionLocal() as session:
        locations = await list_locations(session)
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


@app.post("/api/locations")
async def create_new_location(location: LocationCreate):
    """Create a new storage location."""
    async with AsyncSessionLocal() as session:
        # Generate embedding
        loc_text = f"{location.name} | {location.description}" if location.description else location.name
        embedding = generate_embedding(loc_text)

        new_loc = await create_location(
            session,
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


# ===== Chat Endpoint =====


@app.post("/api/chat", response_model=ChatResponse)
async def chat(message: ChatMessage):
    """Process a natural language message about inventory.
    
    Uses Azure OpenAI with tool calling if configured, otherwise
    falls back to simple pattern matching.
    """
    if AZURE_OPENAI_ENABLED:
        return await _chat_with_ai(message.message)
    else:
        return await _chat_fallback(message.message)


async def _chat_with_ai(user_message: str) -> ChatResponse:
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
            except Exception as e:
                logger.warning(f"Failed to generate display name: {e}")
            
            # Get or create location
            loc = await get_or_create_location(session, location.strip(), display_name=display_name)
            
            # Generate embedding
            item_text = _get_item_text_for_embedding(name, description, category)
            embedding = generate_embedding(item_text)
            
            # Log transaction
            await log_transaction(
                session,
                operation="CREATE",
                data={"name": name, "quantity": quantity, "category": category, "location": loc.name},
            )
            
            # Create item
            new_item = await create_item(
                session,
                name=name,
                quantity=quantity,
                category=category,
                description=description,
                location_id=loc.id,
                embedding=embedding,
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

    async def handle_remove_item(item_id: int, quantity: int | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            item = await get_item(session, item_id)
            if not item:
                return {"success": False, "error": f"Item {item_id} not found"}
            
            item_name = item.name
            current_qty = item.quantity
            
            if quantity is None or quantity >= current_qty:
                # Remove completely
                await log_transaction(session, operation="DELETE", item_id=item_id, data={"name": item_name})
                await delete_item(session, item_id)
                return {"success": True, "message": f"Removed all {current_qty} {item_name}"}
            else:
                # Reduce quantity
                new_qty = current_qty - quantity
                await log_transaction(session, operation="UPDATE", item_id=item_id, data={"quantity_removed": quantity})
                await update_item(session, item_id, quantity=new_qty)
                return {"success": True, "message": f"Removed {quantity} {item_name}, {new_qty} remaining"}

    async def handle_search_items(query: str, location: str | None = None) -> dict:
        async with AsyncSessionLocal() as session:
            query_embedding = generate_embedding(query)
            results = await search_items_by_embedding(session, query_embedding, location_name=location, limit=10)
            
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
            items = await list_items(session, location_name=location, category=category)
            return {
                "success": True,
                "count": len(items),
                "items": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "quantity": item.quantity,
                        "category": item.category,
                        "location": item.location.name if item.location else None,
                    }
                    for item in items
                ],
            }

    async def handle_list_locations() -> dict:
        async with AsyncSessionLocal() as session:
            locations = await list_locations(session)
            return {
                "success": True,
                "count": len(locations),
                "locations": [{"id": loc.id, "name": loc.name} for loc in locations],
            }

    tool_handlers = {
        "add_item": handle_add_item,
        "remove_item": handle_remove_item,
        "search_items": handle_search_items,
        "list_items": handle_list_items,
        "list_locations": handle_list_locations,
    }

    try:
        response_text = await process_chat_with_tools(user_message, tool_handlers)
        return ChatResponse(response=response_text, action="ai_response")
    except Exception as e:
        logger.exception("AI chat error")
        return ChatResponse(
            response=f"I had trouble processing that request. Error: {str(e)}. "
            "Try rephrasing or use the manual interface.",
            action="error",
        )


async def _chat_fallback(user_message: str) -> ChatResponse:
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
            
            items = await list_items(session, location_name=location)
            
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
            raw_results = await search_items_by_embedding(session, query_embedding, limit=5)
            
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


# ===== Frontend Serving =====


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
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run_api()

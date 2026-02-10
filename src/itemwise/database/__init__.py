"""Database package initialization."""

from .crud import (
    create_item,
    create_location,
    delete_item,
    get_item,
    get_location,
    get_location_by_name,
    get_or_create_location,
    get_transaction_logs,
    list_items,
    list_locations,
    log_transaction,
    normalize_location_name,
    search_items_by_embedding,
    search_items_by_text,
    update_item,
)
from .engine import AsyncSessionLocal, close_db, get_session, init_db
from .models import Base, Inventory, InventoryItem, InventoryMember, ItemLot, Location, TransactionLog

__all__ = [
    # Models
    "Base",
    "Inventory",
    "InventoryItem",
    "InventoryMember",
    "ItemLot",
    "Location",
    "TransactionLog",
    # Engine
    "AsyncSessionLocal",
    "init_db",
    "close_db",
    "get_session",
    # CRUD - Items
    "create_item",
    "get_item",
    "list_items",
    "update_item",
    "delete_item",
    "search_items_by_text",
    "search_items_by_embedding",
    # CRUD - Locations
    "create_location",
    "get_location",
    "get_location_by_name",
    "get_or_create_location",
    "list_locations",
    "normalize_location_name",
    # CRUD - Transactions
    "log_transaction",
    "get_transaction_logs",
]

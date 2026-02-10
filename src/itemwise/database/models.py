"""SQLAlchemy database models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Embedding dimension for Azure OpenAI text-embedding-ada-002 model
EMBEDDING_DIMENSION = 1536


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class User(Base):
    """Model for user accounts."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class Inventory(Base):
    """Model for shared inventories (households)."""

    __tablename__ = "inventories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    members = relationship("InventoryMember", back_populates="inventory", cascade="all, delete-orphan")
    items = relationship("InventoryItem", back_populates="inventory")
    locations = relationship("Location", back_populates="inventory")

    def __repr__(self) -> str:
        return f"<Inventory(id={self.id}, name='{self.name}')>"


class InventoryMember(Base):
    """Model for inventory membership (many-to-many users ↔ inventories)."""

    __tablename__ = "inventory_members"
    __table_args__ = (
        UniqueConstraint('inventory_id', 'user_id', name='uq_inventory_member'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    inventory_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventories.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    inventory = relationship("Inventory", back_populates="members")
    user = relationship("User")

    def __repr__(self) -> str:
        return f"<InventoryMember(inventory_id={self.inventory_id}, user_id={self.user_id})>"


class Location(Base):
    """Model for storage locations (freezer, garage, closet, etc.)."""

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint('inventory_id', 'normalized_name', name='uq_location_inventory_normalized_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    inventory_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventories.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)  # Display name (e.g., "Tim's Pocket")
    normalized_name: Mapped[str] = mapped_column(String, nullable=False, index=True)  # For matching (e.g., "tims pocket")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    if TYPE_CHECKING:
        items: Mapped[list["InventoryItem"]]
        inventory: Mapped["Inventory"]
    else:
        items = relationship("InventoryItem", back_populates="location")
        inventory = relationship("Inventory", back_populates="locations")

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}')>"


class InventoryItem(Base):
    """Model for inventory items stored in locations."""

    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("locations.id"), nullable=True, index=True
    )
    inventory_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventories.id"), nullable=False, index=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationships
    if TYPE_CHECKING:
        location: Mapped[Optional["Location"]]
    else:
        location = relationship("Location", back_populates="items")
        inventory = relationship("Inventory", back_populates="items")
        lots = relationship("ItemLot", back_populates="item", cascade="all, delete-orphan", order_by="ItemLot.added_at")

    def __repr__(self) -> str:
        return f"<InventoryItem(id={self.id}, name='{self.name}', quantity={self.quantity})>"


class ItemLot(Base):
    """Model for tracking individual batches/lots of items with dates."""

    __tablename__ = "item_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("inventory_items.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    added_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    item = relationship("InventoryItem", back_populates="lots")
    added_by = relationship("User")

    def __repr__(self) -> str:
        return f"<ItemLot(id={self.id}, item_id={self.item_id}, quantity={self.quantity}, added_at={self.added_at})>"


class TransactionLog(Base):
    """Model for logging AI operations."""

    __tablename__ = "transaction_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation: Mapped[str] = mapped_column(String, nullable=False)
    item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="PENDING")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<TransactionLog(id={self.id}, operation='{self.operation}', status='{self.status}')>"

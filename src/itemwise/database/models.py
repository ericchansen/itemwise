"""SQLAlchemy database models."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Embedding dimension for sentence-transformers all-MiniLM-L6-v2 model
EMBEDDING_DIMENSION = 384


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


class Location(Base):
    """Model for storage locations (freezer, garage, closet, etc.)."""

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint('user_id', 'normalized_name', name='uq_location_user_normalized_name'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
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
        user: Mapped["User"]
    else:
        items = relationship("InventoryItem", back_populates="location")
        user = relationship("User", backref="locations")

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
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    embedding: Mapped[Optional[list[float]]] = mapped_column(
        Vector(EMBEDDING_DIMENSION), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    # Relationship to location
    if TYPE_CHECKING:
        location: Mapped[Optional["Location"]]
    else:
        location = relationship("Location", back_populates="items")

    def __repr__(self) -> str:
        return f"<InventoryItem(id={self.id}, name='{self.name}', quantity={self.quantity})>"


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

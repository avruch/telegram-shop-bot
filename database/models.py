from dataclasses import dataclass, field
from typing import Optional
import json


@dataclass
class Product:
    id: int
    name: str
    description: str
    price: float
    image_url: str
    stock_json: str

    @property
    def stock(self) -> dict:
        return json.loads(self.stock_json)

    def available_sizes(self) -> list[str]:
        return [size for size, qty in self.stock.items() if qty > 0]

    def stock_for_size(self, size: str) -> int:
        return self.stock.get(size, 0)

    def to_catalog_summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "available_sizes": self.available_sizes(),
            "description": self.description,
        }

    @classmethod
    def from_row(cls, row) -> "Product":
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            price=row["price"],
            image_url=row["image_url"] or "",
            stock_json=row["stock_json"],
        )


@dataclass
class OrderItem:
    id: int
    order_id: int
    product_id: int
    size: str
    quantity: int
    product_name: Optional[str] = None
    product_price: Optional[float] = None

    @classmethod
    def from_row(cls, row) -> "OrderItem":
        return cls(
            id=row["id"],
            order_id=row["order_id"],
            product_id=row["product_id"],
            size=row["size"],
            quantity=row["quantity"],
            product_name=row["name"] if "name" in row.keys() else None,
            product_price=row["price"] if "price" in row.keys() else None,
        )


@dataclass
class Order:
    id: int
    user_id: int
    status: str
    total_price: float
    shipping_name: Optional[str] = None
    shipping_address: Optional[str] = None
    shipping_phone: Optional[str] = None
    screenshot_file_id: Optional[str] = None
    items: list[OrderItem] = field(default_factory=list)

    @classmethod
    def from_row(cls, row) -> "Order":
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            status=row["status"],
            total_price=row["total_price"],
            shipping_name=row["shipping_name"],
            shipping_address=row["shipping_address"],
            shipping_phone=row["shipping_phone"],
            screenshot_file_id=row["screenshot_file_id"],
        )

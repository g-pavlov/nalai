#!/usr/bin/env python3
"""
Mock Ecommerce API Service
A simple FastAPI service that implements the ecommerce API specification
"""

import uuid
from datetime import UTC, datetime

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Initialize FastAPI app
app = FastAPI(
    title="Ecommerce API",
    version="1.0.0",
    description="A simple ecommerce API for managing products, orders, and users"
)

# Security
security = HTTPBearer()

# Mock data storage
products_db = {}
orders_db = {}
users_db = {}

# Sample data
SAMPLE_PRODUCTS = [
    {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "name": "Wireless Headphones",
        "description": "High-quality wireless headphones with noise cancellation",
        "price": 199.99,
        "category": "Electronics",
        "stock": 50,
        "imageUrl": "https://example.com/headphones.jpg",
        "createdAt": "2024-01-01T10:00:00Z",
        "updatedAt": "2024-01-01T10:00:00Z"
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440002",
        "name": "Smartphone",
        "description": "Latest smartphone with advanced features",
        "price": 799.99,
        "category": "Electronics",
        "stock": 25,
        "imageUrl": "https://example.com/smartphone.jpg",
        "createdAt": "2024-01-01T10:00:00Z",
        "updatedAt": "2024-01-01T10:00:00Z"
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440003",
        "name": "Running Shoes",
        "description": "Comfortable running shoes for all terrains",
        "price": 89.99,
        "category": "Sports",
        "stock": 100,
        "imageUrl": "https://example.com/shoes.jpg",
        "createdAt": "2024-01-01T10:00:00Z",
        "updatedAt": "2024-01-01T10:00:00Z"
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "name": "Coffee Maker",
        "description": "Automatic coffee maker with timer",
        "price": 149.99,
        "category": "Home & Kitchen",
        "stock": 30,
        "imageUrl": "https://example.com/coffee-maker.jpg",
        "createdAt": "2024-01-01T10:00:00Z",
        "updatedAt": "2024-01-01T10:00:00Z"
    },
    {
        "id": "550e8400-e29b-41d4-a716-446655440005",
        "name": "Yoga Mat",
        "description": "Non-slip yoga mat for home workouts",
        "price": 29.99,
        "category": "Sports",
        "stock": 75,
        "imageUrl": "https://example.com/yoga-mat.jpg",
        "createdAt": "2024-01-01T10:00:00Z",
        "updatedAt": "2024-01-01T10:00:00Z"
    }
]

SAMPLE_USER = {
    "id": "user-123e4567-e89b-12d3-a456-426614174000",
    "email": "john.doe@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "phone": "+1-555-0123",
    "createdAt": "2024-01-01T10:00:00Z",
    "updatedAt": "2024-01-01T10:00:00Z"
}

# Initialize mock data
for product in SAMPLE_PRODUCTS:
    products_db[product["id"]] = product

users_db[SAMPLE_USER["id"]] = SAMPLE_USER

# Pydantic models
class CreateProductRequest(BaseModel):
    name: str
    description: str | None = None
    price: float = Field(..., ge=0)
    category: str
    stock: int = Field(..., ge=0)
    imageUrl: str | None = None

class UpdateProductRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    price: float | None = Field(None, ge=0)
    category: str | None = None
    stock: int | None = Field(None, ge=0)
    imageUrl: str | None = None

class Address(BaseModel):
    street: str
    city: str
    state: str
    zipCode: str
    country: str

class OrderItem(BaseModel):
    productId: str
    quantity: int = Field(..., ge=1)
    unitPrice: float = Field(..., ge=0)
    totalPrice: float = Field(..., ge=0)

class CreateOrderRequest(BaseModel):
    items: list[dict]  # Simplified for mock
    shippingAddress: Address

class UpdateUserRequest(BaseModel):
    firstName: str | None = None
    lastName: str | None = None
    phone: str | None = None

class Pagination(BaseModel):
    page: int
    limit: int
    total: int
    pages: int

class Error(BaseModel):
    error: str
    code: str | None = None
    details: dict | None = None

# Helper functions
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Mock authentication - always returns the sample user"""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Invalid authentication")
    return SAMPLE_USER

def calculate_pagination(items: list, page: int, limit: int) -> dict:
    """Calculate pagination info"""
    total = len(items)
    pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    end = start + limit
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "pages": pages
    }

def get_now() -> str:
    """Get current timestamp in ISO format"""
    return datetime.now(UTC).isoformat()

# API Endpoints

@app.get("/products", tags=["Products"])
async def list_products(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    category: str | None = None
):
    """List all products with optional filtering and pagination"""
    products = list(products_db.values())

    # Filter by category if provided
    if category:
        products = [p for p in products if p["category"].lower() == category.lower()]

    # Calculate pagination
    pagination_info = calculate_pagination(products, page, limit)
    start = (page - 1) * limit
    end = start + limit
    paginated_products = products[start:end]

    return {
        "products": paginated_products,
        "pagination": pagination_info
    }

@app.post("/products", tags=["Products"], status_code=201)
async def create_product(
    product_data: CreateProductRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new product"""
    product_id = str(uuid.uuid4())
    now = get_now()

    new_product = {
        "id": product_id,
        "name": product_data.name,
        "description": product_data.description,
        "price": product_data.price,
        "category": product_data.category,
        "stock": product_data.stock,
        "imageUrl": product_data.imageUrl,
        "createdAt": now,
        "updatedAt": now
    }

    products_db[product_id] = new_product
    return new_product

@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: str):
    """Get product by ID"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")
    return products_db[product_id]

@app.put("/products/{product_id}", tags=["Products"])
async def update_product(
    product_id: str,
    product_data: UpdateProductRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update an existing product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")

    product = products_db[product_id].copy()

    # Update only provided fields
    if product_data.name is not None:
        product["name"] = product_data.name
    if product_data.description is not None:
        product["description"] = product_data.description
    if product_data.price is not None:
        product["price"] = product_data.price
    if product_data.category is not None:
        product["category"] = product_data.category
    if product_data.stock is not None:
        product["stock"] = product_data.stock
    if product_data.imageUrl is not None:
        product["imageUrl"] = product_data.imageUrl

    product["updatedAt"] = get_now()
    products_db[product_id] = product

    return product

@app.delete("/products/{product_id}", tags=["Products"], status_code=204)
async def delete_product(
    product_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a product"""
    if product_id not in products_db:
        raise HTTPException(status_code=404, detail="Product not found")

    del products_db[product_id]

@app.get("/orders", tags=["Orders"])
async def list_orders(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: str | None = None,
    current_user: dict = Depends(get_current_user)
):
    """List user orders with optional filtering and pagination"""
    user_orders = [order for order in orders_db.values() if order["userId"] == current_user["id"]]

    # Filter by status if provided
    if status:
        user_orders = [order for order in user_orders if order["status"] == status]

    # Calculate pagination
    pagination_info = calculate_pagination(user_orders, page, limit)
    start = (page - 1) * limit
    end = start + limit
    paginated_orders = user_orders[start:end]

    return {
        "orders": paginated_orders,
        "pagination": pagination_info
    }

@app.post("/orders", tags=["Orders"], status_code=201)
async def create_order(
    order_data: CreateOrderRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create a new order"""
    order_id = str(uuid.uuid4())
    now = get_now()

    # Process order items
    order_items = []
    total_amount = 0

    for item in order_data.items:
        product_id = item["productId"]
        quantity = item["quantity"]

        if product_id not in products_db:
            raise HTTPException(status_code=400, detail=f"Product {product_id} not found")

        product = products_db[product_id]
        if product["stock"] < quantity:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for product {product['name']}")

        unit_price = product["price"]
        total_price = unit_price * quantity
        total_amount += total_price

        order_items.append({
            "productId": product_id,
            "quantity": quantity,
            "unitPrice": unit_price,
            "totalPrice": total_price
        })

        # Update stock
        products_db[product_id]["stock"] -= quantity
        products_db[product_id]["updatedAt"] = now

    new_order = {
        "id": order_id,
        "userId": current_user["id"],
        "items": order_items,
        "totalAmount": total_amount,
        "status": "pending",
        "shippingAddress": order_data.shippingAddress.dict(),
        "createdAt": now,
        "updatedAt": now
    }

    orders_db[order_id] = new_order
    return new_order

@app.get("/orders/{order_id}", tags=["Orders"])
async def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get order by ID"""
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")

    order = orders_db[order_id]
    if order["userId"] != current_user["id"]:
        raise HTTPException(status_code=401, detail="Not authorized to view this order")

    return order

@app.get("/users/profile", tags=["Users"])
async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get user profile"""
    return current_user

@app.put("/users/profile", tags=["Users"])
async def update_user_profile(
    user_data: UpdateUserRequest,
    current_user: dict = Depends(get_current_user)
):
    """Update user profile"""
    updated_user = current_user.copy()

    # Update only provided fields
    if user_data.firstName is not None:
        updated_user["firstName"] = user_data.firstName
    if user_data.lastName is not None:
        updated_user["lastName"] = user_data.lastName
    if user_data.phone is not None:
        updated_user["phone"] = user_data.phone

    updated_user["updatedAt"] = get_now()
    users_db[current_user["id"]] = updated_user

    return updated_user

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": get_now()}

if __name__ == "__main__":
    print("Starting Mock Ecommerce API Service...")
    print("API Documentation available at: http://localhost:8000/docs")
    print("Health check: http://localhost:8000/health")
    print("Sample products available at: http://localhost:8000/products")
    print("\nSample API calls:")
    print("  GET  /products")
    print("  POST /products")
    print("  GET  /orders")
    print("  POST /orders")
    print("  GET  /users/profile")
    print("\nNote: All endpoints require Bearer token authentication (any token will work)")

    uvicorn.run(app, host="0.0.0.0", port=8000)

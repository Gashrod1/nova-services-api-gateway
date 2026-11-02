from fastapi import FastAPI, HTTPException

app = FastAPI(title="E-Shop Orders Service")

orders = [
    {"id": 101, "userId": 1, "item": "Laptop"},
    {"id": 102, "userId": 2, "item": "Phone"},
    {"id": 103, "userId": 1, "item": "Keyboard"},
]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/orders")
def get_orders():
    return orders


@app.get("/orders/user/{user_id}")
def get_orders_by_user(user_id: int):
    return [order for order in orders if order["userId"] == user_id]


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    order = next((o for o in orders if o["id"] == order_id), None)

    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    return order

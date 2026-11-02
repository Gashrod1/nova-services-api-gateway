import os
import asyncio
import secrets

import httpx
from fastapi import FastAPI, Depends, Header, HTTPException

app = FastAPI(title="E-Shop API Gateway")

USERS_SERVICE = os.getenv("USERS_SERVICE", "http://users:8000")
ORDERS_SERVICE = os.getenv("ORDERS_SERVICE", "http://orders:8000")

# Le token vient d'une variable d'environnement.
GATEWAY_TOKEN = os.getenv("GATEWAY_TOKEN", "")


# Vérification de l'authentification
async def require_token(
    authorization: str | None = Header(default=None),
):
    if not GATEWAY_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Gateway authentication is not configured",
        )

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.removeprefix("Bearer ")

    if not token or not secrets.compare_digest(token, GATEWAY_TOKEN):
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# Fonction commune pour appeler les microservices
async def fetch_json(url: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail="A backend service is unavailable",
        ) from exc


# Health check public
@app.get("/health")
async def health():
    return {"status": "ok"}


# Route protégée : Users
@app.get("/users", dependencies=[Depends(require_token)])
async def proxy_users():
    return await fetch_json(f"{USERS_SERVICE}/users")


# Route protégée : Orders
@app.get("/orders", dependencies=[Depends(require_token)])
async def proxy_orders():
    return await fetch_json(f"{ORDERS_SERVICE}/orders")


# Route protégée : agrégation User + Orders
@app.get("/profile/{user_id}", dependencies=[Depends(require_token)])
async def get_profile(user_id: int):

    users, orders = await asyncio.gather(
        fetch_json(f"{USERS_SERVICE}/users"),
        fetch_json(f"{ORDERS_SERVICE}/orders"),
    )

    user = next(
        (u for u in users if u["id"] == user_id),
        None,
    )

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user_orders = [
        order for order in orders
        if order["userId"] == user_id
    ]

    return {
        "user": user,
        "orders": user_orders,
    }

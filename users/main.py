from fastapi import FastAPI, HTTPException

app = FastAPI(title="E-Shop Users Service")

users = [
    {"id": 1, "name": "Alice", "email": "alice@test.com"},
    {"id": 2, "name": "Bob", "email": "bob@test.com"},
]


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/users")
def get_users():
    return users


@app.get("/users/{user_id}")
def get_user(user_id: int):
    user = next((u for u in users if u["id"] == user_id), None)

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user

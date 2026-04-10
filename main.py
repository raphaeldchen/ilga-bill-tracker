from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database import init_db
from routers import bills, actions, fetch, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Illinois Legislative Tracker", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(bills.router)
app.include_router(actions.router)
app.include_router(fetch.router)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")

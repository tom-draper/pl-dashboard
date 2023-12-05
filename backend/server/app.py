import os
import sys
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Required to access database module in parent folder
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import Database  # noqa: E402

season = 2023

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

database = Database(season)
cache = {
    "team": {"time": None, "data": None},
    "fantasy": {"time": None, "data": None},
    "predictions": {"time": None, "data": None},
}


def recent_cache(date: datetime) -> bool:
    return (datetime.now() - date).total_seconds() < 30


@app.get("/api/teams")
async def team() -> str:
    if cache["team"]["data"] is not None and recent_cache(cache["team"]["time"]):
        teams_data = cache["team"]["data"]
    else:
        teams_data = await database.get_teams_data()
        cache["team"]["data"] = teams_data
        cache["team"]["time"] = datetime.now()
    return teams_data


@app.get("/api/fantasy")
async def fantasy() -> str:
    if cache["fantasy"]["data"] is not None and recent_cache(cache["fantasy"]["time"]):
        fantasy_data = cache["fantasy"]["data"]
    else:
        fantasy_data = await database.get_fantasy_data()
        cache["fantasy"]["data"] = fantasy_data
        cache["fantasy"]["time"] = datetime.now()
    return fantasy_data


@app.get("/api/predictions")
async def predictions() -> str:
    if cache["predictions"]["data"] is not None and recent_cache(
        cache["predictions"]["time"]
    ):
        predictions_data = cache["predictions"]["data"]
    else:
        predictions_data = await database.get_predictions()
        cache["predictions"]["data"] = predictions_data
        cache["predictions"]["time"] = datetime.now()
    return predictions_data


if __name__ == "__main__":
    uvicorn.run("server.app:app", reload=True)

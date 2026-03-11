import logging
from contextlib import asynccontextmanager

from datetime import datetime
import json
import os
from dotenv import load_dotenv

from fastapi import FastAPI, Query, Request,Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.database import close_db, get_pool, init_db
from app.models import Transaction, TransactionOut, OverlandPayload

logger = logging.getLogger("uvicorn.error")

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database table 'transactions' is ready.")
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    if request.method == "POST":
        return PlainTextResponse("Invalid JSON payload", status_code=400)
    return PlainTextResponse("Invalid query parameters", status_code=400)


@app.get("/health", response_class=PlainTextResponse)
async def health():
    return "LifeOS is healthy"


@app.post("/transaction", response_class=PlainTextResponse, status_code=201)
async def create_transactions(transactions: list[Transaction]):
    pool = get_pool()
    count = 0

    sql = """
        INSERT INTO transactions (id, vendor, amount, timestamp)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (id) DO NOTHING
    """

    async with pool.acquire() as conn:
        for t in transactions:
            try:
                await conn.execute(sql, t.id, t.vendor, t.amount, t.timestamp)
                count += 1
            except Exception as e:
                logger.error(f"Error inserting transaction {t.id}: {e}")
                continue

    return f"Processed {count} transaction(s)"


@app.get("/transactions", response_model=list[TransactionOut])
async def get_transactions(
    start: datetime = Query(..., description="Start of time range"),
    end: datetime = Query(..., description="End of time range"),
    limit: int = Query(100, ge=1, le=1000, description="Max number of results"),
):
    pool = get_pool()

    sql = """
        SELECT id, vendor, amount, timestamp, created_at
        FROM transactions
        WHERE timestamp >= $1 AND timestamp <= $2
        ORDER BY timestamp DESC
        LIMIT $3
    """

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, start, end, limit)

    return [dict(row) for row in rows]


# Initialize the HTTP Bearer security scheme
security = HTTPBearer()

def verify_bearer_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Read the expected token from your .env file
    expected_token = os.getenv("OVERLAND_TOKEN")
    
    # Safety check: ensure the server actually has a token configured
    if not expected_token:
        logger.error("OVERLAND_TOKEN environment variable is not set.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Server configuration error"
        )
        
    # Check if the token sent by Overland matches your .env token
    if credentials.credentials != expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    return credentials.credentials


@app.post("/location", status_code=200)
async def create_locations(
    payload: OverlandPayload,
    token: str = Depends(verify_bearer_token)
):
    pool = get_pool()
    count = 0

    # ST_MakePoint takes (longitude, latitude)
    # The ::jsonb cast ensures the raw dictionary is stored correctly
    sql = """
        INSERT INTO location_logs (
            timestamp, geom, latitude, longitude, altitude,
            horizontal_accuracy, battery_level, battery_state,
            wifi_ssid, motion_state, device_id, raw_payload
        )
        VALUES (
            $1, ST_SetSRID(ST_MakePoint($2, $3), 4326), $3, $2, $4,
            $5, $6, $7, $8, $9, $10, $11::jsonb
        )
        ON CONFLICT (timestamp) 
        DO UPDATE SET 
            geom = EXCLUDED.geom,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude,
            altitude = EXCLUDED.altitude,
            horizontal_accuracy = EXCLUDED.horizontal_accuracy,
            battery_level = EXCLUDED.battery_level,
            battery_state = EXCLUDED.battery_state,
            wifi_ssid = EXCLUDED.wifi_ssid,
            motion_state = EXCLUDED.motion_state,
            raw_payload = EXCLUDED.raw_payload;
    """

    async with pool.acquire() as conn:
        for loc in payload.locations:
            props = loc.properties
            
            # Overland GeoJSON coordinates are [longitude, latitude]
            lon = loc.geometry.coordinates[0]
            lat = loc.geometry.coordinates[1]

            # Convert motion list ['driving', 'stationary'] to a comma-separated string
            motion_str = ",".join(props.motion) if props.motion else None

            # Serialize the specific location feature back to JSON string for the raw_payload column
            raw_json = json.dumps(loc.model_dump(mode="json"))

            try:
                await conn.execute(
                    sql,
                    props.timestamp,
                    lon,                      # $2
                    lat,                      # $3
                    props.altitude,           # $4
                    props.horizontal_accuracy,# $5
                    props.battery_level,      # $6
                    props.battery_state,      # $7
                    props.wifi,               # $8
                    motion_str,               # $9
                    props.device_id,          # $10
                    raw_json                  # $11
                )
                count += 1
            except Exception as e:
                logger.error(f"Error inserting location: {e}")
                continue

    # Overland specifically expects a JSON response with "result": "ok" to mark the batch as successfully sent
    return JSONResponse(content={"result": "ok"})
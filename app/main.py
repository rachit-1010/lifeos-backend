import logging
from contextlib import asynccontextmanager

from datetime import datetime

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse

from app.database import close_db, get_pool, init_db
from app.models import Transaction, TransactionOut

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database table 'transactions' is ready.")
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)


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

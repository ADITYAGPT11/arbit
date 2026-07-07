"""
FastAPI Application Factory — no database, no auth.
Pure API-driven: fetches live data from brokers and computes analytics on the fly.
"""

import asyncio
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from fastapi.middleware.gzip import GZipMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send, Message

from core.deps import set_service_flags
from core.config import settings

from routers import (
    market as market_router,
    brokers as brokers_router,
    arbitrage as arbitrage_router,
    options as options_router,
    iv as iv_router,
    analytics as analytics_router,
    risk as risk_router,
    backtest as backtest_router,
    correlation as correlation_router,
)

from services.market_data_service import setup_market_data_service
from services.arbitrage_service import setup_arbitrage_service

# ── Load .env ──
ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# ── Logging ──
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── App ──
app = FastAPI(title="Indian Markets Arbitrage Platform")
api_router = APIRouter(prefix="/api")


# ── Pure ASGI CORS middleware — injects headers at the protocol level ──

class CORSHeadersMiddleware:
    """ASGI middleware that adds CORS headers to every response.

    Operates at the raw ASGI Send/Receive level — intercepts the
    'http.response.start' message and appends CORS headers before
    forwarding it. This is the most reliable approach because:
    - It runs at the ASGI protocol level, before any Starlette middleware
    - It works on every response type (streaming, file, JSON, etc.)
    - It works even if an error occurs during response processing
    - It handles OPTIONS preflight requests correctly
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"access-control-allow-origin", b"*"))
                headers.append((b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS, PATCH"))
                headers.append((b"access-control-allow-headers", b"*"))
                headers.append((b"access-control-max-age", b"86400"))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_cors)
        except Exception as exc:
            logger.exception("Unhandled exception in request handler")
            body = json.dumps({"detail": str(exc)}).encode("utf-8")
            headers = [
                (b"access-control-allow-origin", b"*"),
                (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS, PATCH"),
                (b"access-control-allow-headers", b"*"),
                (b"access-control-max-age", b"86400"),
                (b"content-type", b"application/json"),
            ]
            await send({
                "type": "http.response.start",
                "status": 500,
                "headers": headers,
            })
            await send({
                "type": "http.response.body",
                "body": body,
            })


# ── Attempt external service imports & set availability flags ──

angel_available = False
brokers_available = False
oc_available = False
iv_available = False

try:
    from angel_one_service import get_angel_service, SYMBOL_TOKENS, INDEX_TOKENS as ANGEL_INDEX_TOKENS
    angel_available = True
except ImportError:
    get_angel_service = None
    SYMBOL_TOKENS = {}
    ANGEL_INDEX_TOKENS = {}
    logger.warning("Angel One service not available, using simulated data")

try:
    from brokers import BROKER_REGISTRY, get_broker, list_brokers, session_manager
    brokers_available = True
except ImportError:
    logger.warning("Brokers module not available")

try:
    from option_chain_service import get_option_chain_service
    oc_available = True
except ImportError:
    logger.warning("Option chain service not available")

try:
    from iv_analytics_service import (
        calculate_iv, calculate_historical_volatility, calculate_iv_rank,
        calculate_iv_percentile, calculate_max_pain, build_iv_skew,
        get_atm_iv, detect_iv_signal, INDIA_VIX_TOKEN, INDIA_VIX_EXCHANGE,
    )
    iv_available = True
except ImportError:
    logger.warning("IV analytics service not available")

set_service_flags(
    angel_one=angel_available,
    brokers=brokers_available,
    option_chain=oc_available,
    iv_analytics=iv_available,
)

setup_market_data_service(
    angel_available=angel_available,
    get_angel_service_fn=get_angel_service if angel_available else None,
    symbol_tokens=SYMBOL_TOKENS,
    index_tokens=ANGEL_INDEX_TOKENS,
)
setup_arbitrage_service(
    angel_available=angel_available,
    get_angel_service_fn=get_angel_service if angel_available else None,
)

# ── Include routers ──

@api_router.get("/")
async def root():
    return {"message": "Indian Markets Arbitrage Platform API", "version": "1.0.0"}

@api_router.get("/health")
async def health():
    from datetime import datetime, timezone
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}

api_router.include_router(market_router.router)
api_router.include_router(brokers_router.router)
api_router.include_router(arbitrage_router.router)
api_router.include_router(options_router.router)
api_router.include_router(iv_router.router)
api_router.include_router(analytics_router.router)
api_router.include_router(risk_router.router)
api_router.include_router(backtest_router.router)
api_router.include_router(correlation_router.router)

# ── Middleware ──

app.include_router(api_router)

# CORS middleware must be the outermost layer so it wraps everything
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSHeadersMiddleware)  # outermost — wraps everything, runs first/last


# ── Startup ──

@app.on_event("startup")
async def startup_event():
    if angel_available:
        logger.info("Angel One ready in publisher-login mode")
    if brokers_available:
        try:
            from brokers import system_session as _ss
            if _ss.is_enabled():
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, _ss.login_now)
                _ss.start_background_refresher()
        except Exception as e:
            logger.warning("System auto-login bootstrap failed: %s", e)

    # ── Pre-warm NSE price cache in background — server starts immediately ──
    async def _warm_cache():
        try:
            from services.correlation_service import correlation_service
            import time
            logger.info("Pre-warming NSE price cache (20-day) in background...")
            t0 = time.time()
            await asyncio.wait_for(
                correlation_service.fetch_all_prices(20),
                timeout=300,
            )
            elapsed = time.time() - t0
            logger.info("Price cache warmed in %.1fs — first load will be instant", elapsed)
        except Exception as e:
            logger.warning("Price cache pre-warm failed (%s) — will lazy-load on first request", e)

    asyncio.create_task(_warm_cache())

@app.on_event("shutdown")
async def shutdown_event():
    if brokers_available:
        try:
            from brokers import system_session as _ss
            _ss.stop_background_refresher()
        except Exception:
            pass

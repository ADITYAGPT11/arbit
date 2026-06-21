"""Broker connection routes — publisher-login flow. No auth required.

Since there's no user auth, broker sessions use a fixed default user_id ("default_user").
All browser tabs share the same in-memory broker session for now.
"""

import logging
import uuid
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from urllib.parse import urlencode

from core.deps import is_brokers_available

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brokers", tags=["Brokers"])

# Default user ID for all sessions (no auth mode)
DEFAULT_USER_ID = "default_user"

try:
    from brokers import get_broker as _get_broker_provider, list_brokers as _list_brokers
    from brokers import session_manager as broker_session_manager
except ImportError:
    _get_broker_provider = None
    _list_brokers = None
    broker_session_manager = None
    logger.warning("Brokers module not available")


@router.get("/list")
async def brokers_list():
    """List all brokers in the registry with their static info."""
    if not is_brokers_available():
        return {"brokers": [], "available": False}

    items = []
    for info in _list_brokers():
        item = dict(info)
        item["is_connected"] = False
        item["connected_at"] = None
        item["expires_at"] = None
        item["profile"] = None
        sess = broker_session_manager.get(DEFAULT_USER_ID, info["broker_id"])
        if sess:
            pub = sess.to_public_dict()
            item["is_connected"] = pub["is_connected"]
            item["connected_at"] = pub["connected_at"]
            item["expires_at"] = pub["expires_at"]
            item["profile"] = pub["profile"]
        items.append(item)
    return {"available": True, "brokers": items}


@router.post("/{broker_id}/connect")
async def broker_connect(broker_id: str):
    """Begin a broker connection. Returns the broker's publisher-login URL."""
    if not is_brokers_available():
        raise HTTPException(status_code=400, detail="Brokers module not available")

    try:
        broker = _get_broker_provider(broker_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown broker: {broker_id}")

    if broker.coming_soon or not broker.enabled:
        raise HTTPException(status_code=400, detail=f"{broker.display_name} integration is coming soon")

    if not broker.is_platform_configured():
        raise HTTPException(
            status_code=503,
            detail=f"{broker.display_name} is not yet configured on this server. The ARBIT administrator must set the platform API key.",
        )

    state = broker_session_manager.create_state(DEFAULT_USER_ID, broker_id)
    try:
        login_url = broker.build_login_url(state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build login URL: {e}")

    resp = JSONResponse({
        "broker_id": broker_id,
        "display_name": broker.display_name,
        "login_url": login_url,
        "state": state,
        "expires_in_seconds": int(broker_session_manager.STATE_TTL.total_seconds()),
    })
    resp.set_cookie(
        key=f"broker_state_{broker_id}",
        value=state,
        max_age=int(broker_session_manager.STATE_TTL.total_seconds()),
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )
    return resp


@router.get("/{broker_id}/callback")
async def broker_callback(broker_id: str, request: Request):
    """Public redirect-callback endpoint that the broker hits after user login."""
    if not is_brokers_available():
        raise HTTPException(status_code=400, detail="Brokers module not available")

    logger.info("Broker callback hit: broker=%s query_params=%s", broker_id, dict(request.query_params))
    params = dict(request.query_params)
    state = params.get("state", "") or request.cookies.get(f"broker_state_{broker_id}", "")

    def _front_redirect(status: str, message: str = "", broker: str = broker_id):
        qs = urlencode({"status": status, "broker": broker, "message": message[:300]})
        r = RedirectResponse(url=f"/connect-broker?{qs}", status_code=302)
        r.delete_cookie(f"broker_state_{broker}", path="/")
        return r

    if not state:
        return _front_redirect("error", "Missing state token. Please retry the connect from the same browser tab.")

    mapped = broker_session_manager.consume_state(state)
    if not mapped:
        return _front_redirect("error", "State token expired or invalid. Please try again.")

    user_id, mapped_broker_id = mapped
    if mapped_broker_id != broker_id:
        return _front_redirect("error", "Broker mismatch on callback")

    try:
        broker = _get_broker_provider(broker_id)
    except KeyError:
        return _front_redirect("error", f"Unknown broker: {broker_id}")

    try:
        session = broker.handle_callback(params)
        session.user_id = user_id
        broker_session_manager.set(session)
    except Exception as e:
        logger.exception("Broker callback failed for %s", broker_id)
        return _front_redirect("error", str(e))

    return _front_redirect("success", "Connected successfully")


@router.get("/sessions")
async def broker_sessions():
    """List all active broker sessions."""
    if not is_brokers_available():
        return {"sessions": []}
    sessions = broker_session_manager.list_for_user(DEFAULT_USER_ID)
    return {"sessions": [s.to_public_dict() for s in sessions]}


@router.post("/{broker_id}/disconnect")
async def broker_disconnect(broker_id: str):
    """Disconnect a broker."""
    if not is_brokers_available():
        raise HTTPException(status_code=400, detail="Brokers module not available")

    try:
        broker = _get_broker_provider(broker_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown broker: {broker_id}")

    sess = broker_session_manager.get(DEFAULT_USER_ID, broker_id)
    if sess:
        try:
            broker.disconnect(sess)
        except Exception:
            pass
        broker_session_manager.delete(DEFAULT_USER_ID, broker_id)
    return {"status": "ok", "message": f"Disconnected from {broker.display_name}"}

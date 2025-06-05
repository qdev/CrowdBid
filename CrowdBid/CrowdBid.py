from datetime import datetime

import reflex as rx
from fastapi import FastAPI

from CrowdBid.auction_create import create_auction_ui
from CrowdBid.auction_edit import edit_page_ui
from CrowdBid.auction_list import list_auction_ui
from CrowdBid.bid import bid_ui
from CrowdBid.bid_data import data_bid_ui
from sqlmodel import select
import websockets
from CrowdBid.models import Auction, Bid

clients = set()


async def ws_handler(websocket):
    clients.add(websocket)
    try:
        async for message in websocket:
            # Broadcast an alle Clients (außer dem Sender)
            for client in clients.copy():
                if client != websocket:
                    try:
                        await client.send(message)
                    except websockets.exceptions.ConnectionClosed:
                        clients.remove(client)
    finally:
        clients.remove(websocket)


async def deploy_ws():
    server = await websockets.serve(
        ws_handler,
        "127.0.0.1",  # Nur lokale Verbindungen
        28765,  # Port für WebSocket
        ping_interval=None,  # Deaktiviert automatische Pings
        ping_timeout=None  # Deaktiviert Ping-Timeouts
    )
    await server.wait_closed()


@rx.page(route="/404")
def not_found():
    return rx.vstack(
        rx.heading("404 - Nicht gefunden"),
        rx.text("Die angeforderte Auktion wurde nicht gefunden."),
        rx.link("Zurück zur Startseite", href="/"),
        padding="2em",
        spacing="4",
    )
app = rx.App()

@app.api.get("/maintenance")
def maintenance():
    """Entfernt abgelaufene Auktionen und deren Gebote."""
    current_time = datetime.now()
    with rx.session() as session:  # Synchrone Session
        expired_auctions = session.exec(
            select(Auction).where(Auction.expiration < current_time)
        ).all()
        for auction in expired_auctions:
            bids = session.exec(select(Bid).where(Bid.ida == auction.id)).all()
            for bid in bids:
                session.delete(bid)
            session.delete(auction)
        session.commit()
    return {"status": "OK", "cleaned_auctions": len(expired_auctions)}


app.register_lifespan_task(deploy_ws)
app.add_page(create_auction_ui, route="/")
app.add_page(list_auction_ui, route="/list")
app.add_page(edit_page_ui)
app.add_page(data_bid_ui)
app.add_page(bid_ui)

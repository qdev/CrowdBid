import reflex as rx
from CrowdBid.auction_create import create_auction_ui
from CrowdBid.auction_edit import edit_page_ui
from CrowdBid.auction_list import list_auction_ui
from CrowdBid.bid import bid_ui
from CrowdBid.bid_data import data_bid_ui
import asyncio
import websockets
from CrowdBid.test import namenliste


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
    async with websockets.serve(ws_handler, "localhost", 28765):
        await asyncio.Future()  # run forever


@rx.page(route="/404")
def not_found():
    return rx.vstack(
        rx.heading("404 - Nicht gefunden"),
        rx.text("Die angeforderte Auktion wurde nicht gefunden."),
        rx.link("Zurück zur Startseite", href="/"),
        padding="2em",
        spacing="4",
    )

# App-Konfiguration
app = rx.App()
app.register_lifespan_task(deploy_ws)
app.add_page(create_auction_ui, route="/")
app.add_page(list_auction_ui, route="/list")
app.add_page(namenliste, route="/test")
app.add_page(edit_page_ui)
app.add_page(data_bid_ui)
app.add_page(bid_ui)

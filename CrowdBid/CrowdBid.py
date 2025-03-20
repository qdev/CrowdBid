import reflex as rx
from CrowdBid.auction_create import create_auction_ui
from CrowdBid.auction_edit import edit_page_ui
from CrowdBid.auction_list import list_auction_ui
from CrowdBid.bid import bid_ui
from CrowdBid.bid_data import data_bid_ui

# App-Konfiguration
app = rx.App()
app.add_page(create_auction_ui, route="/")
app.add_page(list_auction_ui, route="/list")
app.add_page(edit_page_ui)
app.add_page(data_bid_ui)
app.add_page(bid_ui)
from datetime import datetime, timedelta
import reflex as rx
import sqlmodel
import secrets
from sqlmodel import select

from CrowdBid.models import Auction

### BACKEND ###
class EditAuctionState(rx.State):
    """Status für die Bearbeitungsseite."""
    auction: Auction = None

    @rx.var
    def current_auction_token(self) -> str:
        return self.router.page.params.get("token", "")

    def get_auction(self):
        with rx.session() as session:
            self.auction = session.exec(
                select(Auction).where(Auction.config_token == self.current_auction_token)
            ).first()

    def update_auction(self, form_data: dict):
        with rx.session() as session:
            auction = session.exec(
                select(Auction).where(Auction.id == self.auction.id)
            ).first()

            auction.topic = form_data.get("topic", auction.topic)
            auction.description = form_data.get("description", auction.description)
            auction.target_bid = float(form_data.get("target_bid", auction.target_bid))
            auction.update_at = datetime.now()

            session.add(auction)
            session.commit()

        return rx.window_alert("Auktion wurde aktualisiert")


### FRONTEND ###

@rx.page(route="/[token]/edit")
def edit_page_ui():
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.input(
                    placeholder="Thema",
                    name="topic",
                    value=rx.cond(
                        EditAuctionState.auction,
                        EditAuctionState.auction.topic,
                        ""
                    ),
                ),
                rx.text_area(
                    placeholder="Beschreibung",
                    name="description",
                    value=rx.cond(
                        EditAuctionState.auction,
                        EditAuctionState.auction.description,
                        ""
                    ),
                ),
                rx.input(
                    placeholder="Zielgebot",
                    type_="number",
                    name="target_bid",
                    value=rx.cond(
                        EditAuctionState.auction,
                        EditAuctionState.auction.target_bid,
                        0
                    ),
                ),
                rx.button("Aktualisieren", type_="submit")
            ),
            on_submit=EditAuctionState.update_auction,
        ),
        on_mount=EditAuctionState.get_auction,
    )

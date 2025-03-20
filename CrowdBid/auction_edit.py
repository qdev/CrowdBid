from datetime import datetime, timedelta
import reflex as rx
import sqlmodel
import secrets

from jeepney.low_level import padding
from sqlmodel import select

from CrowdBid.components import header
from CrowdBid.models import Auction


### BACKEND ###
class EditAuctionState(rx.State):
    """Status für die Bearbeitungsseite."""
    auction: Auction = None
    bid_url: str
    edit_url: str

    @rx.var
    def current_auction_token(self) -> str:
        return self.router.page.params.get("token", "")

    def get_auction(self):
        with rx.session() as session:
            self.auction = session.exec(
                select(Auction).where(Auction.config_token == self.current_auction_token)
            ).first()
            if self.auction is not None:
                self.edit_url=f"{self.router.page.host}/{self.auction.config_token}/edit"
                self.bid_url=f"{self.router.page.host}/{self.auction.token}/bid"
            else:
                return rx.redirect("/")
                

    def update_auction(self, form_data: dict):
        with rx.session() as session:
            auction = session.exec(
                select(Auction).where(Auction.id == self.auction.id)
            ).first()

            auction.topic = form_data.get("topic", auction.topic)
            auction.description = form_data.get("description", auction.description)
            auction.target_bid = float(form_data.get("target_bid", auction.target_bid))
            auction.expiration = datetime.strptime(form_data.get("expiration",auction.expiration.strftime("%Y-%m-%d")), "%Y-%m-%d")
            auction.update_at = datetime.now()


            session.add(auction)
            session.commit()
        return rx.window_alert("Auktion wurde aktualisiert")

    def delete_auction(self):
        with rx.session() as session:
            auction = session.exec(
                select(Auction).where(Auction.id == self.auction.id)
            ).first()
            session.delete(auction)
            session.commit()
        return rx.redirect("/")


    @rx.var
    def expiration_str(self) -> str:
        return self.auction.expiration.strftime("%Y-%m-%d")

### FRONTEND ###

@rx.page(route="/[token]/edit")
def edit_page_ui():
    return rx.vstack(
        header(),
        rx.form(
            rx.vstack(
                rx.input(
                    placeholder="Thema",
                    name="topic",
                    default_value=EditAuctionState.auction.topic,
                ),
                rx.text_area(
                    placeholder="Beschreibung",
                    name="description",
                    default_value=EditAuctionState.auction.description
                ),
                rx.input(
                    placeholder="Zielgebot",
                    type_="number",
                    name="target_bid",
                    default_value=EditAuctionState.auction.target_bid.to_string()
                ),
                rx.input(
                    placeholder="Delete On",
                    name="expiration",
                    default_value=EditAuctionState.expiration_str,
                    type="date",
                ),
                rx.button("Aktualisieren", type_="submit")
            ),
            on_submit=EditAuctionState.update_auction,
        ),
        rx.hstack(
            rx.text("BidLink:"),
            rx.box(
                rx.link(EditAuctionState.bid_url,
                        href=EditAuctionState.bid_url,
                        color=rx.color_mode_cond(light="black", dark="white"),
                        font_size="0.9em"),
                background_color="var(--gray-6)",
                border_radius="10px",
                padding_x="10px",
                padding_y="5px", ),
            rx.button(rx.icon("copy"), on_click=rx.set_clipboard(EditAuctionState.bid_url)),
                      spacing="3"
                      ),
            rx.hstack(
                rx.text("EditLink:"),
                rx.box(
                    rx.link(EditAuctionState.edit_url,
                            href=EditAuctionState.edit_url,
                            color=rx.color_mode_cond(light="black", dark="white"),
                            font_size="0.9em"),
                    background_color="var(--gray-6)",
                    border_radius="10px",
                    padding_x="10px",
                    padding_y="5px", ),
                rx.button(rx.icon("copy"), on_click=rx.set_clipboard(EditAuctionState.edit_url)),
                spacing="3"
            ),
            rx.alert_dialog.root(
                rx.alert_dialog.trigger(
                    rx.button("Löschen", color_scheme="red"),
                ),
                rx.alert_dialog.content(
                    rx.alert_dialog.title("Auktion löschen"),
                    rx.alert_dialog.description(
                        "Sind Sie sicher, dass Sie diese Auktion löschen möchten?",
                    ),
                    rx.flex(
                        rx.alert_dialog.cancel(
                            rx.button("Abbrechen"),
                        ),
                        rx.alert_dialog.action(
                            rx.button(
                                "Ja, löschen",
                                color_scheme="red",
                                on_click=EditAuctionState.delete_auction,
                            ),
                        ),
                        spacing="3",
                        margin_top="16px",
                        justify="end",
                    ),
                ),
            ),
            spacing="7",
            on_mount=EditAuctionState.get_auction,
            padding="0.7rem"
        )

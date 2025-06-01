from datetime import datetime, timedelta
import reflex as rx
import sqlmodel
import secrets
from sqlmodel import select

from CrowdBid.components import header
from CrowdBid.models import Auction


### BACKEND ###

class CreateAuctionState(rx.State):
    """Der App-Status."""
    in_90_days :str = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
    is_form_valid: bool = False
    topic: str = ""
    target_bid: str = ""

    def validate_form(self):
        """Überprüft die Formulareingaben."""
        try:
            self.is_form_valid = bool(self.topic.strip()) and float(self.target_bid) > 0
        except ValueError:
            self.is_form_valid = False
            
    @rx.event
    def handle_topic_change(self, value: str):
        """Behandelt Änderungen am Thema."""
        self.topic = value
        self.validate_form()

    @rx.event
    def handle_target_bid_change(self, value: str):
        """Behandelt Änderungen am Zielgebot."""
        self.target_bid = value
        self.validate_form()

    @rx.event
    def create_auction(self, form_data: dict):
        """Erstellt eine neue Auktion."""
        token = secrets.token_hex(8)
        config_token = secrets.token_hex(8)
        now = datetime.now()
        auction_data = {
            "token": token,
            "config_token": config_token,
            "create_at": now,
            "update_at": now,
            "expiration": datetime.strptime(form_data.get("expiration"), "%Y-%m-%d"),
            "topic": form_data.get("topic"),
            "description": form_data.get("description"),
            "target_bid": float(form_data.get("target_bid", 0))
        }

        with rx.session() as session:

            new_auction = Auction(**auction_data)
            session.add(new_auction)
            session.commit()
            session.refresh(new_auction)

        return rx.redirect(f"/{config_token}/edit")

    @rx.event
    def on_mount(self):
        """Reset form fields when the component mounts."""
        self.topic = ""
        self.target_bid = ""
        self.is_form_valid = False


### FRONTEND ###

def create_auction_ui():
    """Formular zum Erstellen einer Auktion."""
    return rx.vstack(
        header(),
        rx.card(
            rx.form(
                rx.vstack(
                    rx.heading("Neue Auktion erstellen", size="6"),
                    rx.divider(),
                    rx.flex(
                        rx.vstack(
                            rx.text.strong("Thema"),
                            rx.input(
                                placeholder=f"z.B. Mietversteigerung 1992",
                                name="topic",
                                required=True,
                                size="3",
                                width="100%",
                                value=CreateAuctionState.topic,
                                on_change=CreateAuctionState.handle_topic_change,
                            ),
                            align_items="start",
                            width="100%"
                        ),
                        direction="column",
                        width="100%"
                    ),
                    rx.flex(
                        rx.vstack(
                            rx.text.strong("Beschreibung"),
                            rx.text_area(
                                placeholder="Beschreibe Deine Auktion...",
                                name="description",
                                min_height="150px",
                                width="100%"
                            ),
                            align_items="start",
                            width="100%"
                        ),
                        direction="column",
                        width="100%"
                    ),
                    rx.hstack(
                        rx.vstack(
                            rx.text.strong("Zielgebot (€)"),
                            rx.input(
                                placeholder="0.00",
                                type_="number",
                                name="target_bid",
                                required=True,
                                size="3",
                                value=CreateAuctionState.target_bid,
                                on_change=CreateAuctionState.handle_target_bid_change,
                            ),
                            align_items="start",
                        ),
                        rx.vstack(
                            rx.text.strong("Ablaufdatum"),
                            rx.input(
                                name="expiration",
                                default_value=CreateAuctionState.in_90_days,
                                type="date",
                                size="3"
                            ),
                            align_items="start",
                        ),
                        spacing="8",
                        width="100%"
                    ),
                    rx.cond(
                        CreateAuctionState.is_form_valid,
                        rx.button(
                            "Auktion erstellen",
                            type_="submit",
                            width="100%",
                            size="3",
                            color_scheme="grass",
                        ),
                        rx.button(
                            "Auktion erstellen",
                            type_="submit",
                            width="100%",
                            size="3",
                            color_scheme="gray",
                            is_disabled=True,
                        ),
                    ),
                    spacing="6",
                    width="100%",
                ),
                on_submit=CreateAuctionState.create_auction,
                reset_on_submit=True,
                width="100%",
            ),
            width="100%",
            max_width="600px",
            padding="6",
        ),
        rx.el.hr(width="100%"),
        spacing="8",
        padding="2em",
        align_items="center",
        width="100%",
        on_mount=CreateAuctionState.on_mount,  # Add this line
    )

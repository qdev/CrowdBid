from datetime import datetime, timedelta
import reflex as rx
import sqlmodel
import secrets
from sqlmodel import select

from CrowdBid.models import Auction


### BACKEND ###

class CreateAuctionState(rx.State):
    """Der App-Status."""

    def create_auction(self, form_data: dict):
        """Erstellt eine neue Auktion."""
        token = secrets.token_hex(8)
        config_token = secrets.token_hex(8)

        # Zeitstempel setzen
        now = datetime.now()

        # Auktion erstellen
        auction_data = {
            "token": token,
            "config_token": config_token,
            "create_at": now,
            "update_at": now,
            "delete_on": now + timedelta(days=90),
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


### FRONTEND ###

def create_auction_ui():
    """Formular zum Erstellen einer Auktion."""
    return rx.vstack(
        rx.form(
            rx.vstack(
                rx.input(
                    placeholder="Thema",
                    name="topic",
                    required=True
                ),
                rx.text_area(
                    placeholder="Beschreibung",
                    name="description"
                ),
                rx.input(
                    placeholder="Zielgebot",
                    type_="number",
                    name="target_bid",
                    required=True
                ),
                rx.button("Erstellen", type_="submit")
            ),
            on_submit=CreateAuctionState.create_auction,
            reset_on_submit=True,
        ),
        spacing="4",
    )
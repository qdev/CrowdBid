from datetime import datetime, timedelta
import reflex as rx
import sqlmodel
import secrets

from jeepney.low_level import padding
from sqlmodel import select

from CrowdBid.components import header
from CrowdBid.models import Auction, Bid


### BACKEND ###
# Im State fügen wir zwei neue Methoden hinzu:
class EditAuctionState(rx.State):
    """Status für die Bearbeitungsseite."""
    auction: Auction = None
    bid_url: str
    edit_url: str
    is_form_valid: bool = False
    topic: str = ""
    target_bid: str = ""
    round_end_mode: str = "auto"
    peek: bool = True  # Neue State-Variable

    @rx.event
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
        self.target_bid = value
        self.validate_form()

    @rx.event
    def handle_round_end_mode_change(self, value: str):
        self.round_end_mode = value
        self.validate_form()

    @rx.event
    def handle_peek_change(self, value: bool):
        """Behandelt Änderungen an der Peek-Option."""
        self.peek = value
        self.validate_form()

    @rx.var
    def current_auction_token(self) -> str:
        return self.router.page.params.get("token", "")

    def get_auction(self):
        with rx.session() as session:
            self.auction = session.exec(
                select(Auction).where(Auction.config_token == self.current_auction_token)
            ).first()
            if self.auction is not None:
                self.edit_url = f"{self.router.page.host}/{self.auction.config_token}/edit"
                self.bid_url = f"{self.router.page.host}/{self.auction.token}/bid"
                # Initialisiere die Formularfelder mit den aktuellen Werten
                self.topic = self.auction.topic
                self.target_bid = str(self.auction.target_bid)
                self.round_end_mode = self.auction.round_end_mode or "auto"
                self.peek = self.auction.peek or True  # Lade peek-Wert
                # self.validate_form()
            else:
                return rx.redirect("/")

    def update_auction(self, form_data: dict):
        with rx.session() as session:
            auction = session.exec(select(Auction).where(Auction.id == self.auction.id)).first()

            auction.topic = form_data.get("topic", auction.topic)
            auction.description = form_data.get("description", auction.description)
            auction.target_bid = float(form_data.get("target_bid", auction.target_bid))
            auction.expiration = datetime.strptime(form_data.get("expiration", auction.expiration.strftime("%Y-%m-%d")), "%Y-%m-%d")
            auction.update_at = datetime.now()
            auction.round_end_mode = self.round_end_mode
            auction.peek = self.peek  # Speichere peek-Wert
            session.add(auction)
            session.commit()
            self.is_form_valid = False

    def delete_auction(self):
        with rx.session() as session:
            for bid in session.exec(select(Bid).where(Bid.ida == self.auction.id)).all():
                session.delete(bid)
            auction = session.exec(select(Auction).where(Auction.id == self.auction.id)).first()
            session.delete(auction)
            session.commit()
        return rx.redirect("/")

    def copy_bid_url(self):
        """Kopiert die Bid URL und zeigt eine Toast-Benachrichtigung."""
        return [
            rx.set_clipboard(self.bid_url),
            rx.toast.success(
                "Bieten-Link wurde in die Zwischenablage kopiert",
                title="Kopiert!",
            ),
        ]

    def copy_edit_url(self):
        """Kopiert die Edit URL und zeigt eine Toast-Benachrichtigung."""
        return [
            rx.set_clipboard(self.edit_url),
            rx.toast.success(
                "Bearbeiten-Link wurde in die Zwischenablage kopiert",
                title="Kopiert!",
            ),
        ]

    @rx.var
    def expiration_str(self) -> str:
        return self.auction.expiration.strftime("%Y-%m-%d") if self.auction and self.auction.expiration else ""


### FRONTEND ###
@rx.page(route="/[token]/edit")
def edit_page_ui():
    return rx.vstack(
        header(),

        # Links Card
        rx.card(
            rx.vstack(
                rx.heading("Auktions Links", size="6", weight="medium"),
                "Bitte Kopieren!",
                rx.divider(),
                # Bid Link
                rx.vstack(
                    rx.text.strong("Link zum Teilen mit den Bietenden:"),
                    rx.hstack(
                        rx.box(
                            rx.link(
                                EditAuctionState.bid_url,
                                href=EditAuctionState.bid_url,
                                color=rx.color_mode_cond(light="black", dark="white"),
                                font_size="0.9em",
                                target="_blank"
                            ),
                            background_color="var(--gray-6)",
                            border_radius="10px",
                            padding_x="10px",
                            padding_y="5px",
                            width="100%"
                        ),
                        # Für den Bid URL Button:
                        rx.button(
                            rx.icon("copy"),
                            on_click=EditAuctionState.copy_bid_url,
                            variant="outline",
                            size="2"
                        ),
                        width="100%"
                    ),
                    width="100%",
                    align_items="start"
                ),
                # Edit Link
                rx.vstack(
                    rx.text.strong("Link (dies Seite) zum Bearbeiten der Auktion:"),
                    rx.hstack(
                        rx.box(
                            rx.link(
                                EditAuctionState.edit_url,
                                href=EditAuctionState.edit_url,
                                color=rx.color_mode_cond(light="black", dark="white"),
                                font_size="0.9em"
                            ),
                            background_color="var(--gray-6)",
                            border_radius="10px",
                            padding_x="10px",
                            padding_y="5px",
                            width="100%"
                        ),
                        # Für den Edit URL Button:
                        rx.button(
                            rx.icon("copy"),
                            on_click=EditAuctionState.copy_edit_url,
                            variant="outline",
                            size="2"
                        ),
                        width="100%"
                    ),
                    width="100%",
                    align_items="start"
                ),
                spacing="4",
                width="100%",
            ),
            width="100%",
            max_width="600px",
            padding="6",
        ),

        # Main Form Card
        rx.card(
            rx.form(
                rx.vstack(
                    rx.heading("Auktion bearbeiten", size="6", weight="medium"),
                    rx.divider(),
                    rx.flex(
                        rx.vstack(
                            rx.text.strong("Thema"),
                            rx.input(
                                placeholder="Thema der Auktion",
                                name="topic",
                                value=EditAuctionState.topic,
                                on_change=EditAuctionState.handle_topic_change,
                                size="3",
                                width="100%"
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
                                placeholder="Beschreibung der Auktion",
                                name="description",
                                default_value=EditAuctionState.auction.description,
                                on_change=EditAuctionState.validate_form,
                                min_height="150px",
                                width="100%"
                            ),
                            align_items="start",
                            width="100%"
                        ),
                        direction="column",
                        width="100%"
                    ),
                    rx.flex(
                        rx.vstack(
                            rx.text.strong("Rundenende"),
                            rx.radio_group.root(
                                rx.text(
                                    rx.flex(
                                        rx.radio_group.item(value="auto"),
                                        "Automatisches Rundende mit letztem Gebot",
                                        spacing="2"
                                    ),
                                    as_="label"
                                ),
                                rx.text(
                                    rx.flex(
                                        rx.radio_group.item(value="manual_last"),
                                        "Manuelles Beenden nach dem letzten Gebot",
                                        spacing="2"
                                    ),
                                    as_="label"
                                ),
                                rx.text(
                                    rx.flex(
                                        rx.radio_group.item(value="manual_first"),
                                        "Manuelles Beenden nach Rundenstart",
                                        spacing="2"
                                    ),
                                    as_="label"
                                ),
                                name="round_end_mode",
                                value=EditAuctionState.round_end_mode,
                                on_change=EditAuctionState.handle_round_end_mode_change,
                                direction="column",
                                spacing="3",
                                size="3"
                            ),
                            align_items="start",
                            width="100%"
                        ),
                        direction="column",
                        width="100%"
                    ),
                    rx.flex(
                        rx.vstack(
                            rx.text.strong("Optionen"),
                            rx.checkbox(
                                "Gebote während der Runde sichtbar (Peek)",
                                checked=EditAuctionState.peek,
                                on_change=EditAuctionState.handle_peek_change,
                                name="peek",
                                size="3"
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
                                value=EditAuctionState.target_bid,
                                on_change=EditAuctionState.handle_target_bid_change,
                                size="3"
                            ),
                            align_items="start",
                        ),
                        rx.vstack(
                            rx.text.strong("Ablaufdatum"),
                            rx.input(
                                name="expiration",
                                default_value=EditAuctionState.expiration_str,
                                on_change=EditAuctionState.validate_form,
                                type="date",
                                size="3"
                            ),
                            align_items="start",
                        ),
                        spacing="8",
                        width="100%"
                    ),
                    rx.cond(
                        EditAuctionState.is_form_valid,
                        rx.button(
                            "Aktualisieren",
                            type_="submit",
                            width="100%",
                            size="3",
                            color_scheme="grass",
                        ),
                        rx.button(
                            "Aktualisieren",
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
                on_submit=EditAuctionState.update_auction,
                width="100%",
            ),
            width="100%",
            max_width="600px",
            padding="6",
        ),

        # Delete Card
        rx.card(
            rx.vstack(
                rx.heading(""),
                rx.divider(),
                rx.alert_dialog.root(
                    rx.alert_dialog.trigger(
                        rx.button(
                            "Auktion löschen",
                            color_scheme="red",
                            variant="outline",
                            size="3",
                            width="100%"
                        ),
                    ),
                    rx.alert_dialog.content(
                        rx.alert_dialog.title("Auktion löschen"),
                        rx.alert_dialog.description(
                            "Sind Sie sicher, dass Sie diese Auktion löschen möchten?",
                        ),
                        rx.flex(
                            rx.alert_dialog.cancel(
                                rx.button(
                                    "Abbrechen",
                                    variant="soft",
                                    size="2"
                                ),
                            ),
                            rx.alert_dialog.action(
                                rx.button(
                                    "Ja, löschen",
                                    color_scheme="red",
                                    size="2",
                                    on_click=EditAuctionState.delete_auction,
                                ),
                            ),
                            spacing="3",
                            margin_top="16px",
                            justify="end",
                        ),
                    ),
                ),
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
        on_mount=EditAuctionState.get_auction,
    )
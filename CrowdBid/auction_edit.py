from datetime import datetime, timedelta
import reflex as rx
import sqlmodel
import secrets
import io
import csv

from jeepney.low_level import padding
from sqlmodel import select, func

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
    import_error: str = ""  # Für Fehlermeldungen beim Import

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
                self.round_end_mode = self.auction.round_end_mode
                self.peek = self.auction.peek # Lade peek-Wert
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

    def export_result_csv(self):
        """Exportiert das Ergemiss der Auktion als CSV-Datei."""
        with rx.session() as session:
            subq = select(Bid.name, func.max(Bid.round).label("max_round")).where(Bid.ida == self.auction.id).group_by(Bid.name).subquery()
            bids = session.exec(select(Bid).join(subq, (Bid.name == subq.c.name) & (Bid.round == subq.c.max_round)).where(Bid.ida == self.auction.id)).all()
            csv_content = ""
            for bid in bids:
                csv_content += f"{bid.name};{bid.bid}\n"

            return rx.download(
                data=csv_content,
                filename=f"auktionsergebnis_{self.auction.topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            )

    def export_csv(self):
        """Exportiert die Auktionsdaten als CSV-Datei."""
        with rx.session() as session:
            # Alle Gebote für diese Auktion holen
            bids = session.exec(
                select(Bid).where(Bid.ida == self.auction.id).order_by(Bid.name, Bid.round)
            ).all()

            # Daten nach Namen gruppieren
            bid_data = {}
            for bid in bids:
                if bid.name not in bid_data:
                    bid_data[bid.name] = []
                if bid.round > 0:
                    while len(bid_data[bid.name]) < bid.round - 1:
                        bid_data[bid.name].append("")
                    bid_data[bid.name].append(f"{bid.bid}")

            # CSV-Daten erstellen
            csv_content = ""
            for name, bids_list in bid_data.items():
                csv_content += f"{name};{';'.join(bids_list)}\n"

            # CSV-Datei zum Download anbieten
            filename = f"auktion_{self.auction.topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

            return rx.download(
                data=csv_content,
                filename=filename
            )

    async def handle_file_upload(self, files: list[rx.UploadFile]):
        for file in files:
            print(file.name)
            try:
                # Datei lesen
                content = await file.read()
                csv_text = content.decode('utf-8')

                # CSV parsen
                imported_data = []
                for line in csv_text.strip().split('\n'):
                    if line.strip():
                        parts = line.split(';')
                        if len(parts) >= 2:  # Mindestens Name und ein Gebot
                            name = parts[0].strip()
                            bids = []
                            for i, bid_str in enumerate(parts[1:], 1):
                                if bid_str.strip():  # Nur nicht-leere Gebote
                                    try:
                                        bid_value = float(bid_str.strip())
                                        bids.append((i, bid_value))
                                    except ValueError:
                                        continue
                            if bids:  # Nur wenn mindestens ein Gebot vorhanden ist
                                imported_data.append((name, bids))

                if not imported_data:
                    self.import_error = "Keine gültigen Daten in der CSV-Datei gefunden"
                    return

                # Alle vorhandenen Gebote löschen und neue erstellen
                with rx.session() as session:
                    # Alle Gebote für diese Auktion löschen
                    existing_bids = session.exec(select(Bid).where(Bid.ida == self.auction.id)).all()
                    for bid in existing_bids:
                        session.delete(bid)

                    # Neue Gebote erstellen
                    current_time = datetime.now()
                    for name, bids in imported_data:
                        # Dummy-Eintrag für Runde 0 (zum Hinzufügen des Bieters)
                        session.add(Bid(
                            name=name,
                            round=0,
                            bid=0,
                            ida=self.auction.id,
                            time=current_time
                        ))

                        # Echte Gebote
                        for round_num, bid_value in bids:
                            session.add(Bid(
                                name=name,
                                round=round_num,
                                bid=bid_value,
                                ida=self.auction.id,
                                time=current_time
                            ))

                    session.commit()

                return rx.toast.success(
                    f"CSV-Datei erfolgreich importiert! {len(imported_data)} Bieter wurden importiert.",
                    title="Import erfolgreich",
                )
            except Exception as e:
                self.import_error = f"Fehler beim Importieren: {str(e)}"
                return rx.toast.error(
                    "Fehler beim Importieren der CSV-Datei",
                    title="Import fehlgeschlagen",
                )

    async def import_csv(self, form_data: dict):
        """Importiert Auktionsdaten aus einer CSV-Datei."""
        self.import_error = ""

        csv_file = form_data.get("csv_file", None)
        if not csv_file:
            self.import_error = "Bitte wählen Sie eine CSV-Datei aus."
            return

        try:
            # CSV-Datei lesen und verarbeiten
            csv_text = csv_file.decode("utf-8")
            csv_data = csv.reader(io.StringIO(csv_text), delimiter=";")

            imported_data = []
            for row in csv_data:
                if row:
                    name = row[0].strip()
                    bids = []
                    for i, bid_str in enumerate(row[1:], 1):
                        try:
                            bid_value = float(bid_str.strip())
                            bids.append((i, bid_value))
                        except ValueError:
                            pass
                    imported_data.append((name, bids))

            with rx.session() as session:
                # Alle Gebote für diese Auktion löschen
                existing_bids = session.exec(select(Bid).where(Bid.ida == self.auction.id)).all()
                for bid in existing_bids:
                    session.delete(bid)

                # Neue Gebote erstellen
                current_time = datetime.now()
                for name, bids in imported_data:
                    # Dummy-Eintrag für Runde 0 (zum Hinzufügen des Bieters)
                    session.add(Bid(
                        name=name,
                        round=0,
                        bid=0,
                        ida=self.auction.id,
                        time=current_time
                    ))

                    # Echte Gebote
                    for round_num, bid_value in bids:
                        session.add(Bid(
                            name=name,
                            round=round_num,
                            bid=bid_value,
                            ida=self.auction.id,
                            time=current_time
                        ))

                session.commit()

            return rx.toast.success(
                f"CSV-Datei erfolgreich importiert! {len(imported_data)} Bieter wurden importiert.",
                title="Import erfolgreich",
            )

        except Exception as e:
            self.import_error = f"Fehler beim Importieren: {str(e)}"
            return rx.toast.error(
                "Fehler beim Importieren der CSV-Datei",
                title="Import fehlgeschlagen",
            )

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
                                        "Manuelles Beenden, nach dem letzten Gebot",
                                        spacing="2"
                                    ),
                                    as_="label"
                                ),
                                rx.text(
                                    rx.flex(
                                        rx.radio_group.item(value="manual_first"),
                                        "Manuelles Beenden möglich, nach Rundenstart",
                                        spacing="2"
                                    ),
                                    as_="label"
                                ),
                                # rx.text(
                                #     rx.flex(
                                #         rx.radio_group.item(value="edit"),
                                #         "Nur Hier in den Einstellungen möglich",
                                #         spacing="2",
                                #         disabled=True,
                                #     ),
                                #     as_="label"
                                # ),
                                name="round_end_mode",
                                value=EditAuctionState.round_end_mode,
                                on_change=EditAuctionState.handle_round_end_mode_change,
                                direction="column",
                                spacing="3",
                                size="3"
                            ),
                            # rx.button(
                            #     "Manuell aktuelle Runde Beenden",
                            #     disabled=True,
                            #     height="25px"
                            # ),
                            align_items="start",
                            width="100%"
                        ),
                        direction="column",
                        width="100%"
                    ),
                    rx.flex(
                        rx.vstack(
                            rx.text.strong("Sichtbarkeit"),
                            rx.checkbox(
                                "Beendete Runden können eingesehen werden",
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

        # Export & Import & Delete Card
        rx.card(
            rx.vstack(
                rx.heading("Aktionen", size="6", weight="medium"),
                rx.divider(),
                # Export Button
                rx.button(
                    rx.icon("download"),
                    "Ergemnisse Als CSV exportieren",
                    on_click=EditAuctionState.export_result_csv,
                    color_scheme="green",
                    variant="outline",
                    size="3",
                    width="100%"
                ),
                # Export Button
                rx.button(
                    rx.icon("download"),
                    "Auktion als CSV exportieren",
                    on_click=EditAuctionState.export_csv,
                    color_scheme="blue",
                    variant="outline",
                    size="3",
                    width="100%"
                ),
                # Import Button mit Warning Dialog
                rx.alert_dialog.root(
                    rx.alert_dialog.trigger(
                        rx.button(
                            rx.icon("upload"),
                            "Aktion als CSV importieren",
                            color_scheme="orange",
                            variant="outline",
                            size="3",
                            width="100%"
                        ),
                    ),
                    rx.alert_dialog.content(
                        rx.alert_dialog.title("CSV-Datei importieren"),
                        rx.alert_dialog.description(
                            "Achtung: Alle vorhandenen Gebote werden gelöscht und durch die importierten Daten ersetzt. Dieser Vorgang kann nicht rückgängig gemacht werden.",
                        ),
                        rx.vstack(
                            rx.upload(
                                rx.cond(
                                    rx.selected_files("upload"),
                                    rx.vstack(
                                        rx.icon("file-check", size=48, color="green"),
                                        rx.selected_files("upload"),
                                        align="center",
                                    ),
                                    rx.vstack(
                                        rx.icon("file-question", size=48),
                                        " CSV-Datei auswählen",
                                        align="center",
                                    )
                                ),
                                id="upload",
                                margin="2em",
                                accept=".csv",
                                multiple=False,
                            ),
                            rx.flex(
                                rx.alert_dialog.action(
                                    rx.button(
                                        "Upload",
                                        variant="soft",
                                        size="2",
                                        on_click=EditAuctionState.handle_file_upload(rx.upload_files("upload")),
                                        disabled=~rx.selected_files("upload"),
                                    ),
                                ),
                                rx.spacer(),
                                rx.alert_dialog.cancel(
                                    rx.button(
                                        "Abbrechen",
                                        on_click=rx.clear_selected_files("upload"),
                                        variant="soft",
                                        size="2"
                                    ),
                                ),
                                spacing="3",
                                margin_top="16px",
                                justify="end",
                                width="100%",
                            ),
                            spacing="3",
                            width="100%",
                            align="center",
                        ),
                    ),

                ),
                rx.divider(),
                rx.divider(),
                # Delete Button
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
                spacing="4",
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
        on_mount=EditAuctionState.get_auction,
    )

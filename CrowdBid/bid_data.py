from datetime import datetime, timedelta
from typing import List
import reflex as rx
import sqlmodel
from sqlmodel import select

from CrowdBid.components import header
from CrowdBid.models import Auction, Bid

### BACKEND ###

class DataBidState(rx.State):
    """Der App State."""
    auction: Auction = None
    bids: List[Bid] = []
    current_bid: Bid = None


    @rx.var
    def auction_token(self) -> str:
        """Get the token from the URL parameters."""
        return self.router.page.params.get("token", "")

    def load_entries(self):
        """Lädt die Auktion anhand des Tokens."""
        with rx.session() as session:
            self.auction = session.exec(
                select(Auction).where(Auction.token == self.auction_token)
            ).first()
            if self.auction:
                self.bids = session.exec(
                    select(Bid).where(Bid.ida== self.auction.id)
                ).all()

    @rx.event
    def add_bid(self, form_data: dict):
        """Füge ein neues Bid hinzu."""
        form_data["time"] = datetime.now()
        with rx.session() as session:
            new_bid = Bid(**form_data)
            new_bid.ida = self.auction.id
            session.add(new_bid)
            session.commit()
            session.refresh(new_bid)
        self.load_entries()

    @rx.event
    def update_bid(self, form_data: dict):
        """Aktualisiere ein bestehendes Bid."""
        if not self.current_bid:
            return
        with rx.session() as session:
            bid = session.exec(
                select(Bid).where(
                    (Bid.ida == self.current_bid.ida) &
                    (Bid.name == self.current_bid.name) &
                    (Bid.round == self.current_bid.round)
                )
            ).first()
            for field, value in form_data.items():
                setattr(bid, field, value)
            session.add(bid)
            session.commit()
        self.load_entries()

    @rx.event
    def delete_bid(self, ida: int, name: str, round: int):
        with rx.session() as session:
            bid = session.exec(
                select(Bid).where(
                    sqlmodel.and_(
                        Bid.ida == ida,
                        Bid.name == name,
                        Bid.round == round
                    )
                )
            ).first()
            if bid:
                session.delete(bid)
                session.commit()
        self.load_entries()


### FRONTEND ###



@rx.page(route="/[token]/data")
def data_bid_ui():
    """
    Seite für die Anzeige der Bids einer Auktion.
    """
    return rx.vstack(
        header(),
        rx.heading(f"DATA: {DataBidState.auction.topic}"),
        rx.box(bid_table(), width="100%", border_width="1px", border_color="#444444", border_radius="20px"),
        bid_form(),
        on_mount=DataBidState.load_entries,
        width="100%",
        spacing="6",
        #padding_x=["1.5em", "1.5em", "3em"],
        padding="0.7rem"
    )


def bid_form():
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.hstack(
                    rx.icon("plus"),
                    rx.text("Add DataSet"),
                ),
            ),
        ),
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("New DataSet"),
                rx.form(
                    rx.vstack(
                        rx.input(
                            placeholder="Name",
                            name="name",
                            required=True,
                        ),
                        rx.input(
                            placeholder="Round",
                            name="round",
                            type="number",
                            required=True,
                        ),
                        rx.input(
                            placeholder="Bid",
                            name="bid",
                            type="number",
                            required=True,
                        ),
                        rx.hstack(
                            rx.dialog.close(
                                rx.button("Cancel")
                            ),
                            rx.dialog.close(
                                rx.button("Save", type="submit")
                            ),
                        ),
                    ),
                    on_submit=DataBidState.add_bid,
                ),
            ),
        ),
    )


def bid_table():
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Round"),
                rx.table.column_header_cell("Bid"),
                rx.table.column_header_cell("Date"),
                rx.table.column_header_cell(""),
            ),
        ),
        rx.table.body(
            rx.foreach(
                DataBidState.bids,
                lambda bid: rx.table.row(
                    rx.table.cell(bid.name),
                    rx.table.cell(bid.round),
                    rx.table.cell(bid.bid),
                    rx.table.cell(bid.time),
                    rx.table.cell(
                        rx.hstack(
                            rx.button(
                                "Delete",
                                on_click=lambda: DataBidState.delete_bid(
                                    bid.ida, bid.name, bid.round
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

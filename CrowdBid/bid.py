from datetime import datetime
import reflex as rx
import sqlalchemy
from sqlmodel import select
from CrowdBid.models import Auction, Bid


### BACKEND ###

class BidState(rx.State):
    bids: list[dict] = []
    max_round: int = 0
    auction: Auction = None

    @rx.var
    def auction_token(self) -> str:
        """Get the token from the URL parameters."""
        return self.router.page.params.get("token", "")

    @rx.var
    def round_headers(self) -> list[str]:
        return [f"Round {i}" for i in range(1, self.max_round + 1)]

    @rx.var
    def round_keys(self) -> list[str]:
        return [f"round{i}" for i in range(1, self.max_round + 1)]

    @rx.var
    def last_round_key(self) -> str:
        return f"round{self.max_round}" if self.max_round > 0 else ""

    @rx.event
    def add_bidder(self, form_data: dict):
        """Add a new bidder"""
        form_data["time"] = datetime.now()
        with rx.session() as session:
            new_bid = Bid(**form_data)
            new_bid.ida = self.auction.id
            new_bid.round = self.max_round
            session.add(new_bid)
            session.commit()
            session.refresh(new_bid)
        self.load_bids()

    @rx.event
    def handle_bid(self, form_data: dict):
        if "bid" in form_data:
            with rx.session() as session:
                session.execute(
                    sqlalchemy.text(
                        "INSERT INTO bid (name, round, bid, ida, time) "
                        "VALUES (:name, :round, :bid, :ida, datetime('now')) "
                        "ON CONFLICT (name, round, ida) DO UPDATE "
                        "SET bid = :bid"
                    ),
                    {
                        "name": form_data["name"],
                        "round": self.max_round,
                        "bid": float(form_data["bid"]),
                        "ida": self.auction.id
                    }
                )
                session.commit()

            # Tabelle neu laden
            self.load_bids()


    @rx.event
    def load_bids(self):
        with rx.session() as session:
            self.auction = session.exec(select(Auction).where(Auction.token == self.auction_token)).first()
            # Alle Bids aus der Datenbank holen
            query = select(Bid)
            all_bids = session.exec(query).all()

            bid_dict = {}
            rounds = set()

            for bid in all_bids:
                if bid.name not in bid_dict:
                    bid_dict[bid.name] = {}
                bid_dict[bid.name][f"round{bid.round}"] = bid.bid
                rounds.add(bid.round)

            self.max_round = max(rounds) if rounds else 0

            transformed_bids = []
            for name, rounds_data in bid_dict.items():
                row = {"name": name}
                row.update(rounds_data)
                transformed_bids.append(row)

            self.bids = transformed_bids


### FRONTEND ###

def bid_dialog(name: str):
    return rx.dialog.content(
        rx.dialog.title("Gebot eingeben"),
        rx.form(
            rx.vstack(
                rx.el.input(
                    name="name",
                    hidden=True,
                    value=name,
                ),
                rx.input(
                    placeholder="Bid",
                    name="bid",
                    type_="number",
                    required=True,
                ),
                rx.hstack(
                    rx.dialog.close(
                        rx.button("Cancel")
                    ),
                    rx.dialog.close(
                        rx.button("Submit", type="submit")
                    ),
                ),
            ),
            on_submit=BidState.handle_bid,
        ),
    )


@rx.page(route="/[token]/bid")
def bid_ui():
    """
    Seite für die Anzeige der Bids einer Auktion.
    """
    return rx.vstack(
        rx.heading(BidState.auction.topic),
        rx.text(BidState.auction.description),
        rx.divider(),
        rx.box(bid_table(), width="100%", border_width="1px", border_color="#444444", border_radius="20px"),
        add_bidder_dialog(),
        width="100%",
        spacing="6",
        padding_x=["1.5em", "1.5em", "3em"],
    )


def add_bidder_dialog():
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.hstack(
                    rx.icon("plus"),
                    rx.text("Add Bidder"),
                ),
            ),
        ),
        rx.dialog.content(
            rx.vstack(
                rx.dialog.title("New Bidder"),
                rx.form(
                    rx.vstack(
                        rx.input(
                            placeholder="Name",
                            name="name",
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
                                rx.button("Bid", type="submit")
                            ),
                        ),
                    ),
                    on_submit=BidState.add_bidder,
                ),
            ),
        ),
    )


def bid_table():
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.foreach(
                    BidState.round_headers,
                    lambda round_name: rx.table.column_header_cell(round_name)
                ),
                rx.table.column_header_cell("Action")
            )
        ),
        rx.table.body(
            rx.foreach(
                BidState.bids,
                lambda bid: rx.table.row(
                    rx.table.cell(bid["name"]),
                    rx.foreach(
                        BidState.round_keys,
                        lambda round_key: rx.table.cell(bid.get(round_key, "-"))
                    ),
                    rx.table.cell(
                        rx.dialog.root(
                            rx.dialog.trigger(
                                rx.button(
                                    rx.cond(
                                        bid.contains(BidState.last_round_key),
                                        "Change",
                                        "Bid"
                                    ),
                                    width="80px",
                                )
                            ),
                            bid_dialog(bid["name"]),
                        )
                    )
                )
            )
        ),
        on_mount=BidState.load_bids,
        variant="surface",
        size="3",
        width="100%"
    )

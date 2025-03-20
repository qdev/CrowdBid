import reflex as rx
from CrowdBid.models import Auction
from sqlmodel import select
from datetime import datetime

### BACKEND ###

class ListAuctionState(rx.State):
    auctions: list[Auction] = []
    current_auction: Auction = Auction()

    def load_entries(self) -> list[Auction]:
        with rx.session() as session:
            query = select(Auction)
            self.auctions = session.exec(query).all()

    @rx.event
    def delete_auction(self, id: int):
        with rx.session() as session:
            auction = session.exec(select(Auction).where(Auction.id == id)).first()
            session.delete(auction)
            session.commit()
        self.load_entries()



### FRONTEND ###

def list_auction_ui():
    return rx.vstack(
        auktion_table(),
        on_mount=ListAuctionState.load_entries,
        width="100%",
    )

def auktion_table():
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Bid"),
                rx.table.column_header_cell("Data"),
                rx.table.column_header_cell("Edit"),
                rx.table.column_header_cell("Topic"),
                rx.table.column_header_cell("Target Bid"),
                rx.table.column_header_cell("Created"),
                rx.table.column_header_cell("Updated"),
                rx.table.column_header_cell("Actions"),
            )
        ),
        rx.table.body(
            rx.foreach(
                ListAuctionState.auctions,
                lambda auction: rx.table.row(
                    rx.table.cell(rx.link("bid",href=f"/{auction.token}/bid")),
                    rx.table.cell(rx.link("data", href=f"/{auction.token}/data")),
                    rx.table.cell(rx.link("edit", href=f"/{auction.config_token}/edit")),
                    rx.table.cell(auction.topic),
                    rx.table.cell(auction.target_bid),
                    rx.table.cell(auction.create_at),
                    rx.table.cell(auction.update_at),
                    rx.table.cell(
                        rx.hstack(
                            rx.button("Delete", on_click=lambda: ListAuctionState.delete_auction(auction.id))
                        )
                    )
                )
            )
        ),
        on_mount=ListAuctionState.load_entries
    )
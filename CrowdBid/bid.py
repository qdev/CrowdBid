import asyncio
import math

import reflex as rx
import websockets
from sqlmodel import select
from CrowdBid.components import header
from CrowdBid.models import Auction, Bid
from sqlalchemy import update
from datetime import datetime
from typing import Optional, List, Dict, Any


### BACKEND ###

# Aktuell gemischt Deutsch/Englisch
class BidState(rx.State):
    new_name: str = ""  # Deutsch
    bids: List[Dict[str, Any]] = []
    actual_round: int = 1
    status: str = ""
    auction: Optional[Auction] = None
    rounds: List[int] = []
    sums: List[float] = []
    hidden: bool = True
    missing: int
    editing_name: str = ""  # Englisch
    show_add_input: bool = False
    hovered_name: str = ""
    editing_value_name: str = ""
    is_valid_bid: bool = False

    def reset_bid_validation(self):
        self.is_valid_bid = False

    @rx.event(background=True)
    async def ws_listener(self):
        while True:
            try:
                async with websockets.connect("ws://localhost:28765") as ws:
                    async for message in ws:
                        async with self:
                            msg = message.split("#")
                            if msg[0] == f"A{self.auction.id}":
                                self.load_bids()
                                if msg[1]:
                                    yield rx.toast.info(msg[1])
            except Exception:
                await asyncio.sleep(2)

    @rx.event(background=True)
    async def send_ws(self, msg: str = ""):
        try:
            async with websockets.connect("ws://localhost:28765") as ws:
                await ws.send(f"A{self.auction.id}#{msg}")
        except Exception:
            pass

    @rx.event
    def toggle_hidden(self):
        self.hidden = not self.hidden
        self.status += "."
        return BidState.send_ws()

    @rx.event
    def end_round(self):
        with rx.session() as session:
            session.exec(update(Auction).where(Auction.id == self.auction.id).values(last_round=self.actual_round + 1))
            session.commit()
        return BidState.send_ws(f"Die Runde {self.actual_round} wurde beendet.")

    @rx.var
    def auction_token(self) -> str:
        return self.router.page.params.get("token", "")

    @rx.var
    def last_round_key(self) -> str:
        return f"round{self.actual_round}" if self.actual_round > 0 else ""

    @rx.event
    def handle_bid(self, form_data: dict):
        self.is_valid_bid = False
        try:
            with rx.session() as session:
                session.merge(Bid(name=form_data["name"], round=self.actual_round, bid=float(form_data["bid"]), ida=self.auction.id, time=datetime.now()))
                session.commit()
            return BidState.send_ws(f"{form_data['name']} hat ein Gebot abgegeben.")
        except Exception as e:
            print(f"Error: {str(e)}")
            self.load_bids()
            return None

    @rx.event
    def load_bids(self):
        with rx.session() as session:
            # First, try to get the auction
            self.auction = session.exec(select(Auction).where(Auction.token == self.auction_token)).first()

            # If no auction is found, redirect to 404 and return early
            if self.auction is None:
                return rx.redirect("/404")

            # Rest of the method remains the same
            all_bids = session.exec(select(Bid).where(Bid.ida == self.auction.id)).all()

            bid_dict = {}
            ar = 0

            for bid in all_bids:
                if bid.name not in bid_dict:
                    bid_dict[bid.name] = {}
                bid_dict[bid.name][bid.round] = bid.bid
                ar = max(ar, bid.round)

            self.bids = []
            bid_sum = {}
            for name, values in bid_dict.items():
                tb = {'name': name}
                tv = float("nan")
                for r in range(1, ar + 1):
                    if r in values:
                        tv = values.get(r)
                        tb[r] = tv
                    elif r < max(ar, self.auction.last_round) and not math.isnan(tv):
                        tb[r] = - tv
                    if not math.isnan(tv):
                        bid_sum[r] = bid_sum.get(r, 0) + tv
                self.bids.append(tb)

            self.missing = sum([0 if ar in x else 1 for x in self.bids])
            if ar == 0 or (self.missing == 0 and self.auction.round_end_mode == "auto") or self.auction.last_round > ar:
                self.actual_round = ar + 1
                self.missing = len(self.bids)
            else:
                self.actual_round = ar

            if self.actual_round < 2:
                self.status = f"Es sind {self.auction.target_bid} € aufzubringen. Durch Klicken auf das \uFF0B können neue Bietende hinzugefügt werden."
            else:
                s = bid_sum[self.actual_round - 1]
                if self.auction.target_bid > s:
                    self.status = f"Es sind {self.auction.target_bid} € aufzubringen. In der Letzten Runde wurden davon {s / self.auction.target_bid * 100:.1f} % erreicht. Es Fehlen noch {self.auction.target_bid - s} €"
                else:
                    self.status = f"Es waren {self.auction.target_bid} € aufzubringen. Es sind zusätzlich {s - self.auction.target_bid} € geboten worden"
            self.rounds = list(range(1, self.actual_round))
            self.sums = [float(bid_sum.get(i, 0)) if bid_sum.get(i, 0).is_integer() else bid_sum.get(i, 0) for i in range(1, self.actual_round)]

    @rx.event
    def rename_bidder(self, name_alt: str, name_neu: str):
        with rx.session() as session:
            if not session.exec(select(Bid).where((Bid.ida == self.auction.id) & (Bid.name == name_neu))).first():
                session.exec(update(Bid).where((Bid.ida == self.auction.id) & (Bid.name == name_alt)).values(name=name_neu))
                session.commit()

    @rx.event
    def add_name(self):
        if self.new_name.strip():
            with rx.session() as session:
                session.add(Bid(name=self.new_name.strip(), round=0, bid=0, ida=self.auction.id, time=datetime.now()))
                session.commit()
            self.new_name = ""
            self.show_add_input = False
            return BidState.send_ws(f"Neuer Bietende: {self.new_name.strip()}")
        return None

    @rx.event
    def show_add(self):
        self.cancel_edit_name()
        self.show_add_input = True
        self.new_name = ""

    @rx.event
    def cancel_add(self):
        self.show_add_input = False
        self.new_name = ""

    @rx.event
    def start_edit_name(self, name: str):
        self.editing_name = name
        self.editing_value_name = name
        self.show_add_input = False

    @rx.event
    def cancel_edit_name(self):
        self.editing_name = ""
        self.editing_value_name = ""
        self.hovered_name = ""

    @rx.event
    def confirm_edit_name(self):
        if self.editing_value_name.strip():
            newn = self.editing_value_name
            oldn = self.editing_name
            self.rename_bidder(oldn, newn)
            self.editing_name = ""
            self.editing_value_name = ""
            self.hovered_name = ""
            return BidState.send_ws(f"{oldn} hat sich in {newn} umbenannt.")
        return None

    @rx.event
    def validate_bid(self, value: str):
        try:
            if value and float(value) >= 0:
                self.is_valid_bid = True
            else:
                self.is_valid_bid = False
        except ValueError:
            self.is_valid_bid = False


### FRONTEND ###

@rx.page(route="/[token]/bid", on_load=BidState.ws_listener)
def bid_ui():
    return rx.vstack(
        header(BidState, BidState.auction.peek),
        rx.card(
            rx.vstack(
                rx.heading(BidState.auction.topic, size="6"),
                rx.divider(),
                rx.text(BidState.auction.description),
                spacing="4",
            ),
            width="100%",
            max_width="1000px",
            padding="6",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Status", size="1"),
                rx.divider(),
                rx.text(BidState.status),
                spacing="4",
            ),
            width="100%",
            max_width="1000px",
            padding="6",
        ),
        rx.card(
            rx.vstack(
                rx.heading("Gebote", size="1"),
                rx.divider(),
                bid_table(),
                spacing="4",
            ),
            width="100%",
            max_width="1000px",
            padding="6",
        ),
        rx.spacer(),
        rx.el.hr(width="100%"),
        width="100%",
        spacing="6",
        align_items="center",
        padding="2em",
    )


def bid_dialog(name: str, add: bool):
    return rx.dialog.content(
        rx.dialog.title("Gebot eingeben"),
        rx.dialog.description("Formular zum Eingeben eines neuen Gebots"),
        rx.form(
            rx.flex(
                rx.el.input(
                    name="name",
                    type="hidden",
                    value=name,
                ),
                rx.vstack(
                    rx.input(
                        placeholder="0.00",
                        name="bid",
                        # type="number",
                        # required=True,
                        min="0.01",
                        step="0.01",
                        size="3",
                        on_change=BidState.validate_bid,
                    ),
                    rx.cond(add & (BidState.auction.round_end_mode == "auto") & (BidState.missing == 1),
                            rx.text("Achtung! Dieses Gebot schließt die Runde ab. Ein Ändern ist dan nicht mehr möglich.", color="red")),
                    align_items="start",
                ),
                rx.flex(
                    rx.dialog.close(
                        rx.button(
                            "Abbrechen",
                            variant="soft",
                            size="2",
                        ),
                    ),
                    rx.cond(
                        BidState.is_valid_bid,
                        rx.dialog.close(
                            rx.button(
                                "Bieten",
                                type="submit",
                                size="2",
                                color_scheme="grass",
                            ),
                        ),
                        rx.button(
                            "Bieten",
                            type="submit",
                            size="2",
                            color_scheme="gray",
                            is_disabled=True,
                        ),
                    ),
                    spacing="3",
                    justify="end",
                ),
                direction="column",
                spacing="4",
            ),
            on_submit=BidState.handle_bid,
        ),
        max_width="400px",
    )


def bidder(name):
    return rx.cond(
        BidState.editing_name == name,
        rx.hstack(
            rx.input(
                value=BidState.editing_value_name,
                on_change=BidState.set_editing_value_name,
                auto_focus=True,
            ),
            rx.icon("check", on_click=BidState.confirm_edit_name, color="green"),
            rx.icon("x", on_click=BidState.cancel_edit_name, color="red"),
        ),
        rx.hstack(
            rx.box(
                rx.text(
                    name,
                    on_click=lambda: BidState.start_edit_name(name),
                    style={"cursor": "pointer"},
                ),
                rx.cond(
                    (BidState.hovered_name == name) | (BidState.editing_name == name),
                    rx.icon(
                        "pencil",
                        size=12,
                        on_click=lambda: BidState.start_edit_name(name),
                        style={"margin_left": "2px", "vertical_align": "middle"},
                    ),
                ),
                on_mouse_enter=lambda: BidState.set_hovered_name(name),
                on_mouse_leave=lambda: BidState.set_hovered_name(""),
                style={"display": "inline-flex", "align_items": "center"},
            ),
            align="center",
        )
    )


def bid_table():
    return rx.box(
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell(
                        "Runde:",
                        style={
                            "position": "sticky",
                            "left": "0",
                            "background": "var(--gray-2)",
                            "z_index": "1"
                        }
                    ),
                    rx.foreach(
                        BidState.rounds,
                        # lambda r: rx.table.column_header_cell(f"\u00A0{r}\u00A0", vertical_align="middle", style={"white_space": "nowrap", "text_decoration": "underline", "text_decoration_thickness": "2px","text_underline_offset": "4px"})
                        lambda r: rx.table.column_header_cell(f"R{r}", vertical_align="middle")
                    ),
                    rx.cond(
                        BidState.bids.length() > 1,
                        rx.table.column_header_cell(
                            f"R{BidState.actual_round}",
                        ),
                    ),
                )
            ),
            rx.table.body(
                rx.foreach(
                    BidState.bids,
                    lambda bid: rx.table.row(
                        rx.table.cell(
                            bidder(bid["name"]),
                            vertical_align="middle",
                            style={
                                "position": "sticky",
                                "left": "0",
                                "background": "var(--gray-2)",
                                "z_index": "1"
                            }
                        ),

                        rx.foreach(
                            BidState.rounds,
                            lambda r: rx.table.cell(
                                rx.cond(
                                    BidState.hidden,
                                    rx.icon("eye-off", color="gray", size=16),
                                    rx.cond(
                                        rx.Var(f"{bid[r]} <= 0", _var_type=bool),
                                        rx.text.em(rx.Var(f"-{bid[r]}", _var_type=float), color="grey"),
                                        rx.text(bid.get(r, "-"))
                                    ),
                                ),
                                vertical_align="middle"
                            )
                        ),
                        rx.cond(
                            BidState.bids.length() > 1,
                            rx.table.cell(
                                rx.cond(
                                    bid.contains(BidState.actual_round),
                                    rx.hstack(
                                        rx.dialog.root(
                                            rx.dialog.trigger(rx.button("Ändern", width="70px")),
                                            bid_dialog(bid["name"], False),
                                            on_open_change=BidState.reset_bid_validation,
                                        ),
                                        rx.icon("circle-check-big", color="green", size=24),
                                    ),
                                    rx.hstack(
                                        rx.dialog.root(
                                            rx.dialog.trigger(rx.button("Bieten", width="70px")),
                                            bid_dialog(bid["name"], True),
                                            on_open_change=BidState.reset_bid_validation,
                                        ),
                                        rx.icon("circle", color="gray", size=24),
                                    )
                                ),
                            ),
                        ),
                        width="100%",
                        vertical_align="middle"
                    ),
                ),
                rx.table.row(
                    rx.table.cell(
                        rx.cond(
                            ~BidState.show_add_input,
                            rx.icon("plus", size=24, on_click=BidState.show_add),
                            rx.hstack(
                                rx.input(
                                    placeholder="Name eingeben",
                                    value=BidState.new_name,
                                    on_change=BidState.set_new_name,
                                    auto_focus=True,
                                ),
                                rx.icon("check", on_click=BidState.add_name, color="green"),
                                rx.icon("x", on_click=BidState.cancel_add, color="red"),
                            ),
                        ),
                        style={
                            "position": "sticky",
                            "left": "0",
                            "background": "var(--gray-2)",
                            "z_index": "1"
                        }
                    ),
                    rx.foreach(
                        BidState.rounds,
                        lambda r: rx.table.column_header_cell("")
                    ),
                    rx.cond(
                        BidState.bids.length() > 1,
                        rx.table.column_header_cell("")
                    ),
                ),

                rx.table.row(
                    rx.table.column_header_cell(
                        "Summe:",
                        vertical_align="middle",
                        style={
                            "position": "sticky",
                            "left": "0",
                            "background": "var(--gray-2)",
                            "z_index": "1"
                        }
                    ),
                    rx.foreach(
                        BidState.sums,
                        lambda r: rx.table.column_header_cell(f"{r}", vertical_align="middle")
                    ),
                    rx.cond(
                        BidState.bids.length() > 1,
                        rx.table.column_header_cell(
                            # Bei "auto" - zeige die Info-Box
                            rx.cond(
                                BidState.auction.round_end_mode == "auto",
                                rx.box(
                                    rx.text(
                                        "Runde endet automatisch mit letztem Gebot",
                                        size="1",
                                        style={
                                            "line_height": "1.2",
                                            "text_align": "center",
                                            "white_space": "pre-line"
                                        }
                                    ),
                                    padding="2",
                                    border_radius="8px",
                                    background="var(--gray-a3)",
                                    border="1px solid var(--gray-a6)",
                                    width="110px"
                                ),
                                # Bei "manual_last" - zeige Button oder Info
                                rx.cond(
                                    BidState.auction.round_end_mode == "manual_last",
                                    rx.cond(
                                        BidState.missing == 0,
                                        rx.button(
                                            "Runde beenden",
                                            on_click=BidState.end_round,
                                            size="1",
                                            color_scheme="blue",
                                            variant="solid",
                                            width="110px"
                                        ),
                                        rx.box(
                                            rx.text(
                                                "Es fehlen noch Gebote",
                                                size="1",
                                                style={
                                                    "line_height": "1.2",
                                                    "text_align": "center",
                                                    "white_space": "pre-line"
                                                }
                                            ),
                                            padding="2",
                                            border_radius="8px",
                                            background="var(--gray-a3)",
                                            border="1px solid var(--gray-a6)",
                                            width="110px"
                                        )
                                    ),
                                    # Bei "manual_first" - zeige immer Button
                                    rx.cond(
                                        BidState.bids.length() - BidState.missing > 0,
                                        rx.button(
                                            "Runde beenden",
                                            on_click=BidState.end_round,
                                            size="1",
                                            color_scheme="blue",
                                            variant="solid",
                                            width="110px"
                                        ),
                                        rx.box(
                                            rx.text(
                                                "Es fehlen noch Gebote",
                                                size="1",
                                                style={
                                                    "line_height": "1.2",
                                                    "text_align": "center",
                                                    "white_space": "pre-line"
                                                }
                                            ),
                                            padding="2",
                                            border_radius="8px",
                                            background="var(--gray-a3)",
                                            border="1px solid var(--gray-a6)",
                                            width="110px"
                                        )
                                    ),
                                )
                            )
                        )
                    ),
                    bg="var(--gray-a2)",
                ),
            ),
            variant="surface",
            size="3",
            width="100%",
            id="bid-table",
        ),
        on_mount=lambda: [
            BidState.load_bids(),
            rx.call_script("""
                setTimeout(() => {
                    const table = document.getElementById('bid-table');
                    if (table) {
                        const viewport = table.querySelector('[data-radix-scroll-area-viewport]');
                        if (viewport) {
                            viewport.scrollLeft = viewport.scrollWidth;
                        }
                    }
                }, 100);
            """)
        ],
        width="100%",
    )

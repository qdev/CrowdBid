import reflex as rx


def header(bs=None):
    return (
        rx.vstack(
            rx.flex(
                rx.link(
                    rx.badge(
                        rx.icon(tag="gavel", size=32),
                        rx.heading("CrowdBid", size="6"),
                        color_scheme="blue",
                        radius="large",
                        align="center",
                        variant="surface",
                        padding="0.65rem",
                    ),
                    href="/",
                ),
                rx.spacer(),
                rx.hstack(
                    rx.cond(bs and bs.hidden,
                            rx.icon("eye", on_click=bs.toggle_hidden if bs else None),
                            rx.icon("eye-off", on_click=bs.toggle_hidden if bs else None)) if bs else rx.text(""),
                    rx.color_mode.button(),
                    spacing="3",
                    align_items="center",
                ),
                width="100%",
                align_items="center",
                top="0px",
            ),
            rx.el.hr(width="100%"),
            width="100%",
        ),
    )
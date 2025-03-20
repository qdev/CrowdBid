import reflex as rx

def header():
    return (
        rx.vstack(
            rx.flex(
                rx.badge(
                    rx.icon(tag="gavel", size=32),
                    rx.heading("CrowdBid", size="6"),
                    # color_scheme="green",
                    color_scheme="blue",
                    radius="large",
                    align="center",
                    variant="surface",
                    padding="0.65rem",
                ),
                rx.spacer(),
                rx.color_mode.button(),
                width="100%",
                top="0px",
            ),
            rx.el.hr(width="100%"),
            width="100%",
        ),
    )

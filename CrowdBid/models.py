from datetime import datetime, timedelta
import reflex as rx
import sqlmodel


class Auction(rx.Model, table=True):
    id: int = sqlmodel.Field(default=None, primary_key=True)
    token: str = sqlmodel.Field(max_length=16, unique=True)
    config_token: str = sqlmodel.Field(max_length=16, unique=True)
    create_at: datetime
    update_at: datetime
    expiration: datetime = sqlmodel.Field(default=None)
    topic: str = sqlmodel.Field(default=None)
    description: str = sqlmodel.Field(default=None)
    target_bid: float = sqlmodel.Field(default=None)


class Bid(rx.Model, table=True):
    ida: int = sqlmodel.Field(default=None, primary_key=True)
    name: str = sqlmodel.Field(default=None, primary_key=True)
    round: int = sqlmodel.Field(default=None, primary_key=True)
    bid: float
    time: datetime
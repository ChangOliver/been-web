from datetime import UTC, date, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel


def now_utc() -> datetime:
    return datetime.now(UTC)


class PlaceType(StrEnum):
    country = "country"
    region = "region"
    city = "city"
    airport = "airport"


class PlaceStatusValue(StrEnum):
    visited = "visited"
    lived = "lived"
    planned = "planned"


class TripStatus(StrEnum):
    planned = "planned"
    completed = "completed"
    cancelled = "cancelled"


class Profile(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(default="My travels", max_length=120)
    is_default: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class PlaceStatus(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    place_type: PlaceType = Field(default=PlaceType.country, index=True)
    place_code: str = Field(index=True, max_length=16)
    status: PlaceStatusValue
    first_visited_on: date | None = None
    last_visited_on: date | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class Visit(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    place_type: PlaceType = Field(default=PlaceType.country)
    place_code: str = Field(index=True, max_length=16)
    trip_id: UUID | None = Field(default=None, foreign_key="trip.id", index=True)
    arrived_on: date | None = None
    departed_on: date | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class Trip(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    profile_id: UUID = Field(foreign_key="profile.id", index=True)
    name: str = Field(max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    status: TripStatus = Field(default=TripStatus.planned)
    notes: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TripStop(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    trip_id: UUID = Field(foreign_key="trip.id", index=True)
    place_type: PlaceType = Field(default=PlaceType.country)
    place_code: str = Field(max_length=16)
    arrival_date: date | None = None
    departure_date: date | None = None
    position: int = Field(default=0)
    notes: str | None = None

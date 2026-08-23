from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import PlaceStatusValue, PlaceType, TripStatus


class Country(BaseModel):
    code: str
    alpha3: str
    numeric: str
    name: str
    continent: str | None = None


class StatusUpsert(BaseModel):
    status: PlaceStatusValue
    first_visited_on: date | None = None
    last_visited_on: date | None = None
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.first_visited_on and self.last_visited_on and self.last_visited_on < self.first_visited_on:
            raise ValueError("last_visited_on must not precede first_visited_on")
        return self


class StatusResponse(StatusUpsert):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    place_type: PlaceType
    place_code: str


class Place(BaseModel):
    code: str
    place_type: PlaceType
    name: str
    country_code: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class VisitCreate(BaseModel):
    place_type: PlaceType = PlaceType.country
    place_code: str = Field(min_length=2, max_length=16)
    arrived_on: date | None = None
    departed_on: date | None = None
    trip_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.arrived_on and self.departed_on and self.departed_on < self.arrived_on:
            raise ValueError("departed_on must not precede arrived_on")
        return self


class VisitResponse(VisitCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TripCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    start_date: date | None = None
    end_date: date | None = None
    status: TripStatus = TripStatus.planned
    notes: str | None = Field(default=None, max_length=10000)

    @model_validator(mode="after")
    def dates_are_ordered(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class TripResponse(TripCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    stops: list["TripStopResponse"] = []


class TripStopCreate(BaseModel):
    place_type: PlaceType = PlaceType.country
    place_code: str = Field(min_length=2, max_length=16)
    arrival_date: date | None = None
    departure_date: date | None = None
    position: int = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=10000)


class TripStopResponse(TripStopCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class Statistics(BaseModel):
    countries_visited: int
    countries_lived: int
    countries_planned: int
    recognized_countries: int
    visited_percentage: float
    trips: int
    visits: int
    travel_days: int
    regions_visited: int = 0
    regions_total: int = 0
    regions_percentage: float = 0
    cities_visited: int = 0
    airports_visited: int = 0

from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from uuid import UUID

import airportsdata
import geonamescache
import pycountry
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlmodel import Session, delete, select

from app.core.config import get_settings
from app.core.database import get_session
from app.models import PlaceStatus, PlaceStatusValue, PlaceType, Profile, Trip, TripStop, Visit
from app.schemas import (
    Country,
    Place,
    Statistics,
    StatusResponse,
    StatusUpsert,
    TripCreate,
    TripResponse,
    TripStopCreate,
    TripStopResponse,
    VisitCreate,
    VisitResponse,
)

router = APIRouter(prefix="/api/v1")
UK_TOP_REGIONS = (
    ("GB-E12000001", "North East"),
    ("GB-E12000002", "North West"),
    ("GB-E12000003", "Yorkshire and The Humber"),
    ("GB-E12000004", "East Midlands"),
    ("GB-E12000005", "West Midlands"),
    ("GB-E12000006", "East of England"),
    ("GB-E12000007", "London"),
    ("GB-E12000008", "South East"),
    ("GB-E12000009", "South West"),
    ("GB-N92000002", "Northern Ireland"),
    ("GB-S92000003", "Scotland"),
    ("GB-W92000004", "Wales"),
)
# ISO entries that are administered territories/dependencies rather than
# standalone countries in the country picker. Their places remain available
# under the owning country's regions/cities/airports where applicable.
NON_SOVEREIGN_TERRITORIES = {
    "AS", "AI", "AW", "BM", "BQ", "BV", "CC", "CK", "CX", "EH", "FK",
    "FO", "GF", "GG", "GI", "GL", "GP", "GS", "GU", "HK", "IM", "IO",
    "JE", "KY", "MO", "MS", "NC", "NF", "NU", "PF", "PG", "PN", "PR",
    "RE", "SH", "SJ", "SX", "TC", "TK", "UM", "VI", "WF", "YT",
}
TOURIST_CITY_NAMES = {
    "amsterdam", "athens", "auckland", "bangkok", "barcelona", "beijing", "berlin", "boston", "budapest", "buenos aires", "cairo", "cape town", "chicago", "copenhagen", "dublin", "dubai", "edinburgh", "florence", "frankfurt", "hanoi", "honolulu", "istanbul", "jaipur", "jerusalem", "johannesburg", "kyoto", "las vegas", "lima", "lisbon", "london", "los angeles", "madrid", "manila", "marrakesh", "melbourne", "mexico city", "miami", "milan", "montreal", "moscow", "munich", "mumbai", "new orleans", "new york city", "osaka", "paris", "phuket", "prague", "reykjavik", "rio de janeiro", "rome", "san francisco", "santiago", "seoul", "shanghai", "singapore", "stockholm", "sydney", "taipei", "tel aviv", "tokyo", "toronto", "vancouver", "venice", "vienna", "washington", "zurich", "denpasar", "ho chi minh city", "kuala lumpur", "queenstown", "cancun", "orlando", "palermo", "porto", "salzburg", "seville", "tallinn", "valletta", "warsaw", "xian", "zhangjiajie"
}


def countries() -> list[Country]:
    display_names = {"Taiwan, Province of China": "Taiwan"}
    geo_countries = geonamescache.GeonamesCache().get_countries()
    return [Country(code=c.alpha_2, alpha3=c.alpha_3, numeric=c.numeric, name=display_names.get(c.name, c.name), continent=geo_countries.get(c.alpha_2, {}).get("continentcode")) for c in pycountry.countries if c.alpha_2 not in NON_SOVEREIGN_TERRITORIES]


@lru_cache
def reference_places(place_type: str, featured_only: bool = True) -> tuple[Place, ...]:
    if place_type == "region":
        subdivisions = [item for item in pycountry.subdivisions if item.country_code != "GB"]
        return tuple([Place(code=item.code, place_type="region", name=item.name, country_code=item.country_code) for item in subdivisions] + [Place(code=code, place_type="region", name=name, country_code="GB") for code, name in UK_TOP_REGIONS])
    if place_type == "city":
        cities = geonamescache.GeonamesCache().get_cities()
        featured: dict[str, dict[str, Any]] = {}
        for item in cities.values():
            name = str(item.get("name", "")).casefold()
            key = f"{item['countrycode']}:{name}"
            if not featured_only:
                if key not in featured or item.get("population", 0) > featured[key].get("population", 0):
                    featured[key] = item
            elif name in TOURIST_CITY_NAMES and (key not in featured or item.get("population", 0) > featured[key].get("population", 0)):
                featured[key] = item
        return tuple(Place(code=f"{item['countrycode']}-{item['geonameid']}", place_type="city", name=city_display_name(item), country_code=item["countrycode"], region_code=str(item.get("admin1code", "")) or None, latitude=item["latitude"], longitude=item["longitude"]) for item in featured.values())
    if place_type == "airport":
        airports = airportsdata.load("IATA")
        return tuple(Place(code=code, place_type="airport", name=f"{item['name']} ({code})", country_code=item.get("country"), latitude=item.get("lat"), longitude=item.get("lon")) for code, item in airports.items())
    return tuple(Place(code=item.code, place_type="country", name=item.name) for item in countries())


def english_name(item: dict[str, Any]) -> str:
    name = str(item.get("name", ""))
    if name.isascii():
        return name
    alternatives = [str(value) for value in item.get("alternatenames", []) if str(value).isascii()]
    return min(alternatives or [name], key=len)


def city_display_name(item: dict[str, Any]) -> str:
    name = english_name(item)
    admin_code = str(item.get("admin1code", ""))
    region_label = admin_code.upper()
    return f"{name}, {region_label}" if region_label else name


def place_or_404(place_type: str, code: str) -> Place:
    item = next((place for place in reference_places(place_type) if place.code.casefold() == code.casefold()), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Unknown {place_type} code")
    return item


def country_or_404(code: str) -> Country:
    normalized = code.upper()
    result = next((country for country in countries() if country.code == normalized), None)
    if result is None:
        raise HTTPException(status_code=404, detail="Unknown country code")
    return result


def default_profile(session: Session) -> Profile:
    profile = session.exec(select(Profile).where(Profile.is_default)).first()
    if profile is None:
        profile = Profile()
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api", "timestamp": datetime.now(UTC).isoformat()}


@router.get("/meta")
def meta() -> dict[str, str]:
    settings = get_settings()
    return {"app": settings.app_name, "environment": settings.environment, "schema_version": "1", "geo_data_version": "pycountry"}


@router.get("/countries", response_model=list[Country])
def list_countries() -> list[Country]:
    return countries()


@router.get("/countries/{code}")
def country_detail(code: str, session: Session = Depends(get_session)) -> dict[str, Any]:
    country = country_or_404(code)
    profile = default_profile(session)
    place_status = session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id, PlaceStatus.place_code == country.code)).first()
    visits = session.exec(select(Visit).where(Visit.profile_id == profile.id, Visit.place_code == country.code).order_by(Visit.arrived_on.desc())).all()
    return {"country": country, "status": place_status, "visits": visits}


@router.get("/places/{place_type}", response_model=list[Place])
def list_places(place_type: str, country_code: str | None = None, limit: int = Query(default=50000, ge=1, le=50000), featured: bool = True) -> list[Place]:
    if place_type not in ("region", "city", "airport"):
        raise HTTPException(status_code=400, detail="place_type must be region, city, or airport")
    places = reference_places(place_type, featured_only=featured if place_type == "city" else True)
    if country_code:
        places = tuple(item for item in places if item.country_code == country_code.upper())
    return list(places[:limit])


@router.get("/places/{place_type}/{code}", response_model=Place)
def get_place(place_type: str, code: str) -> Place:
    return place_or_404(place_type, code)


@router.get("/search", response_model=list[Country])
def search(q: str = Query(min_length=1, max_length=100)) -> list[Country]:
    query = q.casefold().strip()
    return [country for country in countries() if query in country.name.casefold() or query == country.code.casefold()][:30]


@router.get("/search-all", response_model=list[Place])
def search_all(q: str = Query(min_length=1, max_length=100), place_type: str | None = None) -> list[Place]:
    query = q.casefold().strip()
    types = [place_type] if place_type else ["country", "region", "city", "airport"]
    result: list[Place] = []
    for current_type in types:
        result.extend(item for item in reference_places(current_type) if query in item.name.casefold() or query == item.code.casefold())
        if len(result) >= 50:
            break
    return result[:50]


@router.get("/place-statuses", response_model=list[StatusResponse])
def list_statuses(session: Session = Depends(get_session)) -> list[PlaceStatus]:
    profile = default_profile(session)
    statuses = list(session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id)).all())
    # Backfill the parent country for region records created before automatic
    # parent tracking was enabled.
    existing = {(item.place_type, item.place_code) for item in statuses}
    changed = False
    for item in statuses:
        if item.place_type != PlaceType.region or item.status not in (PlaceStatusValue.visited, PlaceStatusValue.lived):
            continue
        region = place_or_404("region", item.place_code)
        if not region.country_code or (PlaceType.country, region.country_code) in existing:
            continue
        parent = PlaceStatus(profile_id=profile.id, place_type=PlaceType.country, place_code=region.country_code, status=item.status)
        session.add(parent)
        statuses.append(parent)
        existing.add((PlaceType.country, region.country_code))
        changed = True
    if changed:
        session.commit()
    return statuses


@router.put("/place-statuses/{place_type}/{place_code}", response_model=StatusResponse)
def upsert_status(place_type: str, place_code: str, payload: StatusUpsert, session: Session = Depends(get_session)) -> PlaceStatus:
    try:
        typed_place = PlaceType(place_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown place type")
    place = place_or_404(place_type, place_code)
    profile = default_profile(session)
    item = session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id, PlaceStatus.place_type == typed_place, PlaceStatus.place_code == place.code)).first()
    if item is None:
        item = PlaceStatus(profile_id=profile.id, place_type=typed_place, place_code=place.code, status=payload.status)
    item.status, item.first_visited_on, item.last_visited_on, item.notes = payload.status, payload.first_visited_on, payload.last_visited_on, payload.notes
    item.updated_at = datetime.now(UTC)
    session.add(item)
    # Regions and cities imply a country visit; airports remain independent.
    if typed_place in (PlaceType.region, PlaceType.city) and place.country_code and payload.status in (PlaceStatusValue.visited, PlaceStatusValue.lived):
        parent = session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id, PlaceStatus.place_type == PlaceType.country, PlaceStatus.place_code == place.country_code)).first()
        if parent is None:
            parent = PlaceStatus(profile_id=profile.id, place_type=PlaceType.country, place_code=place.country_code, status=payload.status)
        elif parent.status == PlaceStatusValue.planned or (payload.status == PlaceStatusValue.lived and parent.status == PlaceStatusValue.visited):
            parent.status = payload.status
        parent.updated_at = datetime.now(UTC)
        session.add(parent)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/place-statuses/{place_type}/{place_code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_status(place_type: str, place_code: str, session: Session = Depends(get_session)) -> Response:
    profile = default_profile(session)
    try:
        typed_place = PlaceType(place_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Unknown place type")
    item = session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id, PlaceStatus.place_type == typed_place, PlaceStatus.place_code == place_code)).first()
    if item:
        session.delete(item)
        session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/visits", response_model=list[VisitResponse])
def list_visits(session: Session = Depends(get_session)) -> list[Visit]:
    profile = default_profile(session)
    return list(session.exec(select(Visit).where(Visit.profile_id == profile.id).order_by(Visit.arrived_on.desc())).all())


@router.post("/visits", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
def create_visit(payload: VisitCreate, session: Session = Depends(get_session)) -> Visit:
    place = place_or_404(payload.place_type.value, payload.place_code)
    profile = default_profile(session)
    item = Visit(profile_id=profile.id, place_code=place.code, **payload.model_dump(exclude={"place_code"}))
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/visits/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_visit(visit_id: UUID, session: Session = Depends(get_session)) -> Response:
    item = session.get(Visit, visit_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/visits/{visit_id}", response_model=VisitResponse)
def update_visit(visit_id: UUID, payload: VisitCreate, session: Session = Depends(get_session)) -> Visit:
    item = session.get(Visit, visit_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Visit not found")
    place = place_or_404(payload.place_type.value, payload.place_code)
    item.place_type = payload.place_type
    item.place_code = place.code
    item.arrived_on = payload.arrived_on
    item.departed_on = payload.departed_on
    item.trip_id = payload.trip_id
    item.notes = payload.notes
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/trips", response_model=list[TripResponse])
def list_trips(session: Session = Depends(get_session)) -> list[TripResponse]:
    profile = default_profile(session)
    trips = session.exec(select(Trip).where(Trip.profile_id == profile.id).order_by(Trip.start_date.desc())).all()
    return [TripResponse.model_validate(trip).model_copy(update={"stops": [TripStopResponse.model_validate(stop) for stop in session.exec(select(TripStop).where(TripStop.trip_id == trip.id).order_by(TripStop.position)).all()]}) for trip in trips]


@router.post("/trips", response_model=TripResponse, status_code=status.HTTP_201_CREATED)
def create_trip(payload: TripCreate, session: Session = Depends(get_session)) -> Trip:
    profile = default_profile(session)
    item = Trip(profile_id=profile.id, **payload.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.patch("/trips/{trip_id}", response_model=TripResponse)
def update_trip(trip_id: UUID, payload: TripCreate, session: Session = Depends(get_session)) -> Trip:
    item = session.get(Trip, trip_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    item.name = payload.name
    item.start_date = payload.start_date
    item.end_date = payload.end_date
    item.status = payload.status
    item.notes = payload.notes
    item.updated_at = datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip(trip_id: UUID, session: Session = Depends(get_session)) -> Response:
    trip = session.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    session.exec(delete(TripStop).where(TripStop.trip_id == trip_id))
    session.delete(trip)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/trips/{trip_id}/stops", response_model=TripStopResponse, status_code=status.HTTP_201_CREATED)
def add_trip_stop(trip_id: UUID, payload: TripStopCreate, session: Session = Depends(get_session)) -> TripStop:
    if session.get(Trip, trip_id) is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    place = place_or_404(payload.place_type.value, payload.place_code)
    item = TripStop(trip_id=trip_id, place_code=place.code, **payload.model_dump(exclude={"place_code"}))
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/trips/{trip_id}/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip_stop(trip_id: UUID, stop_id: UUID, session: Session = Depends(get_session)) -> Response:
    item = session.get(TripStop, stop_id)
    if item is None or item.trip_id != trip_id:
        raise HTTPException(status_code=404, detail="Trip stop not found")
    session.delete(item)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/statistics/summary", response_model=Statistics)
def statistics(session: Session = Depends(get_session)) -> Statistics:
    profile = default_profile(session)
    statuses = session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id)).all()
    visits = session.exec(select(Visit).where(Visit.profile_id == profile.id)).all()
    trips = session.exec(select(Trip).where(Trip.profile_id == profile.id)).all()
    days = sum((visit.departed_on - visit.arrived_on).days + 1 for visit in visits if visit.arrived_on and visit.departed_on)
    visited = sum(item.place_type == PlaceType.country and item.status in (PlaceStatusValue.visited, PlaceStatusValue.lived) for item in statuses)
    lived = sum(item.place_type == PlaceType.country and item.status == PlaceStatusValue.lived for item in statuses)
    planned = sum(item.place_type == PlaceType.country and item.status == PlaceStatusValue.planned for item in statuses)
    regions = sum(item.place_type == PlaceType.region and item.status == PlaceStatusValue.visited for item in statuses)
    cities = sum(item.place_type == PlaceType.city and item.status == PlaceStatusValue.visited for item in statuses)
    airports = sum(item.place_type == PlaceType.airport and item.status == PlaceStatusValue.visited for item in statuses)
    total = len(countries())
    region_total = len(reference_places("region"))
    return Statistics(countries_visited=visited, countries_lived=lived, countries_planned=planned, recognized_countries=total, visited_percentage=round(visited / total * 100, 1), trips=len(trips), visits=len(visits), travel_days=days, regions_visited=regions, regions_total=region_total, regions_percentage=round(regions / region_total * 100, 1) if region_total else 0, cities_visited=cities, airports_visited=airports)


@router.get("/backups/export")
def export_backup(session: Session = Depends(get_session)) -> dict[str, Any]:
    profile = default_profile(session)
    return {"version": 1, "exported_at": datetime.now(UTC).isoformat(), "statuses": [item.model_dump(mode="json") for item in session.exec(select(PlaceStatus).where(PlaceStatus.profile_id == profile.id)).all()], "visits": [item.model_dump(mode="json") for item in session.exec(select(Visit).where(Visit.profile_id == profile.id)).all()], "trips": [item.model_dump(mode="json") for item in session.exec(select(Trip).where(Trip.profile_id == profile.id)).all()], "trip_stops": [item.model_dump(mode="json") for item in session.exec(select(TripStop)).all()]}


@router.post("/backups/import")
def import_backup(payload: dict[str, Any], session: Session = Depends(get_session)) -> dict[str, int]:
    if payload.get("version") != 1:
        raise HTTPException(status_code=400, detail="Unsupported backup version")
    profile = default_profile(session)
    session.exec(delete(TripStop))
    session.exec(delete(Visit).where(Visit.profile_id == profile.id))
    session.exec(delete(PlaceStatus).where(PlaceStatus.profile_id == profile.id))
    session.exec(delete(Trip).where(Trip.profile_id == profile.id))
    for raw in payload.get("statuses", []):
        item = dict(raw)
        status_item = PlaceStatus.model_validate(item)
        status_item.profile_id = profile.id
        session.add(status_item)
    for raw in payload.get("trips", []):
        item = dict(raw)
        item.pop("stops", None)
        trip_item = Trip.model_validate(item)
        trip_item.profile_id = profile.id
        session.add(trip_item)
    for raw in payload.get("visits", []):
        item = dict(raw)
        visit_item = Visit.model_validate(item)
        visit_item.profile_id = profile.id
        session.add(visit_item)
    for raw in payload.get("trip_stops", []):
        session.add(TripStop.model_validate(raw))
    session.commit()
    return {"statuses": len(payload.get("statuses", [])), "trips": len(payload.get("trips", [])), "visits": len(payload.get("visits", []))}

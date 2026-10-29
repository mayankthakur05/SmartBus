"""
SmartBus Recommender Module
Contains rule-based route-matching, schedule calculation, departure time window filtering,
fare lookup, and fastest-journey recommendation algorithms for the SmartBus system.
"""

import re
from typing import Dict, Any, List, Optional, Tuple


# ==============================================================================
# SCHEDULE DATA HANDLING & DOCUMENTATION
# ==============================================================================
# In the current MongoDB dataset schema (`stop_times` collection), timetable
# records store an `arrival_time` field (e.g. '08:15'). There is no separate
# `departure_time` column in the existing collection.
#
# ASSUMPTION DOCUMENTATION:
# For boarding and intermediate stations along an intercity route, the scheduled
# arrival time of the vehicle at that stop is used as the operational departure
# time proxy (the passenger boards at the scheduled arrival time).
#
# This logic is centralized in `get_stop_schedule_time()` and `calculate_journey_duration()`.
# If separate departure times are added to the database schema in the future,
# updating this helper will propagate throughout the entire recommendation pipeline.
# ==============================================================================

def get_stop_schedule_time(db, trip_id: str, stop_name: str, stop_id: Optional[str] = None) -> Optional[str]:
    """
    Centralized schedule lookup helper.
    Retrieves the scheduled time for a stop on a specific trip.
    Prevents duplicate double-counting by returning the first matching record.
    """
    query: Dict[str, Any] = {"trip_id": trip_id}
    if stop_name:
        query["stop_name"] = stop_name
    elif stop_id:
        query["stop_id"] = stop_id
    else:
        return None

    doc = db.stop_times.find_one(query)
    if doc and isinstance(doc.get("arrival_time"), str):
        t = doc["arrival_time"].strip()
        return t if t else None
    return None


def parse_time_to_minutes(time_str: Optional[str]) -> Optional[int]:
    """
    Safely parses either a 24-hour ('HH:MM', 'HH:MM:SS') or 12-hour ('H:MM AM/PM')
    time string into total minutes since midnight (0..1439).
    Returns None if missing, malformed, or unparseable.
    """
    if not time_str or not isinstance(time_str, str):
        return None
    time_str = time_str.strip().upper()

    # 1. Check 12-hour AM/PM format (e.g. '3:00 PM', '08:15 AM', '12:30 AM')
    match_12h = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(AM|PM)$", time_str)
    if match_12h:
        try:
            h = int(match_12h.group(1))
            m = int(match_12h.group(2))
            period = match_12h.group(4)
            if 1 <= h <= 12 and 0 <= m <= 59:
                if period == "AM":
                    h = 0 if h == 12 else h
                else:
                    h = 12 if h == 12 else h + 12
                return h * 60 + m
        except (ValueError, TypeError):
            return None
        return None

    # 2. Check 24-hour format (e.g. '15:00', '08:15', '23:59')
    match_24h = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", time_str)
    if match_24h:
        try:
            h = int(match_24h.group(1))
            m = int(match_24h.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m
        except (ValueError, TypeError):
            return None
        return None

    return None


def format_time_12h(time_input: Any) -> str:
    """
    Formats a time string ('15:00') or minutes integer (900) into
    readable 12-hour format ('3:00 PM').
    """
    if time_input is None:
        return "Time unavailable"

    if isinstance(time_input, str):
        mins = parse_time_to_minutes(time_input)
    elif isinstance(time_input, int):
        mins = time_input
    else:
        return "Time unavailable"

    if mins is None:
        return "Time unavailable"

    mins = mins % 1440
    hours_24 = mins // 60
    minutes = mins % 60
    period = "AM" if hours_24 < 12 else "PM"
    display_h = 12 if hours_24 in (0, 12) else (hours_24 if hours_24 < 12 else hours_24 - 12)
    return f"{display_h}:{minutes:02d} {period}"


def is_time_in_window(
    departure_time_str: Optional[str],
    window_start_str: str,
    window_minutes: int = 60
) -> bool:
    """
    Checks if `departure_time_str` falls within [window_start, window_start + window_minutes] inclusive.
    Correctly handles midnight wrap-around (e.g. 23:30 to 00:30).
    """
    dep_mins = parse_time_to_minutes(departure_time_str)
    start_mins = parse_time_to_minutes(window_start_str)

    if dep_mins is None or start_mins is None:
        return False

    end_mins = start_mins + window_minutes

    if end_mins < 1440:
        # Standard daytime window
        return start_mins <= dep_mins <= end_mins
    else:
        # Midnight wrap-around
        wrapped_end = end_mins % 1440
        return dep_mins >= start_mins or dep_mins <= wrapped_end


def calculate_journey_duration(departure_time: Optional[str], arrival_time: Optional[str]) -> Optional[int]:
    """
    Calculates journey duration in minutes between departure and arrival times.
    Safely handles missing times and overnight journeys when supported by the data.
    Never returns a negative duration.
    For daytime anomalies (e.g. midday departure with arrival time before departure),
    returns None to avoid fabricated values.
    """
    dep_mins = parse_time_to_minutes(departure_time)
    arr_mins = parse_time_to_minutes(arrival_time)

    if dep_mins is None or arr_mins is None:
        return None

    if arr_mins > dep_mins:
        return arr_mins - dep_mins

    if arr_mins < dep_mins:
        # Check if legitimate overnight journey spanning midnight (duration <= 12h)
        # and departing late evening (>= 18:00) or arriving early morning (<= 12:00)
        overnight_diff = 1440 - dep_mins + arr_mins
        if overnight_diff <= 720 and (dep_mins >= 1080 or arr_mins <= 720):
            return overnight_diff
        # Otherwise an uninterpretable or negative daytime schedule anomaly
        return None

    # arr_mins == dep_mins (0 mins for intercity transition is uninterpretable)
    return None


def format_duration(duration_minutes: Optional[int]) -> str:
    """Formats duration in minutes to human-readable string like '1h 20m' or '45 mins'."""
    if duration_minutes is None:
        return "Duration unavailable"
    if duration_minutes < 60:
        return f"{duration_minutes} mins"
    hours = duration_minutes // 60
    mins = duration_minutes % 60
    if mins == 0:
        return f"{hours}h"
    return f"{hours}h {mins}m"


def generate_recommendation_reason(
    stops_count: int,
    duration_mins: Optional[int],
    fare: Optional[float],
    bus_type: str,
    is_fastest: bool = False
) -> str:
    """
    Generates a transparent, rule-based explanation for why this bus matches
    and ranks well for the passenger's search criteria.
    """
    reasons = []

    if is_fastest:
        reasons.append("⚡ Fastest Journey")

    if stops_count == 0:
        reasons.append("Direct non-stop")
    elif stops_count == 1:
        reasons.append("Express (1 stop)")
    else:
        reasons.append(f"{stops_count} intermediate stops")

    if duration_mins is not None:
        reasons.append(f"approx. {format_duration(duration_mins)}")

    if fare is not None:
        reasons.append(f"₹{fare:.0f} fare")

    if bus_type:
        reasons.append(f"{bus_type}")

    if reasons:
        return " • ".join(reasons)
    return "Valid scheduled route matching travel direction"


def normalize_stop_name(name: str) -> str:
    """Strips whitespace for matching."""
    return name.strip() if name else ""


def find_stop_by_name(db, name: str) -> Optional[Dict[str, Any]]:
    """Looks up a stop document by normalized name."""
    clean_name = normalize_stop_name(name)
    if not clean_name:
        return None
    return db.stops.find_one({"stop_name": {"$regex": f"^{clean_name}$", "$options": "i"}})


def search_buses(
    db,
    source: str,
    destination: str,
    bus_type: Optional[str] = None,
    departure_time: Optional[str] = None,
    window_minutes: int = 60,
    sort_by: str = "recommended"
) -> Dict[str, Any]:
    """
    Core route-matching and recommendation engine.

    1. Validates that both stops exist and are different.
    2. Finds trips whose ordered route contains both stops in the correct direction.
    3. Handles intermediate-stop journeys seamlessly.
    4. Applies preferred departure time filter ([departure_time, departure_time + window_minutes]).
    5. Retrieves stop times and calculates journey duration safely.
    6. Identifies the fastest bus (minimum valid duration) and flags ties.
    7. Fetches exact fare for (source, destination, bus_type).
    8. Sorts and ranks results deterministically.
    """
    clean_src = normalize_stop_name(source)
    clean_dst = normalize_stop_name(destination)

    if not clean_src or not clean_dst:
        raise ValueError("Both source and destination stops must be provided.")

    if clean_src.lower() == clean_dst.lower():
        raise ValueError("Source and destination stops cannot be the same.")

    # 1. Validate stops in database
    src_doc = find_stop_by_name(db, clean_src)
    if not src_doc:
        raise ValueError(f"Origin stop '{clean_src}' was not found in the database.")

    dst_doc = find_stop_by_name(db, clean_dst)
    if not dst_doc:
        raise ValueError(f"Destination stop '{clean_dst}' was not found in the database.")

    canonical_src = src_doc["stop_name"]
    canonical_dst = dst_doc["stop_name"]

    # 2. Find route entries for canonical source and destination
    routes_src_cursor = db.routes.find({"stop_name": canonical_src})
    routes_src_map = {}
    for r in routes_src_cursor:
        seq = r.get("sequence")
        if isinstance(seq, int):
            routes_src_map[r.get("trip_id")] = r

    routes_dst_cursor = db.routes.find({"stop_name": canonical_dst})
    routes_dst_map = {}
    for r in routes_dst_cursor:
        seq = r.get("sequence")
        if isinstance(seq, int):
            routes_dst_map[r.get("trip_id")] = r

    # 3. Match candidate trips where source sequence < destination sequence
    candidate_trips = []
    for trip_id, src_route in routes_src_map.items():
        if trip_id in routes_dst_map:
            dst_route = routes_dst_map[trip_id]
            src_seq = src_route["sequence"]
            dst_seq = dst_route["sequence"]
            if src_seq < dst_seq:
                candidate_trips.append({
                    "trip_id": trip_id,
                    "src_seq": src_seq,
                    "dst_seq": dst_seq,
                    "src_stop_id": src_route.get("stop_id"),
                    "dst_stop_id": dst_route.get("stop_id")
                })

    # Prepare Bus Type Filter
    desired_bus_type = bus_type.strip() if bus_type else None
    if desired_bus_type and desired_bus_type.lower() in ("any", "all", ""):
        desired_bus_type = None

    # Prepare Departure Time Filter
    time_filter_active = False
    clean_dep_time = None
    window_start_mins = None
    window_end_mins = None

    if departure_time and departure_time.strip():
        parsed_mins = parse_time_to_minutes(departure_time.strip())
        if parsed_mins is not None:
            time_filter_active = True
            clean_dep_time = departure_time.strip()
            window_start_mins = parsed_mins
            window_end_mins = (parsed_mins + window_minutes) % 1440

    raw_candidates = []

    for item in candidate_trips:
        trip_id = item["trip_id"]
        src_seq = item["src_seq"]
        dst_seq = item["dst_seq"]

        # Fetch trip
        trip = db.trips.find_one({"trip_id": trip_id})
        if not trip:
            continue

        bus_id = trip.get("bus_id")
        if not bus_id:
            continue

        # Fetch bus
        bus = db.buses.find_one({"bus_id": bus_id})
        if not bus:
            continue

        actual_bus_type = bus.get("bus_type", "Standard")

        # Bus comfort filter
        if desired_bus_type and actual_bus_type.lower() != desired_bus_type.lower():
            continue

        # Fetch scheduled times at passenger's selected source and destination stops
        dep_time = get_stop_schedule_time(db, trip_id, canonical_src, item.get("src_stop_id"))
        arr_time = get_stop_schedule_time(db, trip_id, canonical_dst, item.get("dst_stop_id"))

        # TIME WINDOW FILTER:
        # Filter using the scheduled departure from the passenger's selected source stop!
        if time_filter_active:
            if not dep_time:
                # Bus has no schedule at source stop; cannot verify time window
                continue
            if not is_time_in_window(dep_time, clean_dep_time, window_minutes):
                # Outside the 1-hour window
                continue

        # Lookup exact fare
        fare_doc = db.fares.find_one({
            "source": canonical_src,
            "destination": canonical_dst,
            "bus_type": actual_bus_type
        })
        fare_val = fare_doc.get("fare") if fare_doc and isinstance(fare_doc.get("fare"), (int, float)) else None

        # Intermediate stops count
        intermediate_stops_count = max(0, dst_seq - src_seq - 1)

        # Retrieve intermediate stop names
        intermediate_routes = list(db.routes.find({
            "trip_id": trip_id,
            "sequence": {"$gt": src_seq, "$lt": dst_seq}
        }).sort("sequence", 1))
        intermediate_stops = [ir.get("stop_name") for ir in intermediate_routes if ir.get("stop_name")]

        # Calculate duration strictly between selected source and destination
        duration_minutes = calculate_journey_duration(dep_time, arr_time)
        duration_display = format_duration(duration_minutes)

        dep_minutes = parse_time_to_minutes(dep_time)
        fare_display = f"₹{fare_val:.0f}" if fare_val is not None else "Fare unavailable"

        raw_candidates.append({
            "trip_id": trip_id,
            "bus_id": bus_id,
            "bus_name": bus.get("bus_name", "Express Bus"),
            "operator": bus.get("operator", "State Transport"),
            "bus_type": actual_bus_type,
            "full_trip_source": trip.get("source", canonical_src),
            "full_trip_destination": trip.get("destination", canonical_dst),
            "direction": trip.get("direction", f"{trip.get('source')} to {trip.get('destination')}"),
            "source_stop": canonical_src,
            "destination_stop": canonical_dst,
            "source_sequence": src_seq,
            "destination_sequence": dst_seq,
            "departure_time": dep_time or "Time unavailable",
            "departure_time_12h": format_time_12h(dep_time),
            "arrival_time": arr_time or "Time unavailable",
            "arrival_time_12h": format_time_12h(arr_time),
            "departure_time_minutes": dep_minutes,
            "duration_minutes": duration_minutes,
            "duration_display": duration_display,
            "intermediate_stops_count": intermediate_stops_count,
            "intermediate_stops": intermediate_stops,
            "fare": fare_val,
            "fare_display": fare_display,
            "is_fastest": False  # Will be computed below
        })

    # FASTEST JOURNEY COMPUTATION:
    # Identify shortest calculated duration among all eligible matching buses
    valid_durations = [
        c["duration_minutes"] for c in raw_candidates if c["duration_minutes"] is not None
    ]
    min_duration = min(valid_durations) if valid_durations else None

    # Flag buses that achieve the minimum duration (handles ties cleanly)
    for c in raw_candidates:
        if min_duration is not None and c["duration_minutes"] == min_duration:
            c["is_fastest"] = True
        else:
            c["is_fastest"] = False

        c["recommendation_reason"] = generate_recommendation_reason(
            c["intermediate_stops_count"],
            c["duration_minutes"],
            c["fare"],
            c["bus_type"],
            c["is_fastest"]
        )

    # Ranking & Sorting Logic
    def sort_key(x):
        stops = x["intermediate_stops_count"]
        dur = x["duration_minutes"] if x["duration_minutes"] is not None else float("inf")
        fr = x["fare"] if x["fare"] is not None else float("inf")
        dep = x["departure_time_minutes"] if x["departure_time_minutes"] is not None else float("inf")
        is_fst = 0 if x["is_fastest"] else 1
        tid = x["trip_id"]

        if sort_by in ("fastest_journey", "shortest_journey"):
            # Shortest valid journey duration first; unavailable durations appear after valid durations
            return (dur, stops, fr, dep, tid)
        elif sort_by == "fewest_stops":
            return (stops, dur, fr, dep, tid)
        elif sort_by == "lowest_fare":
            return (fr, dur, stops, dep, tid)
        else:
            # Default: recommended
            # 1. Fastest option
            # 2. Fewer intermediate stops
            # 3. Shorter duration
            # 4. Lower fare
            # 5. Departure schedule
            # 6. Deterministic tie-breaker
            return (is_fst, stops, dur, fr, dep, tid)

    raw_candidates.sort(key=sort_key)

    # Build time filter response metadata
    time_filter_meta: Dict[str, Any] = {"applied": time_filter_active}
    if time_filter_active and clean_dep_time is not None:
        time_filter_meta.update({
            "selected_time": clean_dep_time,
            "selected_time_12h": format_time_12h(clean_dep_time),
            "window_start_mins": window_start_mins,
            "window_start_12h": format_time_12h(window_start_mins),
            "window_end_mins": window_end_mins,
            "window_end_12h": format_time_12h(window_end_mins),
            "window_minutes": window_minutes
        })

    return {
        "success": True,
        "source": canonical_src,
        "destination": canonical_dst,
        "bus_type_filter": desired_bus_type or "All",
        "time_filter": time_filter_meta,
        "fastest_duration_minutes": min_duration,
        "sort_by": sort_by,
        "total_results": len(raw_candidates),
        "results": raw_candidates
    }


def get_trip_route(
    db,
    trip_id: str,
    source: Optional[str] = None,
    destination: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves the ordered route stops for a trip.
    If source and destination are provided, returns only the stops
    between source and destination inclusive (journey-specific view).
    """
    trip = db.trips.find_one({"trip_id": trip_id})
    if not trip:
        raise ValueError(f"Trip '{trip_id}' not found.")

    bus = db.buses.find_one({"bus_id": trip.get("bus_id")})
    bus_type = bus.get("bus_type", "Standard") if bus else "Standard"

    routes = list(db.routes.find({"trip_id": trip_id}).sort("sequence", 1))
    if not routes:
        raise ValueError(f"No route found for trip '{trip_id}'.")

    # Stop times mapping
    stop_times_list = list(db.stop_times.find({"trip_id": trip_id}))
    st_map = {st.get("stop_name"): st.get("arrival_time") for st in stop_times_list}

    # If source and destination specified, slice the route
    start_seq = None
    end_seq = None

    if source and destination:
        clean_src = normalize_stop_name(source)
        clean_dst = normalize_stop_name(destination)
        for r in routes:
            if r.get("stop_name", "").lower() == clean_src.lower():
                start_seq = r.get("sequence")
            if r.get("stop_name", "").lower() == clean_dst.lower():
                end_seq = r.get("sequence")

    ordered_stops = []
    for r in routes:
        seq = r.get("sequence")
        if start_seq is not None and end_seq is not None:
            if seq < start_seq or seq > end_seq:
                continue

        stop_name = r.get("stop_name")
        arrival_time = st_map.get(stop_name, "Schedule unavailable")

        if start_seq is not None and seq == start_seq:
            role = "origin"
        elif end_seq is not None and seq == end_seq:
            role = "destination"
        else:
            role = "intermediate"

        ordered_stops.append({
            "sequence": seq,
            "stop_id": r.get("stop_id"),
            "stop_name": stop_name,
            "arrival_time": arrival_time,
            "arrival_time_12h": format_time_12h(arrival_time),
            "role": role
        })

    # Journey fare if source and destination provided
    journey_fare = None
    if source and destination:
        src_stop = find_stop_by_name(db, source)
        dst_stop = find_stop_by_name(db, destination)
        if src_stop and dst_stop:
            fdoc = db.fares.find_one({
                "source": src_stop["stop_name"],
                "destination": dst_stop["stop_name"],
                "bus_type": bus_type
            })
            if fdoc and isinstance(fdoc.get("fare"), (int, float)):
                journey_fare = fdoc.get("fare")

    return {
        "success": True,
        "trip_id": trip_id,
        "bus_id": trip.get("bus_id"),
        "bus_name": bus.get("bus_name") if bus else "Unknown Bus",
        "operator": bus.get("operator") if bus else "Unknown Operator",
        "bus_type": bus_type,
        "full_source": trip.get("source"),
        "full_destination": trip.get("destination"),
        "direction": trip.get("direction"),
        "journey_source": source,
        "journey_destination": destination,
        "journey_fare": journey_fare,
        "journey_fare_display": f"₹{journey_fare:.0f}" if journey_fare is not None else "Fare unavailable",
        "total_stops": len(ordered_stops),
        "stops": ordered_stops
    }

# SmartBus — Smart Intercity Bus Search & Recommendation System

SmartBus is a final-year Computer Science project delivering a robust, full-stack web application for intercity bus search, directional route-matching, departure time window filtering, and fastest-journey rule-based recommendation across Punjab transit corridors.

Unlike naive search tools that match only origin terminal to final destination terminal, **SmartBus evaluates the entire ordered stop sequence of each trip**. Passengers can search between any two intermediate stops (e.g., *LPU to Jalandhar* or *Phillaur to Beas*) and filter for buses departing within an hour of their preferred travel time, complete with exact ticket fares, scheduled journey durations, and stop sequences.

---

## 1. Project Overview & Key Highlights

- **Intermediate-Stop Route Slicing:** Discovers buses traversing the requested stops in correct chronological sequence (`sequence(Origin) < sequence(Destination)`).
- **1-Hour Preferred Departure Window:** Passengers can specify a preferred departure time (e.g. `3:00 PM`). SmartBus checks the bus's scheduled time at the **passenger's selected source stop** (not the trip's starting depot) and includes buses departing within $[T, T + 60\text{ mins}]$ inclusive.
- **Fastest Journey Recommendation:** Dynamically calculates journey duration ($\text{Arrival} - \text{Departure}$ between requested stops) and prominently highlights the **Fastest Journey** (including tied fastest options).
- **Directional Integrity:** Automatically rejects trips traveling in the reverse direction.
- **Transparent Rule-Based Ranking:** Deterministic ranking based on fastest duration, fewest stops, exact fares, and passenger comfort preference (AC vs. Non-AC).
- **Zero Hallucination / Academic Integrity:** Connects directly to local MongoDB collections. Fares and schedules are drawn from verified database records. Missing schedules or unmapped fares are labeled *"Unavailable"* rather than fabricated.
- **Negative Duration Protection & Overnight Support:** Daytime timetables and erroneous time entries are safely handled without producing negative duration displays, while overnight journeys spanning midnight are calculated accurately.
- **Interactive Journey Route Viewer:** Slices and displays only the stops within the passenger's boarding and drop-off journey segment.

---

## 2. Technology Stack

| Layer | Technologies |
|---|---|
| **Frontend** | HTML5, CSS3, Modern Vanilla JavaScript (ES6+), Fetch API, [Lucide Icons](https://lucide.dev) |
| **Backend** | Python 3.12 / 3.13, Flask 3.1 |
| **Database Driver** | PyMongo 4.19 |
| **Database** | MongoDB 8.3 (Local server at `mongodb://localhost:27017/smartbus`) |
| **Testing** | Pytest 9.1 (Comprehensive 27-test suite with in-memory mock isolation) |

---

## 3. Database Architecture & Collections

The application queries the local `smartbus` MongoDB database containing 6 relational-style collections:

| Collection | Role & Schema Fields |
|---|---|
| `stops` (9 docs) | Master registry of transit stations (`stop_id`, `stop_name`). Includes Ludhiana, Phillaur, Goraya, Phagwara, LPU, Jalandhar, Beas, Amritsar, and Batala. |
| `buses` (95 docs) | Fleet information (`bus_id`, `bus_name`, `operator`, `bus_type`). Comfort types: `AC` and `Non-AC`. |
| `trips` (95 docs) | Scheduled transit corridors (`trip_id`, `bus_id`, `source`, `destination`, `direction`). |
| `routes` (676 docs) | Ordered sequence of stops per trip (`trip_id`, `stop_id`, `stop_name`, `sequence`). Sequence numbers define traversal order (1 to 8). |
| `stop_times` (676 docs) | Published arrival schedule times (`trip_id`, `stop_id`, `stop_name`, `arrival_time`). Format: `HH:MM`. |
| `fares` (128 docs) | Exact point-to-point ticket prices (`source`, `destination`, `bus_type`, `fare`). |

### Schedule Data Handling Assumption (Viva Documentation)
In the current MongoDB dataset schema (`stop_times` collection), timetable entries provide an `arrival_time` field (e.g. `'08:15'`). There is no separate `departure_time` column in the database.
- **Assumption Used:** For intermediate boarding stations along an intercity corridor, the vehicle's scheduled arrival time at that station serves as the operational departure time proxy (the passenger boards at the scheduled arrival time).
- **Centralized Logic:** This assumption is isolated inside `get_stop_schedule_time()` and `calculate_journey_duration()` in `recommender.py`. If separate departure timestamps are added in the future, updating this single helper propagates throughout the application.

---

## 4. Recommendation & Filtering Algorithm

```
[Search Input: Source, Destination, Preferred Departure Time, Bus Type]
       │
       ▼
1. Route Compatibility & Direction Check
   - Must contain both stops in trip route
   - seq(Source) < seq(Destination)
   - Exclude reverse trips
       │
       ▼
2. 1-Hour Departure Time Window Check (if specified)
   - Lookup schedule at passenger's selected source stop
   - Qualifies if dep_time in [T, T + 60 mins] (inclusive)
   - Excludes trips lacking valid timetable at source stop
       │
       ▼
3. Bus Comfort Preference Filter
   - Match AC / Non-AC filter if specified by user
       │
       ▼
4. Journey Duration & Fastest Bus Computation
   - Duration = arr_time(Destination) - dep_time(Source)
   - Minimum valid duration identified among eligible buses
   - Buses matching minimum duration are flagged with is_fastest = True
       │
       ▼
5. Transparent Rationale Generation
   - Generates human-readable explanation (e.g. "⚡ Fastest Journey • Direct non-stop • approx. 20 mins • ₹20 fare")
       │
       ▼
6. Deterministic Multi-Criteria Sorting
   - Recommended (Default): Fastest option -> Fewest stops -> Shortest duration -> Lowest fare
   - Fastest Journey: Shortest valid duration first -> Fewest stops -> Lowest fare
   - Fewest Stops: Minimum intermediate stations -> Shortest duration -> Lowest fare
   - Lowest Fare: Most economical ticket price -> Fewest stops -> Shortest duration
```

---

## 5. Project Folder Structure

```
SmartBus/
├── config.py                      # Centralized configuration and environment loader
├── recommender.py                 # Pure business logic: route matching, time window, fastest bus ranking
├── app.py                         # Flask application factory, routes, and REST error handlers
├── requirements.txt               # Python dependencies
├── README.md                      # Complete system documentation & viva guide
├── .gitignore                     # Git ignore rules for venv, cache, and logs
│
├── templates/
│   └── index.html                 # Modern, accessible single-page web interface with time picker
│
├── static/
│   ├── css/
│   │   └── style.css              # Premium navy/teal theme, fastest-card highlights, responsive layout
│   └── js/
│       └── script.js              # Client-side controller, Fetch API integration, time filter handling
│
├── tests/
│   ├── test_recommendations.py    # Unit tests covering all 15 enhancement scenarios + edge cases
│   └── test_api_live.py           # Integration tests against live local MongoDB
│
└── [CSV Source Files]             # Preserved source data files (buses.csv, routes.csv, etc.)
```

---

## 6. Installation & Setup Instructions (Windows)

### Prerequisites
1. **Operating System:** Windows 10 or 11.
2. **Python:** Python 3.12 or 3.13 installed.
3. **MongoDB Server:** Installed and running locally on port 27017 (`mongodb://localhost:27017/`).
4. **SmartBus Database:** MongoDB database named `smartbus` loaded.

---

### Step 1: Open Project Directory
```powershell
cd C:\Users\DeLL\Desktop\SmartBus
```

---

### Step 2: Run Automated Tests
Execute the comprehensive test suite to confirm all 27 tests pass:

```powershell
python -m pytest -v
```

Expected output:
```
============================= 27 passed in 1.11s ==============================
```

---

### Step 3: Start the Flask Application
```powershell
python app.py
```

Console output:
```
=======================================================
  SmartBus Intercity Search & Recommendation System    
  Running on: http://127.0.0.1:5000                  
  Connected to MongoDB: 'smartbus'                     
=======================================================
```

---

### Step 4: Open in Web Browser
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 7. REST API Documentation

### Search Buses Endpoint
- **Endpoint:** `GET /api/search`
- **Query Parameters:**
  - `source` *(string, required)*: Origin station name (e.g., `LPU`).
  - `destination` *(string, required)*: Drop station name (e.g., `Jalandhar`).
  - `departure_time` *(string, optional)*: Preferred departure time (e.g. `15:00` or `3:00 PM`).
  - `window_minutes` *(int, optional, default: 60)*: Search window in minutes.
  - `bus_type` *(string, optional)*: `AC`, `Non-AC`, or `Any`.
  - `sort_by` *(string, optional)*: `recommended`, `fastest_journey`, `fewest_stops`, `lowest_fare`.

- **Sample Request:**
  `GET /api/search?source=LPU&destination=Jalandhar&departure_time=15:00&sort_by=fastest_journey`

- **Sample JSON Response:**
```json
{
  "success": true,
  "source": "LPU",
  "destination": "Jalandhar",
  "bus_type_filter": "All",
  "sort_by": "fastest_journey",
  "time_filter": {
    "applied": true,
    "selected_time": "15:00",
    "selected_time_12h": "3:00 PM",
    "window_start_mins": 900,
    "window_start_12h": "3:00 PM",
    "window_end_mins": 960,
    "window_end_12h": "4:00 PM",
    "window_minutes": 60
  },
  "fastest_duration_minutes": 20,
  "total_results": 6,
  "results": [
    {
      "trip_id": "T005",
      "bus_id": "B005",
      "bus_name": "Satluj",
      "operator": "Satluj Tour and Travels",
      "bus_type": "Non-AC",
      "source_stop": "LPU",
      "destination_stop": "Jalandhar",
      "departure_time": "15:15",
      "departure_time_12h": "3:15 PM",
      "arrival_time": "15:35",
      "arrival_time_12h": "3:35 PM",
      "duration_minutes": 20,
      "duration_display": "20 mins",
      "intermediate_stops_count": 0,
      "intermediate_stops": [],
      "fare": 20.0,
      "fare_display": "₹20",
      "is_fastest": true,
      "recommendation_reason": "⚡ Fastest Journey • Direct non-stop • approx. 20 mins • ₹20 fare • Non-AC"
    }
  ]
}
```

---

## 8. Verification & Test Suite Coverage

SmartBus includes automated test suites covering all required scenarios:

| Test ID | Scenario Tested | Outcome |
|---|---|---|
| `test_01` | Selected time 3:00 PM: a bus at 3:00 PM is included | PASSED |
| `test_02` | Selected time 3:00 PM: a bus at 3:30 PM is included | PASSED |
| `test_03` | Selected time 3:00 PM: a bus at 4:00 PM is included | PASSED |
| `test_04` | Selected time 3:00 PM: a bus at 2:59 PM is excluded | PASSED |
| `test_05` | Selected time 3:00 PM: a bus at 4:01 PM is excluded | PASSED |
| `test_06` | Selected source is an intermediate stop | PASSED |
| `test_07` | Selected destination is an intermediate stop | PASSED |
| `test_08` | Faster bus ranked ahead of slower bus in fastest_journey sort | PASSED |
| `test_09` | Two equally fast buses are both marked as tied fastest (`is_fastest: true`) | PASSED |
| `test_10` | Missing departure or arrival times handled safely with "Duration unavailable" | PASSED |
| `test_11` | Overnight journey spanning midnight calculated accurately | PASSED |
| `test_12` | AC and Non-AC comfort filters function alongside time filter | PASSED |
| `test_13` | Fare and stop-count sorting modes function correctly | PASSED |
| `test_14` | No matching bus in selected time window returns empty list without error | PASSED |
| `test_15` | No time selected returns all matching buses (preserving backwards compatibility) | PASSED |
| `test_api_live` | Health, stops, all-times, time filter, 12h format, and fastest sort on live DB | PASSED |

---

## 9. Final-Year Viva Talking Points

1. **Boarding Stop Departure vs. Trip Origin Depot:** Explain that when a passenger boards at *LPU* at 3:00 PM on a bus originating from *Ludhiana* at 2:15 PM, the system filters by the vehicle's arrival/departure at *LPU* (e.g. 3:15 PM), not the trip's starting depot time.
2. **Fastest Journey Identification:** Explain how minimum duration is computed dynamically for the queried segment ($T_{arr} - T_{dep}$), highlighting tied fastest options without suppressing other matching buses.
3. **Transparent Rule-Based Logic:** Emphasize that no black-box machine learning or fabricated percentages are used; every recommendation reason is directly traceable to timetable and fare records in MongoDB.

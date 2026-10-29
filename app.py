"""
SmartBus — Flask Application Entry Point
Web backend exposing REST APIs and serving the passenger search frontend.
"""

import os
import sys
from flask import Flask, render_template, request, jsonify
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ConnectionFailure

from config import Config
from recommender import search_buses, get_trip_route, find_stop_by_name

# Initialize Flask App
app = Flask(__name__)
app.config.from_object(Config)

# MongoDB Client Setup (reused across requests)
try:
    mongo_client = MongoClient(app.config["MONGO_URI"], serverSelectionTimeoutMS=3000)
    db = mongo_client[app.config["MONGO_DB_NAME"]]
    mongo_client.admin.command("ping")
    print(f"[SmartBus] Successfully connected to MongoDB at {app.config['MONGO_URI']} (DB: {app.config['MONGO_DB_NAME']})")
except ConnectionFailure as err:
    print(f"[SmartBus WARNING] Could not connect to MongoDB: {err}", file=sys.stderr)
    db = None


def get_db():
    """Returns the active MongoDB database instance or None if unavailable."""
    return db


# ==============================================================================
# HTML ROUTES
# ==============================================================================
@app.route("/")
def index():
    """Serves the main SmartBus single-page web application."""
    return render_template("index.html")


# ==============================================================================
# API ENDPOINTS
# ==============================================================================
@app.route("/api/health", methods=["GET"])
def health_check():
    """
    Application health status and MongoDB connectivity check.
    Does not expose sensitive credentials.
    """
    current_db = get_db()
    if current_db is None:
        return jsonify({
            "status": "degraded",
            "database": {
                "connected": False,
                "message": "Database client failed to connect."
            }
        }), 503

    try:
        current_db.client.admin.command("ping")
        counts = {
            "buses": current_db.buses.count_documents({}),
            "trips": current_db.trips.count_documents({}),
            "stops": current_db.stops.count_documents({}),
            "routes": current_db.routes.count_documents({}),
            "stop_times": current_db.stop_times.count_documents({}),
            "fares": current_db.fares.count_documents({})
        }
        return jsonify({
            "status": "healthy",
            "database": {
                "connected": True,
                "name": current_db.name,
                "document_counts": counts
            }
        }), 200
    except PyMongoError:
        return jsonify({
            "status": "unhealthy",
            "database": {
                "connected": False,
                "error": "Database ping failed."
            }
        }), 500


@app.route("/api/stops", methods=["GET"])
def get_stops():
    """
    Returns the real list of stops from MongoDB.
    Sorted in logical route order (S001, S002, ...) or alphabetically.
    """
    current_db = get_db()
    if current_db is None:
        return jsonify({"success": False, "error": "Database unavailable."}), 503

    try:
        stops_cursor = current_db.stops.find({}, {"_id": 0, "stop_id": 1, "stop_name": 1}).sort("stop_id", 1)
        stops = list(stops_cursor)
        return jsonify({
            "success": True,
            "total": len(stops),
            "stops": stops
        }), 200
    except PyMongoError:
        return jsonify({"success": False, "error": "Failed to retrieve stops."}), 500


@app.route("/api/bus-types", methods=["GET"])
def get_bus_types():
    """Returns the list of supported bus types derived from actual records."""
    current_db = get_db()
    if current_db is None:
        return jsonify({"success": False, "error": "Database unavailable."}), 503

    try:
        types = current_db.buses.distinct("bus_type")
        types = [t for t in types if t]
        return jsonify({
            "success": True,
            "bus_types": ["Any"] + sorted(types)
        }), 200
    except PyMongoError:
        return jsonify({"success": False, "error": "Failed to retrieve bus types."}), 500


@app.route("/api/search", methods=["GET"])
def search():
    """
    Search buses between source and destination stops.
    Accepts:
    - source (required)
    - destination (required)
    - bus_type (optional: AC, Non-AC, Any)
    - departure_time (optional: e.g. 15:00 or 3:00 PM)
    - window_minutes (optional, default 60)
    - sort_by (optional: recommended, fastest_journey, fewest_stops, lowest_fare)
    """
    current_db = get_db()
    if current_db is None:
        return jsonify({"success": False, "error": "Database unavailable."}), 503

    source = request.args.get("source", "").strip()
    destination = request.args.get("destination", "").strip()
    bus_type = request.args.get("bus_type", "").strip()
    departure_time = request.args.get("departure_time", "").strip() or None
    sort_by = request.args.get("sort_by", "recommended").strip().lower()

    # Parse window_minutes
    try:
        window_minutes = int(request.args.get("window_minutes", 60))
        if window_minutes <= 0 or window_minutes > 1440:
            window_minutes = 60
    except (ValueError, TypeError):
        window_minutes = 60

    if not source or not destination:
        return jsonify({
            "success": False,
            "error": "Both origin (source) and destination stops must be selected."
        }), 400

    if source.lower() == destination.lower():
        return jsonify({
            "success": False,
            "error": "Source and destination cannot be the same stop. Please choose different stops."
        }), 400

    # Map shortest_journey to fastest_journey alias
    if sort_by == "shortest_journey":
        sort_by = "fastest_journey"

    valid_sorts = ("recommended", "fastest_journey", "fewest_stops", "lowest_fare")
    if sort_by not in valid_sorts:
        sort_by = "recommended"

    try:
        search_result = search_buses(
            db=current_db,
            source=source,
            destination=destination,
            bus_type=bus_type,
            departure_time=departure_time,
            window_minutes=window_minutes,
            sort_by=sort_by
        )
        return jsonify(search_result), 200
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 400
    except PyMongoError:
        return jsonify({
            "success": False,
            "error": "A database error occurred while querying bus schedules. Please try again."
        }), 500
    except Exception as ex:
        return jsonify({
            "success": False,
            "error": "An unexpected server error occurred."
        }), 500


@app.route("/api/route/<trip_id>", methods=["GET"])
def get_route(trip_id: str):
    """
    Returns ordered route stops for a specific trip.
    If 'source' and 'destination' query parameters are passed,
    only the journey-specific route segment (between source and destination)
    is returned.
    """
    current_db = get_db()
    if current_db is None:
        return jsonify({"success": False, "error": "Database unavailable."}), 503

    source = request.args.get("source", "").strip() or None
    destination = request.args.get("destination", "").strip() or None

    try:
        route_info = get_trip_route(
            db=current_db,
            trip_id=trip_id,
            source=source,
            destination=destination
        )
        return jsonify(route_info), 200
    except ValueError as val_err:
        return jsonify({"success": False, "error": str(val_err)}), 404
    except PyMongoError:
        return jsonify({"success": False, "error": "Database error while fetching route details."}), 500
    except Exception:
        return jsonify({"success": False, "error": "Failed to load route details."}), 500


# ==============================================================================
# ERROR HANDLERS
# ==============================================================================
@app.errorhandler(404)
def not_found_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "API endpoint not found."}), 404
    return render_template("index.html"), 404


@app.errorhandler(500)
def internal_error_handler(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Internal server error."}), 500
    return "<h1>500 Internal Server Error</h1><p>SmartBus encountered an issue.</p>", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n=======================================================")
    print(f"  SmartBus Intercity Search & Recommendation System    ")
    print(f"  Running on: http://127.0.0.1:{port}                  ")
    print(f"  Connected to MongoDB: 'smartbus'                     ")
    print(f"=======================================================\n")
    app.run(host="127.0.0.1", port=port, debug=True)

import streamlit as st

# Must be the first Streamlit command
st.set_page_config(
    page_title="🛫 Airline Support Agent",
    page_icon="✈️",
    layout="wide"
)

import os
import time
import json
import uuid
import random
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from openai import OpenAI
from cleanlab_codex.client import Client as CleanlabClient

# Load environment variables
load_dotenv()

# SECURE: Use Streamlit secrets or environment variables
def get_api_keys():
    """Securely retrieve API keys from Streamlit secrets or environment variables"""
    try:
        # Try Streamlit secrets first (for Streamlit Cloud deployment)
        openai_key = st.secrets.get("OPENAI_API_KEY")
        codex_key = st.secrets.get("CODEX_API_KEY")
        project_id = st.secrets.get("CLEANLAB_PROJECT_ID")
    except:
        # Fallback to environment variables (for local development)
        openai_key = os.getenv("OPENAI_API_KEY")
        codex_key = os.getenv("CODEX_API_KEY")
        project_id = os.getenv("CLEANLAB_PROJECT_ID")
    
    return openai_key, codex_key, project_id

# Get API keys securely
OPENAI_API_KEY, CODEX_API_KEY, CLEANLAB_PROJECT_ID = get_api_keys()

# Validate that required keys are present
if not OPENAI_API_KEY:
    st.error("🚨 **Missing OpenAI API Key!** Please set OPENAI_API_KEY in your secrets or environment variables.")
    st.stop()

if not CODEX_API_KEY:
    st.warning("⚠️ **Missing Codex API Key!** Cleanlab validation will be disabled.")

# Set environment variables securely (only if keys exist)
if CODEX_API_KEY:
    os.environ["CODEX_API_KEY"] = CODEX_API_KEY
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Use default project ID if not provided
CLEANLAB_PROJECT_ID = CLEANLAB_PROJECT_ID or None

if not CLEANLAB_PROJECT_ID:
    st.warning("⚠️ **Missing Cleanlab Project ID!** Cleanlab validation will be disabled.")

# Initialize Cleanlab client (with error handling)
@st.cache_resource
def get_cleanlab_client():
    try:
        cl_client = CleanlabClient()
        return cl_client.get_project(CLEANLAB_PROJECT_ID)
    except Exception as e:
        st.warning(f"⚠️ Cleanlab client initialization failed: {str(e)}")
        return None

cl_project = get_cleanlab_client()

# EXPANDED TOOLS - Much more comprehensive airline support
tools = [
    # Flight Search Tools
    {
        "type": "function",
        "function": {
            "name": "search_one_way",
            "description": "Search for one-way flights between airports",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin airport IATA code (e.g., SFO)"},
                    "destination": {"type": "string", "description": "Destination airport IATA code (e.g., LAX)"},
                    "date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "class": {"type": "string", "description": "Cabin class: economy, business, first", "enum": ["economy", "business", "first"]},
                    "passengers": {"type": "integer", "description": "Number of passengers (default: 1)"}
                },
                "required": ["origin", "destination", "date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_round_trip",
            "description": "Search for round-trip flights",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "Origin airport IATA code"},
                    "destination": {"type": "string", "description": "Destination airport IATA code"},
                    "depart_date": {"type": "string", "description": "Departure date in YYYY-MM-DD format"},
                    "return_date": {"type": "string", "description": "Return date in YYYY-MM-DD format"},
                    "class": {"type": "string", "description": "Cabin class: economy, business, first"},
                    "passengers": {"type": "integer", "description": "Number of passengers"}
                },
                "required": ["origin", "destination", "depart_date", "return_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_multi_city",
            "description": "Search for multi-city flights with multiple stops",
            "parameters": {
                "type": "object",
                "properties": {
                    "segments": {
                        "type": "array", 
                        "description": "Array of flight segments with origin, destination, and date",
                        "items": {
                            "type": "object",
                            "properties": {
                                "origin": {"type": "string", "description": "Origin airport IATA code"},
                                "destination": {"type": "string", "description": "Destination airport IATA code"},
                                "date": {"type": "string", "description": "Flight date in YYYY-MM-DD format"}
                            },
                            "required": ["origin", "destination", "date"]
                        }
                    },
                    "class": {"type": "string", "description": "Cabin class preference"},
                    "passengers": {"type": "integer", "description": "Number of passengers"}
                },
                "required": ["segments"]
            }
        }
    },
    
    # Flight Status & Information
    {
        "type": "function",
        "function": {
            "name": "check_flight_status",
            "description": "Check real-time flight status by flight number",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string", "description": "Flight number (e.g., AA123, DL456)"},
                    "date": {"type": "string", "description": "Flight date in YYYY-MM-DD format (optional)"}
                },
                "required": ["flight_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_flight_details",
            "description": "Get detailed information about a specific flight",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string", "description": "Flight number"},
                    "date": {"type": "string", "description": "Flight date"}
                },
                "required": ["flight_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_flight_route",
            "description": "Get flight path and tracking information",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string", "description": "Flight number to track"},
                    "date": {"type": "string", "description": "Flight date"}
                },
                "required": ["flight_number"]
            }
        }
    },
    
    # Booking Management
    {
        "type": "function",
        "function": {
            "name": "retrieve_booking",
            "description": "Retrieve booking details using confirmation number",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "last_name": {"type": "string", "description": "Passenger's last name"}
                },
                "required": ["confirmation_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "modify_booking",
            "description": "Modify an existing booking (change dates, upgrade, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "modification_type": {"type": "string", "description": "Type of change: date_change, seat_upgrade, meal_preference", "enum": ["date_change", "seat_upgrade", "meal_preference", "add_baggage"]},
                    "new_date": {"type": "string", "description": "New flight date (for date changes)"},
                    "upgrade_class": {"type": "string", "description": "New cabin class (for upgrades)"}
                },
                "required": ["confirmation_number", "modification_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_booking",
            "description": "Cancel a flight booking and calculate refund",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "reason": {"type": "string", "description": "Cancellation reason"}
                },
                "required": ["confirmation_number"]
            }
        }
    },
    
    # Seat Management
    {
        "type": "function",
        "function": {
            "name": "get_seat_map",
            "description": "Get seat map and availability for a specific flight",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string", "description": "Flight number"},
                    "date": {"type": "string", "description": "Flight date"},
                    "class": {"type": "string", "description": "Cabin class to view"}
                },
                "required": ["flight_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "select_seat",
            "description": "Select or change seat assignment",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "seat_number": {"type": "string", "description": "Desired seat number (e.g., 12A)"},
                    "passenger_name": {"type": "string", "description": "Passenger name for seat assignment"}
                },
                "required": ["confirmation_number", "seat_number"]
            }
        }
    },
    
    # Baggage Services
    {
        "type": "function",
        "function": {
            "name": "check_baggage_allowance",
            "description": "Check baggage allowance and fees for a route or booking",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "description": "Route (e.g., SFO-LAX) or confirmation number"},
                    "ticket_type": {"type": "string", "description": "Ticket type: economy, business, first"},
                    "frequent_flyer_status": {"type": "string", "description": "FF status: none, silver, gold, platinum"}
                },
                "required": ["route"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "track_baggage",
            "description": "Track checked baggage location and status",
            "parameters": {
                "type": "object",
                "properties": {
                    "baggage_tag": {"type": "string", "description": "Baggage tag number"},
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"}
                },
                "required": ["baggage_tag"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_baggage_issue",
            "description": "Report lost, delayed, or damaged baggage",
            "parameters": {
                "type": "object",
                "properties": {
                    "issue_type": {"type": "string", "description": "Issue type: lost, delayed, damaged", "enum": ["lost", "delayed", "damaged"]},
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "description": {"type": "string", "description": "Description of the issue"},
                    "contact_info": {"type": "string", "description": "Contact information for follow-up"}
                },
                "required": ["issue_type", "confirmation_number"]
            }
        }
    },
    
    # Airport Services
    {
        "type": "function",
        "function": {
            "name": "get_airport_info",
            "description": "Get airport information, facilities, and services",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "Airport IATA code (e.g., JFK, LAX)"},
                    "info_type": {"type": "string", "description": "Type of info: facilities, transportation, lounges, dining", "enum": ["facilities", "transportation", "lounges", "dining", "general"]}
                },
                "required": ["airport_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_security_wait_times",
            "description": "Get current security checkpoint wait times",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "Airport IATA code"},
                    "terminal": {"type": "string", "description": "Terminal number/letter (optional)"}
                },
                "required": ["airport_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_airport_services",
            "description": "Find specific services at an airport (restaurants, shops, ATMs, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "Airport IATA code"},
                    "service_type": {"type": "string", "description": "Service type: dining, shopping, banking, medical, wifi"},
                    "terminal": {"type": "string", "description": "Specific terminal (optional)"}
                },
                "required": ["airport_code", "service_type"]
            }
        }
    },
    
    # Frequent Flyer & Loyalty
    {
        "type": "function",
        "function": {
            "name": "check_miles_balance",
            "description": "Check frequent flyer miles balance and status",
            "parameters": {
                "type": "object",
                "properties": {
                    "frequent_flyer_number": {"type": "string", "description": "FF program member number"},
                    "program": {"type": "string", "description": "Loyalty program name"}
                },
                "required": ["frequent_flyer_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "redeem_miles",
            "description": "Redeem miles for flights or upgrades",
            "parameters": {
                "type": "object",
                "properties": {
                    "frequent_flyer_number": {"type": "string", "description": "FF program member number"},
                    "redemption_type": {"type": "string", "description": "Redemption type: flight, upgrade, merchandise"},
                    "flight_details": {"type": "string", "description": "Flight details for redemption"},
                    "miles_to_redeem": {"type": "integer", "description": "Number of miles to redeem"}
                },
                "required": ["frequent_flyer_number", "redemption_type"]
            }
        }
    },
    
    # Special Services
    {
        "type": "function",
        "function": {
            "name": "request_special_assistance",
            "description": "Request special assistance (wheelchair, medical, dietary, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "assistance_type": {"type": "string", "description": "Type: wheelchair, medical_oxygen, dietary, pet_travel, unaccompanied_minor"},
                    "details": {"type": "string", "description": "Specific requirements or details"},
                    "passenger_name": {"type": "string", "description": "Passenger requiring assistance"}
                },
                "required": ["confirmation_number", "assistance_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_lounge_access",
            "description": "Book airport lounge access",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "Airport IATA code"},
                    "lounge_name": {"type": "string", "description": "Specific lounge name (optional)"},
                    "date": {"type": "string", "description": "Access date"},
                    "duration": {"type": "integer", "description": "Hours of access needed"},
                    "guests": {"type": "integer", "description": "Number of guests"}
                },
                "required": ["airport_code", "date"]
            }
        }
    },
    
    # Weather & Disruptions
    {
        "type": "function",
        "function": {
            "name": "check_weather_impact",
            "description": "Check weather conditions and potential flight impacts",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "Airport IATA code"},
                    "date": {"type": "string", "description": "Date to check weather"},
                    "flight_number": {"type": "string", "description": "Specific flight number (optional)"}
                },
                "required": ["airport_code"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_disruption_alerts",
            "description": "Get current flight disruptions and alerts",
            "parameters": {
                "type": "object",
                "properties": {
                    "airport_code": {"type": "string", "description": "Airport code to check"},
                    "airline": {"type": "string", "description": "Specific airline (optional)"},
                    "severity": {"type": "string", "description": "Alert severity: low, medium, high"}
                },
                "required": ["airport_code"]
            }
        }
    },
    
    # Pricing & Fare Information
    {
        "type": "function",
        "function": {
            "name": "get_fare_rules",
            "description": "Get fare rules and restrictions for a ticket",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "fare_class": {"type": "string", "description": "Fare class code"}
                },
                "required": ["confirmation_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "compare_upgrade_options",
            "description": "Compare available upgrade options and pricing",
            "parameters": {
                "type": "object",
                "properties": {
                    "confirmation_number": {"type": "string", "description": "Booking confirmation number"},
                    "target_class": {"type": "string", "description": "Desired upgrade class"},
                    "payment_method": {"type": "string", "description": "Payment method: cash, miles, points"}
                },
                "required": ["confirmation_number"]
            }
        }
    }
]

# EXPANDED TOOL IMPLEMENTATIONS with dynamic fake data
def search_one_way(origin: str, destination: str, date: str, class_type: str = "economy", passengers: int = 1) -> dict:
    """Enhanced one-way search with realistic variable data"""
    airlines = ["AA", "DL", "UA", "WN", "B6", "AS", "F9", "NK"]
    aircraft_types = ["Boeing 737", "Airbus A320", "Boeing 777", "Airbus A350", "Boeing 787"]
    
    # Generate 2-4 flight options
    flights = []
    for i in range(random.randint(2, 4)):
        airline = random.choice(airlines)
        flight_num = f"{airline}{random.randint(100, 9999)}"
        
        # Realistic pricing based on class
        base_price = random.randint(200, 800)
        if class_type == "business":
            base_price *= random.uniform(2.5, 4.0)
        elif class_type == "first":
            base_price *= random.uniform(4.0, 8.0)
        
        # Generate realistic times
        dep_hour = random.randint(6, 22)
        duration_hours = random.uniform(1.5, 6.0)
        arr_hour = (dep_hour + duration_hours) % 24
        
        flights.append({
            "flight_number": flight_num,
            "airline": airline,
            "origin": origin,
            "destination": destination,
            "date": date,
            "departure_time": f"{dep_hour:02d}:{random.randint(0, 59):02d}",
            "arrival_time": f"{int(arr_hour):02d}:{random.randint(0, 59):02d}",
            "duration": f"{int(duration_hours)}h {int((duration_hours % 1) * 60)}m",
            "aircraft": random.choice(aircraft_types),
            "price_usd": round(base_price * passengers, 2),
            "seats_available": random.randint(5, 50),
            "class": class_type,
            "stops": random.choice([0, 0, 0, 1]),  # Mostly non-stop
            "baggage_included": random.choice([True, False]),
            "wifi_available": random.choice([True, False]),
            "meal_service": class_type != "economy" or random.choice([True, False])
        })
    
    return {"flights": flights, "search_params": {"origin": origin, "destination": destination, "date": date, "passengers": passengers}}

def search_round_trip(origin: str, destination: str, depart_date: str, return_date: str, class_type: str = "economy", passengers: int = 1) -> dict:
    """Enhanced round-trip search"""
    outbound = search_one_way(origin, destination, depart_date, class_type, passengers)["flights"]
    inbound = search_one_way(destination, origin, return_date, class_type, passengers)["flights"]
    
    # Calculate package savings
    total_one_way = sum(f["price_usd"] for f in outbound[:1] + inbound[:1])
    package_discount = random.uniform(0.05, 0.15)  # 5-15% savings
    package_price = total_one_way * (1 - package_discount)
    
    return {
        "outbound": outbound,
        "inbound": inbound,
        "package_deals": {
            "total_price": round(package_price, 2),
            "savings": round(total_one_way - package_price, 2),
            "discount_percent": round(package_discount * 100, 1)
        }
    }

def search_multi_city(segments: list, class_type: str = "economy", passengers: int = 1) -> dict:
    """Multi-city flight search"""
    all_segments = []
    total_price = 0
    
    for i, segment in enumerate(segments):
        origin = segment.get("origin", "NYC")
        destination = segment.get("destination", "LAX") 
        date = segment.get("date", "2025-04-01")
        
        flights = search_one_way(origin, destination, date, class_type, passengers)["flights"]
        best_flight = min(flights, key=lambda x: x["price_usd"])
        
        all_segments.append({
            "segment_number": i + 1,
            "flight": best_flight
        })
        total_price += best_flight["price_usd"]
    
    return {
        "segments": all_segments,
        "total_price": round(total_price, 2),
        "total_duration": f"{len(segments) * random.randint(3, 8)}h {random.randint(0, 59)}m"
    }

def check_flight_status(flight_number: str, date: str = None) -> dict:
    """Enhanced flight status with more realistic data"""
    statuses = ["On Time", "Delayed", "Cancelled", "Boarding", "Departed", "Arrived", "Diverted"]
    delays = [0, 15, 30, 45, 60, 90, 120, 180]
    
    status = random.choice(statuses)
    delay = random.choice(delays) if status == "Delayed" else 0
    
    # Generate realistic airport codes and gates
    airports = ["JFK", "LAX", "ORD", "DFW", "ATL", "SFO", "LAS", "SEA", "MIA", "BOS"]
    origin = random.choice(airports)
    destination = random.choice([a for a in airports if a != origin])
    
    current_time = datetime.now()
    scheduled_dep = current_time + timedelta(hours=random.randint(1, 12))
    actual_dep = scheduled_dep + timedelta(minutes=delay)
    
    return {
        "flight_number": flight_number,
        "status": status,
        "origin": origin,
        "destination": destination,
        "scheduled_departure": scheduled_dep.strftime("%H:%M"),
        "actual_departure": actual_dep.strftime("%H:%M") if delay > 0 else None,
        "delay_minutes": delay,
        "gate": f"{random.choice(['A', 'B', 'C', 'D'])}{random.randint(1, 50)}",
        "terminal": random.choice(["1", "2", "3", "North", "South"]),
        "aircraft": random.choice(["Boeing 737-800", "Airbus A320", "Boeing 777-200"]),
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "boarding_time": (scheduled_dep - timedelta(minutes=30)).strftime("%H:%M"),
        "estimated_arrival": (actual_dep + timedelta(hours=random.randint(2, 6))).strftime("%H:%M")
    }

def get_flight_details(flight_number: str, date: str = None) -> dict:
    """Detailed flight information"""
    status_info = check_flight_status(flight_number, date)
    
    return {
        **status_info,
        "aircraft_details": {
            "type": status_info["aircraft"],
            "registration": f"N{random.randint(100, 999)}{random.choice(['AA', 'DL', 'UA'])}",
            "age": f"{random.randint(2, 15)} years",
            "seat_configuration": {
                "first": random.randint(8, 16),
                "business": random.randint(20, 40),
                "economy": random.randint(120, 180)
            }
        },
        "route_info": {
            "distance": f"{random.randint(500, 3000)} miles",
            "flight_time": f"{random.randint(2, 8)}h {random.randint(0, 59)}m",
            "altitude": f"{random.randint(35, 42)}000 ft",
            "speed": f"{random.randint(450, 580)} mph"
        },
        "services": {
            "wifi": random.choice([True, False]),
            "entertainment": random.choice([True, False]),
            "meal_service": random.choice([True, False]),
            "power_outlets": random.choice([True, False])
        }
    }

def track_flight_route(flight_number: str, date: str = None) -> dict:
    """Flight tracking and route information"""
    waypoints = ["DEPARTURE", "CLIMB", "CRUISE", "DESCENT", "APPROACH", "ARRIVAL"]
    current_phase = random.choice(waypoints)
    
    return {
        "flight_number": flight_number,
        "current_status": current_phase,
        "current_location": {
            "latitude": round(random.uniform(25.0, 50.0), 4),
            "longitude": round(random.uniform(-125.0, -70.0), 4),
            "altitude": f"{random.randint(35, 42)}000 ft",
            "speed": f"{random.randint(450, 580)} mph",
            "heading": f"{random.randint(0, 359)}°"
        },
        "progress": {
            "percent_complete": random.randint(0, 100),
            "time_remaining": f"{random.randint(0, 8)}h {random.randint(0, 59)}m",
            "distance_remaining": f"{random.randint(0, 2000)} miles"
        },
        "weather_conditions": {
            "turbulence": random.choice(["None", "Light", "Moderate"]),
            "visibility": f"{random.randint(5, 10)} miles",
            "wind_speed": f"{random.randint(10, 50)} mph"
        }
    }

def retrieve_booking(confirmation_number: str, last_name: str = None) -> dict:
    """Retrieve booking details"""
    passenger_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis"]
    first_names = ["John", "Jane", "Michael", "Sarah", "David", "Emily", "Robert", "Lisa"]
    
    passengers = []
    num_passengers = random.randint(1, 4)
    for i in range(num_passengers):
        passengers.append({
            "name": f"{random.choice(first_names)} {random.choice(passenger_names)}",
            "seat": f"{random.randint(10, 30)}{random.choice(['A', 'B', 'C', 'D', 'E', 'F'])}",
            "frequent_flyer": f"FF{random.randint(100000, 999999)}" if random.choice([True, False]) else None,
            "special_meal": random.choice([None, "Vegetarian", "Kosher", "Halal", "Gluten-Free"])
        })
    
    booking_date = datetime.now() - timedelta(days=random.randint(1, 90))
    flight_date = datetime.now() + timedelta(days=random.randint(1, 60))
    
    return {
        "confirmation_number": confirmation_number,
        "booking_status": random.choice(["Confirmed", "Pending", "Cancelled"]),
        "booking_date": booking_date.strftime("%Y-%m-%d"),
        "passengers": passengers,
        "flights": [
            {
                "flight_number": f"{random.choice(['AA', 'DL', 'UA'])}{random.randint(100, 9999)}",
                "date": flight_date.strftime("%Y-%m-%d"),
                "route": f"{random.choice(['JFK', 'LAX', 'ORD'])} → {random.choice(['SFO', 'MIA', 'SEA'])}",
                "class": random.choice(["Economy", "Business", "First"]),
                "status": "Confirmed"
            }
        ],
        "total_price": round(random.uniform(300, 2000), 2),
        "payment_status": "Paid",
        "baggage": {
            "checked": random.randint(0, 2),
            "carry_on": random.randint(1, 2)
        },
        "contact_info": {
            "email": "passenger@example.com",
            "phone": f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
        }
    }

def modify_booking(confirmation_number: str, modification_type: str, new_date: str = None, upgrade_class: str = None) -> dict:
    """Modify existing booking"""
    fees = {
        "date_change": random.randint(50, 200),
        "seat_upgrade": random.randint(100, 500),
        "meal_preference": 0,
        "add_baggage": random.randint(25, 75)
    }
    
    return {
        "confirmation_number": confirmation_number,
        "modification_type": modification_type,
        "status": "Confirmed",
        "change_fee": fees.get(modification_type, 0),
        "new_details": {
            "date": new_date if new_date else "No change",
            "class": upgrade_class if upgrade_class else "No change"
        },
        "updated_total": round(random.uniform(400, 1500), 2),
        "confirmation_email_sent": True
    }

def cancel_booking(confirmation_number: str, reason: str = None) -> dict:
    """Cancel booking and calculate refund"""
    original_price = random.uniform(300, 2000)
    cancellation_fee = random.uniform(50, 300)
    refund_amount = max(0, original_price - cancellation_fee)
    
    return {
        "confirmation_number": confirmation_number,
        "cancellation_status": "Confirmed",
        "original_price": round(original_price, 2),
        "cancellation_fee": round(cancellation_fee, 2),
        "refund_amount": round(refund_amount, 2),
        "refund_method": "Original payment method",
        "processing_time": f"{random.randint(3, 10)} business days",
        "cancellation_number": f"CXL{random.randint(100000, 999999)}"
    }

def get_seat_map(flight_number: str, date: str = None, class_type: str = None) -> dict:
    """Get seat map for flight"""
    # Generate seat map
    rows = random.randint(20, 40)
    seat_map = {}
    
    for row in range(1, rows + 1):
        for seat in ['A', 'B', 'C', 'D', 'E', 'F']:
            status = random.choices(
                ['available', 'occupied', 'blocked', 'premium'], 
                weights=[60, 30, 5, 5]
            )[0]
            
            seat_map[f"{row}{seat}"] = {
                "status": status,
                "type": "window" if seat in ['A', 'F'] else "aisle" if seat in ['C', 'D'] else "middle",
                "extra_legroom": row < 5 or row in [12, 13] or random.choice([True, False]),
                "price": random.randint(0, 150) if status == 'available' else None
            }
    
    return {
        "flight_number": flight_number,
        "aircraft_type": random.choice(["Boeing 737", "Airbus A320"]),
        "seat_map": seat_map,
        "available_seats": len([s for s in seat_map.values() if s["status"] == "available"]),
        "premium_seats_available": len([s for s in seat_map.values() if s["status"] == "available" and s["extra_legroom"]])
    }

def select_seat(confirmation_number: str, seat_number: str, passenger_name: str = None) -> dict:
    """Select seat for passenger"""
    seat_fee = random.randint(0, 75)
    
    return {
        "confirmation_number": confirmation_number,
        "passenger": passenger_name or "Passenger",
        "seat_number": seat_number,
        "seat_type": random.choice(["Standard", "Extra Legroom", "Premium"]),
        "seat_fee": seat_fee,
        "status": "Confirmed",
        "seat_features": {
            "window": seat_number[-1] in ['A', 'F'],
            "aisle": seat_number[-1] in ['C', 'D'],
            "extra_legroom": random.choice([True, False]),
            "power_outlet": random.choice([True, False])
        }
    }

def check_baggage_allowance(route: str, ticket_type: str = "economy", frequent_flyer_status: str = "none") -> dict:
    """Check baggage allowance and fees"""
    base_allowance = {"economy": 1, "business": 2, "first": 3}
    ff_bonus = {"none": 0, "silver": 1, "gold": 1, "platinum": 2}
    
    checked_allowance = base_allowance.get(ticket_type, 1) + ff_bonus.get(frequent_flyer_status, 0)
    
    return {
        "route": route,
        "ticket_type": ticket_type,
        "frequent_flyer_status": frequent_flyer_status,
        "carry_on": {
            "included": 1,
            "dimensions": "22x14x9 inches",
            "weight_limit": "15 lbs"
        },
        "checked_baggage": {
            "included": checked_allowance,
            "weight_limit": "50 lbs each",
            "additional_bag_fee": random.randint(25, 100),
            "overweight_fee": random.randint(50, 150)
        },
        "special_items": {
            "sports_equipment": f"${random.randint(75, 150)}",
            "musical_instruments": f"${random.randint(100, 200)}",
            "pet_carrier": f"${random.randint(125, 300)}"
        }
    }

def track_baggage(baggage_tag: str, confirmation_number: str = None) -> dict:
    """Track baggage status"""
    statuses = ["Checked In", "In Transit", "Arrived at Destination", "Out for Delivery", "Delivered", "Delayed", "Lost"]
    locations = ["Origin Airport", "Hub Airport", "Destination Airport", "Baggage Claim", "Delivery Service"]
    
    return {
        "baggage_tag": baggage_tag,
        "status": random.choice(statuses),
        "current_location": random.choice(locations),
        "last_scan": (datetime.now() - timedelta(hours=random.randint(1, 24))).strftime("%Y-%m-%d %H:%M"),
        "estimated_delivery": (datetime.now() + timedelta(hours=random.randint(2, 48))).strftime("%Y-%m-%d %H:%M"),
        "tracking_history": [
            {"location": "Check-in Counter", "time": "2025-01-15 08:30", "status": "Checked In"},
            {"location": "Baggage Sorting", "time": "2025-01-15 09:15", "status": "Processed"},
            {"location": "Aircraft", "time": "2025-01-15 10:45", "status": "Loaded"}
        ]
    }

def report_baggage_issue(issue_type: str, confirmation_number: str, description: str = None, contact_info: str = None) -> dict:
    """Report baggage issues"""
    case_number = f"BAG{random.randint(100000, 999999)}"
    
    return {
        "case_number": case_number,
        "issue_type": issue_type,
        "confirmation_number": confirmation_number,
        "status": "Case Opened",
        "priority": random.choice(["High", "Medium", "Low"]),
        "assigned_agent": f"Agent {random.randint(1000, 9999)}",
        "estimated_resolution": f"{random.randint(1, 7)} business days",
        "compensation": {
            "daily_allowance": "$50/day" if issue_type == "delayed" else None,
            "replacement_limit": "$1500" if issue_type == "lost" else None
        },
        "next_steps": [
            "Keep all receipts for essential items",
            "Check back in 24 hours for updates",
            "Contact case manager if no update within 48 hours"
        ]
    }

def get_airport_info(airport_code: str, info_type: str = "general") -> dict:
    """Get airport information"""
    airport_names = {
        "JFK": "John F. Kennedy International Airport",
        "LAX": "Los Angeles International Airport", 
        "ORD": "O'Hare International Airport",
        "ATL": "Hartsfield-Jackson Atlanta International Airport",
        "DFW": "Dallas/Fort Worth International Airport"
    }
    
    base_info = {
        "airport_code": airport_code,
        "name": airport_names.get(airport_code, f"{airport_code} Airport"),
        "city": random.choice(["New York", "Los Angeles", "Chicago", "Atlanta", "Dallas"]),
        "terminals": random.randint(2, 8),
        "runways": random.randint(2, 6)
    }
    
    if info_type == "facilities":
        base_info.update({
            "wifi": "Free throughout airport",
            "charging_stations": "Available at all gates",
            "atms": f"{random.randint(15, 40)} locations",
            "currency_exchange": "Available in international terminals",
            "medical": "First aid stations in each terminal"
        })
    elif info_type == "transportation":
        base_info.update({
            "public_transit": ["Subway", "Bus", "Train"],
            "taxi": "Available 24/7",
            "rideshare": ["Uber", "Lyft"],
            "rental_cars": ["Hertz", "Avis", "Enterprise", "Budget"],
            "parking": f"${random.randint(8, 25)}/day"
        })
    elif info_type == "dining":
        base_info.update({
            "restaurants": random.randint(20, 60),
            "fast_food": ["McDonald's", "Starbucks", "Subway", "Pizza Hut"],
            "fine_dining": ["Local specialty restaurants", "International cuisine"],
            "bars": f"{random.randint(5, 15)} locations"
        })
    
    return base_info

# Add all the missing tool implementations
def check_security_wait_times(airport_code: str, terminal: str = None) -> dict:
    """Get security wait times"""
    return {
        "airport_code": airport_code,
        "terminal": terminal or random.choice(["1", "2", "3", "A", "B"]),
        "current_wait_time": f"{random.randint(5, 45)} minutes",
        "checkpoints": [
            {"name": "Main Security", "wait_time": f"{random.randint(10, 30)} min", "status": "Open"},
            {"name": "TSA PreCheck", "wait_time": f"{random.randint(2, 10)} min", "status": "Open"},
            {"name": "CLEAR", "wait_time": f"{random.randint(1, 5)} min", "status": "Open"}
        ],
        "peak_hours": "6-9 AM, 4-7 PM",
        "recommendation": "Arrive 2 hours early for domestic flights"
    }

def find_airport_services(airport_code: str, service_type: str, terminal: str = None) -> dict:
    """Find airport services"""
    services_map = {
        "dining": ["Starbucks", "McDonald's", "Local Bistro", "Sushi Bar", "Pizza Place"],
        "shopping": ["Duty Free", "Electronics Store", "Bookstore", "Souvenir Shop", "Fashion Outlet"],
        "banking": ["ATM Network", "Currency Exchange", "Bank Branch"],
        "medical": ["First Aid Station", "Pharmacy", "Medical Clinic"],
        "wifi": ["Free Airport WiFi", "Premium WiFi Zones", "Business Lounges"]
    }
    
    available_services = services_map.get(service_type, ["General Services"])
    
    return {
        "airport_code": airport_code,
        "service_type": service_type,
        "terminal": terminal or "All Terminals",
        "available_services": random.sample(available_services, min(3, len(available_services))),
        "locations": [f"Gate {random.choice(['A', 'B', 'C'])}{random.randint(1, 30)}" for _ in range(3)],
        "hours": "Most services: 5 AM - 11 PM"
    }

def check_miles_balance(frequent_flyer_number: str, program: str = None) -> dict:
    """Check FF miles balance"""
    return {
        "frequent_flyer_number": frequent_flyer_number,
        "program": program or random.choice(["SkyMiles", "MileagePlus", "AAdvantage"]),
        "miles_balance": random.randint(5000, 150000),
        "tier_status": random.choice(["Silver", "Gold", "Platinum", "Diamond"]),
        "miles_expiring_soon": random.randint(0, 10000),
        "recent_activity": [
            {"date": "2025-01-10", "activity": "Flight credit", "miles": random.randint(500, 2000)},
            {"date": "2025-01-05", "activity": "Purchase bonus", "miles": random.randint(100, 500)}
        ]
    }

def redeem_miles(frequent_flyer_number: str, redemption_type: str, flight_details: str = None, miles_to_redeem: int = None) -> dict:
    """Redeem miles"""
    return {
        "frequent_flyer_number": frequent_flyer_number,
        "redemption_type": redemption_type,
        "miles_redeemed": miles_to_redeem or random.randint(10000, 50000),
        "value": f"${random.randint(100, 600)}",
        "confirmation_number": f"RDM{random.randint(100000, 999999)}",
        "status": "Confirmed",
        "remaining_balance": random.randint(5000, 100000)
    }

def request_special_assistance(confirmation_number: str, assistance_type: str, details: str = None, passenger_name: str = None) -> dict:
    """Request special assistance"""
    return {
        "confirmation_number": confirmation_number,
        "assistance_type": assistance_type,
        "passenger_name": passenger_name or "Passenger",
        "request_id": f"ASSIST{random.randint(100000, 999999)}",
        "status": "Confirmed",
        "details": details or f"Standard {assistance_type} assistance",
        "contact_phone": f"1-800-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "instructions": f"Arrive 30 minutes early for {assistance_type} assistance"
    }

def book_lounge_access(airport_code: str, date: str, lounge_name: str = None, duration: int = None, guests: int = None) -> dict:
    """Book lounge access"""
    lounges = ["Sky Club", "Admirals Club", "United Club", "Priority Pass Lounge"]
    
    return {
        "airport_code": airport_code,
        "lounge_name": lounge_name or random.choice(lounges),
        "date": date,
        "duration": duration or random.randint(2, 6),
        "guests": guests or 1,
        "booking_id": f"LOUNGE{random.randint(100000, 999999)}",
        "cost": f"${random.randint(40, 80)}",
        "amenities": ["WiFi", "Food & Beverages", "Comfortable Seating", "Charging Stations"],
        "location": f"Terminal {random.choice(['A', 'B', 'C'])}, Gate {random.randint(1, 30)}"
    }

def check_weather_impact(airport_code: str, date: str = None, flight_number: str = None) -> dict:
    """Check weather impact"""
    conditions = ["Clear", "Partly Cloudy", "Rain", "Snow", "Thunderstorms", "Fog"]
    impacts = ["No Impact", "Minor Delays", "Moderate Delays", "Significant Delays"]
    
    return {
        "airport_code": airport_code,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "current_weather": random.choice(conditions),
        "temperature": f"{random.randint(20, 90)}°F",
        "flight_impact": random.choice(impacts),
        "delay_probability": f"{random.randint(10, 80)}%",
        "visibility": f"{random.randint(1, 10)} miles",
        "wind_speed": f"{random.randint(5, 30)} mph",
        "recommendation": "Monitor flight status closely" if random.choice([True, False]) else "No special precautions needed"
    }

def get_disruption_alerts(airport_code: str, airline: str = None, severity: str = None) -> dict:
    """Get disruption alerts"""
    alert_types = ["Weather Delay", "Air Traffic Control", "Mechanical Issues", "Crew Scheduling", "Security"]
    
    return {
        "airport_code": airport_code,
        "airline": airline or "All Airlines",
        "current_alerts": [
            {
                "type": random.choice(alert_types),
                "severity": severity or random.choice(["Low", "Medium", "High"]),
                "description": f"Potential delays due to {random.choice(alert_types).lower()}",
                "estimated_delay": f"{random.randint(15, 120)} minutes",
                "affected_flights": random.randint(5, 50)
            }
        ],
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "next_update": (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
    }

def get_fare_rules(confirmation_number: str, fare_class: str = None) -> dict:
    """Get fare rules"""
    return {
        "confirmation_number": confirmation_number,
        "fare_class": fare_class or random.choice(["Y", "B", "M", "H", "Q"]),
        "rules": {
            "changes": {
                "allowed": random.choice([True, False]),
                "fee": f"${random.randint(0, 300)}"
            },
            "cancellation": {
                "allowed": True,
                "fee": f"${random.randint(50, 400)}",
                "refundable": random.choice([True, False])
            },
            "baggage": {
                "checked_included": random.randint(0, 2),
                "carry_on_included": 1
            },
            "seat_selection": {
                "included": random.choice([True, False]),
                "fee_range": "$0-$150"
            }
        },
        "restrictions": [
            "7-day advance purchase required",
            "Saturday night stay may be required",
            "Non-transferable"
        ]
    }

def compare_upgrade_options(confirmation_number: str, target_class: str = None, payment_method: str = None) -> dict:
    """Compare upgrade options"""
    return {
        "confirmation_number": confirmation_number,
        "current_class": "Economy",
        "upgrade_options": [
            {
                "class": "Premium Economy",
                "cash_price": f"${random.randint(100, 300)}",
                "miles_price": f"{random.randint(5000, 15000)} miles",
                "availability": random.choice(["Available", "Waitlist", "Sold Out"])
            },
            {
                "class": "Business",
                "cash_price": f"${random.randint(300, 800)}",
                "miles_price": f"{random.randint(15000, 40000)} miles",
                "availability": random.choice(["Available", "Waitlist", "Sold Out"])
            },
            {
                "class": "First",
                "cash_price": f"${random.randint(800, 2000)}",
                "miles_price": f"{random.randint(40000, 80000)} miles",
                "availability": random.choice(["Available", "Waitlist", "Sold Out"])
            }
        ],
        "recommended": "Premium Economy" if random.choice([True, False]) else "Business"
    }

# Cleanlab validation helper (with error handling)
def run_cleanlab_validation(query: str, messages: list, response: str, thread_id: str, tools: list = None):
    if not cl_project:
        return {"should_guardrail": False, "expert_answer": None, "error": "Cleanlab not available"}
    
    try:
        validate_params = {
            "response": response,
            "query": query,
            "context": "",
            "messages": messages,
            "metadata": {"integration": "airline-support-streamlit", "thread_id": thread_id},
            "tools": tools
        }
        
        vr = cl_project.validate(**validate_params)
        output = {
            "should_guardrail": vr.should_guardrail,
            "expert_answer": vr.expert_answer
        }
        return output
    except Exception as e:
        return {"should_guardrail": False, "expert_answer": None, "error": str(e)}

# LLM call wrapper (with error handling)
@st.cache_data(ttl=300)  # Cache for 5 minutes to avoid repeated calls
def call_openai(messages_json, **kwargs):
    try:
        llm_client = OpenAI(api_key=OPENAI_API_KEY)
        messages = json.loads(messages_json)
        resp = llm_client.chat.completions.create(
            model="gpt-4o",  # Fixed: was "gpt-4.1" which doesn't exist
            messages=messages,
            tools=tools,
            **kwargs
        )
        return resp.choices[0].message
    except Exception as e:
        st.error(f"🚨 OpenAI API Error: {str(e)}")
        raise e

SYSTEM_PROMPT = {
    "role": "system",
    "content": """
You are an advanced airline support assistant with access to comprehensive airline services. You use a ReACT (Reasoning + Acting) approach to help customers with all their travel needs.

Available tools:
""" + "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tools) + """

Instructions:
1. Think step by step about what the customer needs
2. Use the most appropriate tools to gather information or perform actions
3. You can use multiple tools in sequence to fully address complex requests
4. After getting tool results, analyze them and decide if you need more information
5. Provide comprehensive, helpful responses with specific details
6. Always prioritize customer satisfaction and safety

You can help with: flight searches, bookings, seat selection, baggage, airport information, weather impacts, loyalty programs, special assistance, and much more.
"""
}

def react_agent_step(user_input: str, history: list, thread_id: str):
    """Single step of the ReACT agent - returns updated history and whether to continue"""
    
    # Add user input to history if it's not already there
    if not history or history[-1]["content"] != user_input:
        history.append({"role": "user", "content": user_input})
    
    # Query the LLM
    messages_json = json.dumps(history)
    msg = call_openai(messages_json, temperature=0)
    
    # Check if LLM wants to use tools
    if msg.tool_calls:
        # LLM decided to use a tool
        tool_call = msg.tool_calls[0]
        action = tool_call.function.name
        args = json.loads(tool_call.function.arguments)
        
        # Add the structured message with tool calls to history
        msg_dict = {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments
                    }
                }
            ]
        }
        history.append(msg_dict)
        
        # Execute the tool - now with many more options!
        tool_functions = {
            "search_one_way": search_one_way,
            "search_round_trip": search_round_trip,
            "search_multi_city": search_multi_city,
            "check_flight_status": check_flight_status,
            "get_flight_details": get_flight_details,
            "track_flight_route": track_flight_route,
            "retrieve_booking": retrieve_booking,
            "modify_booking": modify_booking,
            "cancel_booking": cancel_booking,
            "get_seat_map": get_seat_map,
            "select_seat": select_seat,
            "check_baggage_allowance": check_baggage_allowance,
            "track_baggage": track_baggage,
            "report_baggage_issue": report_baggage_issue,
            "get_airport_info": get_airport_info,
            "check_security_wait_times": check_security_wait_times,
            "find_airport_services": find_airport_services,
            "check_miles_balance": check_miles_balance,
            "redeem_miles": redeem_miles,
            "request_special_assistance": request_special_assistance,
            "book_lounge_access": book_lounge_access,
            "check_weather_impact": check_weather_impact,
            "get_disruption_alerts": get_disruption_alerts,
            "get_fare_rules": get_fare_rules,
            "compare_upgrade_options": compare_upgrade_options
        }
        
        if action in tool_functions:
            tool_out = tool_functions[action](**args)
        else:
            tool_out = {"error": f"Tool {action} not implemented yet"}
        
        # Add tool result to history
        tool_result = json.dumps(tool_out, indent=2)
        history.append({
            "role": "tool",
            "content": tool_result,
            "tool_call_id": tool_call.id
        })
        
        return history, True, f"🔧 Using tool: {action} with {args}", tool_result
    
    else:
        # LLM provided a final response
        final_response = msg.content
        history.append({"role": "assistant", "content": final_response})
        
        # Run Cleanlab validation
        vr = run_cleanlab_validation(
            query=user_input,
            messages=history,
            response=final_response,
            thread_id=thread_id
        )
        
        return history, False, final_response, vr

# Streamlit UI
def main():
    st.title("🛫 Advanced Airline Support Agent")
    st.markdown("*Comprehensive airline services with 25+ specialized tools*")
    
    # Initialize session state FIRST - before any other code
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "history" not in st.session_state:
        st.session_state.history = [SYSTEM_PROMPT]
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = uuid.uuid4().hex
    
    # PROMINENT CODEX PROJECT LINK
    if CLEANLAB_PROJECT_ID:
        codex_url = f"https://codex.cleanlab.ai/projects/{CLEANLAB_PROJECT_ID}/"
        st.info(f"🔬 **AI Safety Monitoring**: [View Cleanlab Codex Project]({codex_url})")
    
    # Show expanded capabilities
    with st.sidebar:
        st.header("🔒 Project Status")
        if OPENAI_API_KEY:
            st.success("✅ OpenAI API Key: Configured")
        else:
            st.error("❌ OpenAI API Key: Missing")
        
        if cl_project:
            st.success("✅ Cleanlab: Connected")
        else:
            st.warning("⚠️ Cleanlab: Disabled")
        
        st.header("💬 Conversations")
        
        if st.button("🔄 New Conversation"):
            st.session_state.messages = []
            st.session_state.history = [SYSTEM_PROMPT]
            st.session_state.thread_id = uuid.uuid4().hex
            st.rerun()
        
        st.markdown(f"**Thread ID:** `{st.session_state.thread_id[:8]}...`")
        
        # Show expanded example queries
        st.header("💡 Example Queries")
        example_categories = {
            "Flight Search": [
                "Find flights from SFO to LAX on 2025-03-15",
                "Search for business class round-trip from NYC to London",
                "Multi-city trip: NYC→LA→Vegas→NYC in April"
            ],
            "Booking Management": [
                "Retrieve my booking ABC123",
                "Change my flight date for confirmation XYZ789",
                "Cancel booking and calculate refund"
            ],
            "Airport & Services": [
                "What restaurants are at JFK airport?",
                "Check security wait times at LAX",
                "Book lounge access at Chicago O'Hare"
            ],
            "Baggage & Special": [
                "Track my baggage tag 123456789",
                "What's my baggage allowance for international flights?",
                "Request wheelchair assistance for my booking"
            ]
        }
        
        for category, queries in example_categories.items():
            with st.expander(f"📝 {category}"):
                for query in queries:
                    if st.button(query, key=f"example_{hash(query)}"):
                        st.session_state.example_query = query
        
        st.header("🛠️ Available Tools")
        st.markdown(f"**{len(tools)} specialized tools available:**")
        
        tool_categories = {
            "✈️ Flight Services": ["search_one_way", "search_round_trip", "search_multi_city", "check_flight_status", "get_flight_details", "track_flight_route"],
            "📋 Booking Management": ["retrieve_booking", "modify_booking", "cancel_booking"],
            "💺 Seat Services": ["get_seat_map", "select_seat"],
            "🧳 Baggage Services": ["check_baggage_allowance", "track_baggage", "report_baggage_issue"],
            "🏢 Airport Info": ["get_airport_info", "check_security_wait_times", "find_airport_services"],
            "🏆 Loyalty & Upgrades": ["check_miles_balance", "redeem_miles", "compare_upgrade_options"],
            "🌟 Special Services": ["request_special_assistance", "book_lounge_access"],
            "🌤️ Weather & Alerts": ["check_weather_impact", "get_disruption_alerts"],
            "💰 Pricing & Fares": ["get_fare_rules", "compare_upgrade_options"]
        }
        
        for category, tool_list in tool_categories.items():
            with st.expander(category):
                for tool in tool_list:
                    st.write(f"• {tool}")
    
    # Main chat interface
    chat_container = st.container()
    
    # Display chat messages
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                if message["role"] == "assistant":
                    st.markdown(message["content"])
                    # Show validation info if available
                    if "validation" in message and message["validation"]:
                        with st.expander("🛡️ Cleanlab Validation"):
                            st.json(message["validation"])
                    # Show tool usage if available
                    if "tool_info" in message:
                        with st.expander("🔧 Tool Usage"):
                            st.code(message["tool_info"], language="json")
                else:
                    st.markdown(message["content"])
    
    # Handle example query from sidebar
    if "example_query" in st.session_state:
        user_input = st.session_state.example_query
        del st.session_state.example_query
    else:
        # Chat input
        user_input = st.chat_input("Ask me anything about flights, bookings, airports, baggage, or travel services...")
    
    # Process user input
    if user_input:
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Show user message immediately
        with st.chat_message("user"):
            st.markdown(user_input)
        
        # Process with ReACT agent
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            tool_placeholder = st.empty()
            
            max_iterations = 5
            current_history = st.session_state.history.copy()
            
            try:
                for iteration in range(max_iterations):
                    with st.spinner(f"🤔 Thinking... (Step {iteration + 1})"):
                        history, continue_loop, response, extra_info = react_agent_step(
                            user_input, current_history, st.session_state.thread_id
                        )
                        current_history = history
                    
                    if continue_loop:
                        # Show tool usage
                        tool_placeholder.info(f"🔧 **Step {iteration + 1}:** {response}")
                        if isinstance(extra_info, str):
                            with st.expander(f"Tool Result (Step {iteration + 1})"):
                                st.code(extra_info, language="json")
                    else:
                        # Final response
                        message_placeholder.markdown(response)
                        
                        # Show validation info
                        if isinstance(extra_info, dict):
                            if extra_info.get("should_guardrail"):
                                st.warning("🛡️ **Safety Alert:** This response was flagged by Cleanlab validation")
                            
                            with st.expander("🛡️ Cleanlab Validation Results"):
                                st.json(extra_info)
                        
                        # Add to session state
                        assistant_message = {
                            "role": "assistant", 
                            "content": response,
                            "validation": extra_info if isinstance(extra_info, dict) else None
                        }
                        st.session_state.messages.append(assistant_message)
                        break
                
                # Update session history
                st.session_state.history = current_history
            
            except Exception as e:
                st.error(f"🚨 Error processing request: {str(e)}")
                st.info("Please try again or contact support if the issue persists.")
        
        st.rerun()

if __name__ == "__main__":
    main() 
import openai
from openai import OpenAI
import json

# Initialize OpenAI client
client = OpenAI()

# Mock airline support tools
def check_flight_status(flight_number: str):
    return {
        "flight_number": flight_number,
        "status": "On Time",
        "departure": "SFO 10:35 AM",
        "arrival": "JFK 6:55 PM"
    }

def rebook_flight(ticket_id: str, new_date: str):
    return {
        "ticket_id": ticket_id,
        "new_date": new_date,
        "status": "Rebooked Successfully"
    }

def get_baggage_info(baggage_tag: str):
    return {
        "baggage_tag": baggage_tag,
        "location": "Loaded on Flight SFO → JFK",
        "status": "In Transit"
    }

# Tool schema definitions for the agent
tools = [
    {
        "type": "function",
        "function": {
            "name": "check_flight_status",
            "description": "Check the status of a flight by flight number",
            "parameters": {
                "type": "object",
                "properties": {
                    "flight_number": {"type": "string"}
                },
                "required": ["flight_number"]
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rebook_flight",
            "description": "Rebook a flight ticket to a new date",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticket_id": {"type": "string"},
                    "new_date": {"type": "string", "description": "New date in YYYY-MM-DD format"}
                },
                "required": ["ticket_id", "new_date"]
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_baggage_info",
            "description": "Get baggage information by baggage tag number",
            "parameters": {
                "type": "object",
                "properties": {
                    "baggage_tag": {"type": "string"}
                },
                "required": ["baggage_tag"]
            },
        }
    }
]

# Function dispatch table
function_map = {
    "check_flight_status": check_flight_status,
    "rebook_flight": rebook_flight,
    "get_baggage_info": get_baggage_info,
}

# Run the agent loop
def run_agent(user_input: str):
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # lightweight reasoning model
        messages=[{"role": "user", "content": user_input}],
        tools=tools
    )

    message = response.choices[0].message
    if message.tool_calls:
        results = []
        for tool_call in message.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = function_map[func_name](**args)

            results.append({
                "tool": func_name,
                "input": args,
                "output": result
            })

        return results

    return message.content


if __name__ == "__main__":
    # Example queries
    print(run_agent("What's the status of flight UA415?"))
    print(run_agent("Can you rebook my ticket 12345 for September 3rd, 2025?"))
    print(run_agent("Where is my baggage with tag BAG789?"))

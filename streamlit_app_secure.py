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

# Import from our separated modules
from tools import tools, TOOL_FUNCTIONS
from react_agent import ReactAgent

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

# Initialize the ReactAgent
@st.cache_resource
def get_react_agent():
    print(f"DEBUG: Initializing ReactAgent with OpenAI key: {bool(OPENAI_API_KEY)}")
    print(f"DEBUG: Cleanlab project: {bool(cl_project)}")
    agent = ReactAgent(OPENAI_API_KEY, cl_project)
    print(f"DEBUG: ReactAgent initialized successfully")
    return agent

agent = get_react_agent()
print(f"DEBUG: Agent object created: {type(agent)}")

# System prompt for conversation history
SYSTEM_PROMPT = agent.system_prompt

# Streamlit UI
def main():
    # Initialize session state FIRST - before any other code
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    if "history" not in st.session_state:
        st.session_state.history = [SYSTEM_PROMPT]
    
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = uuid.uuid4().hex
    
    st.title("🛫 Advanced Airline Support Agent")
    st.markdown("*Comprehensive airline services with 25+ specialized tools*")
    
    # PROMINENT CODEX PROJECT LINK
    if CLEANLAB_PROJECT_ID:
        codex_url = f"https://codex.cleanlab.ai/projects/{CLEANLAB_PROJECT_ID}/"
        st.info(f"🔬 **AI Safety Monitoring**: [View Cleanlab Codex Project]({codex_url})")
    
    # PROMINENT SAMPLE QUERIES - Show when no conversation has started
    if len(st.session_state.messages) == 0:
        st.markdown("---")
        st.markdown("### 🚀 **Try these sample queries to get started:**")
        
        # Create columns for better layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### ✈️ **Flight Operations**")
            flight_queries = [
                "Find flights from SFO to LAX on 2025-03-15",
                "Search business class round-trip NYC to London",
                "Book flight AA123 on May 15th for John Doe",
                "Check status of flight DL456"
            ]
            for query in flight_queries:
                if st.button(query, key=f"main_{hash(query)}", use_container_width=True):
                    st.session_state.example_query = query
                    st.rerun()
        
        with col2:
            st.markdown("#### 🎯 **Popular Services**")
            service_queries = [
                "What restaurants are at JFK airport?",
                "Track my baggage tag 123456789",
                "Retrieve my booking ABC123",
                "Request wheelchair assistance"
            ]
            for query in service_queries:
                if st.button(query, key=f"main_{hash(query)}", use_container_width=True):
                    st.session_state.example_query = query
                    st.rerun()
        
        # Additional prominent examples in a single row
        st.markdown("#### 🌟 **Advanced Features**")
        col3, col4, col5 = st.columns(3)
        
        with col3:
            if st.button("Multi-city trip planner", key="multi_city", use_container_width=True):
                st.session_state.example_query = "Plan a multi-city trip: NYC→LA→Vegas→NYC in April"
                st.rerun()
        
        with col4:
            if st.button("Weather impact checker", key="weather", use_container_width=True):
                st.session_state.example_query = "Check weather impact on flights at Miami airport"
                st.rerun()
        
        with col5:
            if st.button("Miles & upgrades", key="miles", use_container_width=True):
                st.session_state.example_query = "Check my frequent flyer miles balance FF123456"
                st.rerun()
        
        st.markdown("---")
    
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
                "Multi-city trip: NYC→LA→Vegas→NYC in April",
                "Book flight AA123 on May 15th for John Doe (john@example.com)"
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
            "✈️ Flight Services": ["search_one_way", "search_round_trip", "search_multi_city", "book_flight", "check_flight_status", "get_flight_details", "track_flight_route"],
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
                        print(f"DEBUG: About to call agent.react_step with user_input: {user_input}")
                        print(f"DEBUG: Current history length: {len(current_history)}")
                        print(f"DEBUG: Thread ID: {st.session_state.thread_id}")
                        
                        history, continue_loop, response, extra_info = agent.react_step(
                            user_input, current_history, st.session_state.thread_id
                        )
                        print(f"DEBUG: react_step returned - continue_loop: {continue_loop}, response: {response}")
                        current_history = history
                    
                    if continue_loop:
                        # Show tool usage
                        tool_placeholder.info(f"🔧 **Step {iteration + 1}:** {response}")
                        
                        # Show validation for intermediate steps
                        if isinstance(extra_info, dict):
                            if extra_info.get("should_guardrail"):
                                st.warning(f"🛡️ **Safety Alert (Step {iteration + 1}):** Tool selection was flagged by Cleanlab validation")
                            
                            with st.expander(f"🛡️ Cleanlab Validation (Step {iteration + 1})"):
                                st.json(extra_info)
                        elif isinstance(extra_info, str):
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
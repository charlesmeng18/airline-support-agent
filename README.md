# 🛫 Airline Support Agent - Streamlit App

A conversational AI agent for airline customer support, powered by OpenAI's GPT-4 with ReACT (Reasoning + Acting) methodology and Cleanlab validation for AI safety.

## 🔒 Security Notice

This application handles sensitive API keys. **NEVER** commit actual API keys to version control. Always use environment variables or Streamlit secrets.

## Features

- **25+ Specialized Tools**: Comprehensive airline services including flight search, booking management, seat selection, baggage tracking, airport services, and more
- **Flight Search**: Search for one-way, round-trip, and multi-city flights
- **Flight Status**: Check real-time flight status and tracking
- **Booking Management**: Retrieve, modify, and cancel bookings
- **Seat Management**: View seat maps and select seats
- **Baggage Services**: Check allowances, track bags, report issues
- **Airport Information**: Get facility info, security wait times, services
- **Loyalty Programs**: Check miles, redeem rewards, compare upgrades
- **Special Services**: Request assistance, book lounge access
- **Weather & Alerts**: Check weather impacts and disruption alerts
- **AI Safety**: Integrated Cleanlab validation to ensure safe and appropriate responses
- **Interactive UI**: Modern Streamlit interface with chat functionality

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   Create a `.env` file with your API keys (NEVER commit this file):
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   CODEX_API_KEY=your_cleanlab_codex_api_key_here
   CLEANLAB_PROJECT_ID=your_cleanlab_project_id_here
   ```

   **For Streamlit Cloud deployment**, use Streamlit secrets instead:
   - Create `.streamlit/secrets.toml` (also excluded from git)
   - Add your keys there in TOML format

3. **Run the app:**
   ```bash
   streamlit run streamlit_app_secure.py
   ```

## Usage

1. Open your browser to the provided localhost URL (usually `http://localhost:8501`)
2. Start chatting with the airline support agent
3. Try example queries like:
   - "Find business class flights from SFO to LAX on 2025-03-15"
   - "Check status of flight AA123"
   - "Round trip from NYC to Miami, departing March 10, returning March 17"
   - "Track my baggage with tag number 123456789"
   - "What restaurants are available at JFK airport?"
   - "Request wheelchair assistance for my booking ABC123"
   - "Check my frequent flyer miles balance"

## Architecture

- **ReACT Agent**: Uses reasoning and acting cycles to solve complex queries
- **25+ Tools**: Comprehensive airline service tools for all customer needs
- **Cleanlab Validation**: AI safety monitoring for all responses
- **Session Management**: Maintains conversation context across interactions
- **Secure Credential Handling**: Uses Streamlit secrets and environment variables

## Security Features

- ✅ No hardcoded API keys in source code
- ✅ Secure credential retrieval from environment/secrets
- ✅ Input validation and error handling
- ✅ API key validation on startup
- ✅ Cleanlab safety validation integration

## Note

This is a demo application using simulated airline data. In a production environment, you would integrate with real airline APIs and databases. 
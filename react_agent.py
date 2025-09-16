import json
from openai import OpenAI
from cleanlab_codex.client import Client as CleanlabClient
from braintrust import init_logger, traced, wrap_openai

from tools import tools, TOOL_FUNCTIONS

class ReactAgent:
    def __init__(self, openai_api_key: str, cleanlab_project=None):
        self.openai_api_key = openai_api_key
        self.cleanlab_project = cleanlab_project
        self.llm_client = wrap_openai(OpenAI(api_key=openai_api_key))
        self.logger = init_logger(project="Airline Support Agent")
        
        # System prompt for the agent
        self.system_prompt = {
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

IMPORTANT - Context Handling:
- Pay close attention to the conversation history
- When users make follow-up requests (like "just myself, economy, cheapest"), refer back to previous messages for missing context
- For flight searches, if a user previously mentioned dates/airports, use that information for follow-up queries
- If you're missing required parameters, ask the user to clarify rather than making assumptions
- Always maintain context from previous tool calls and results

Example conversation flow:
User: "Round-trip flight from SFO to LAX on May 10 2026, returning May 15"
Assistant: [searches for round-trip flights]
User: "Just myself, economy, whatever's cheapest"
Assistant: [uses the same dates/airports from previous query, searches with economy class and 1 passenger]

You can help with: flight searches, bookings, seat selection, baggage, airport information, weather impacts, loyalty programs, special assistance, and much more.
"""
        }
    
    @traced
    def call_openai(self, messages: list, **kwargs):
        """Call OpenAI API with error handling"""
        try:
            resp = self.llm_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                tools=tools,
                **kwargs
            )
            return resp.choices[0].message
        except Exception as e:
            raise Exception(f"OpenAI API Error: {str(e)}")
    
    @traced
    def run_cleanlab_validation(self, query: str, messages: list, response, thread_id: str, tools=None, metadata=None):
        """Run Cleanlab validation if available"""
        if not self.cleanlab_project:
            return {"should_guardrail": False, "expert_answer": None, "error": "Cleanlab not available"}
        
        try:
            # Extract the response content as a string for Cleanlab validation
            response_content = response.content
            
            validate_params = {
                "response": response_content,  # Pass the response content as a string
                "query": query,
                "context": "",
                "messages": messages,
                "metadata": metadata or {"integration": "airline-support-streamlit", "thread_id": thread_id},
                "tools": tools
            }
            
            vr = self.cleanlab_project.validate(**validate_params)
            return {
                "should_guardrail": vr.should_guardrail,
                "expert_answer": vr.expert_answer,
                "escalated_to_sme": getattr(vr, 'escalated_to_sme', False)
            }
        except Exception as e:
            return {"should_guardrail": False, "expert_answer": None, "error": str(e)}
    
    @traced
    def react_step(self, user_input: str, history: list, thread_id: str):
        """Single step of the ReACT agent - returns updated history and whether to continue"""
        
        print(f"DEBUG: Starting react_step with input: {user_input}")
        print(f"DEBUG: History length: {len(history)}")
        
        # Add user input to history only if it's not already the last message
        if not history or not (history[-1].get("role") == "user" and history[-1].get("content") == user_input):
            history.append({"role": "user", "content": user_input})
        
        print(f"DEBUG: About to call OpenAI API")
        # Query the LLM
        try:
            response = self.call_openai(history, temperature=0)
            print(f"DEBUG: OpenAI response received: {type(response)}")
            print(f"DEBUG: Response content: {getattr(response, 'content', 'NO CONTENT')}")
        except Exception as e:
            print(f"DEBUG: OpenAI API error: {e}")
            raise e
        
        ### Cleanlab API ###
        try:
            validation_result = self.run_cleanlab_validation(
                query=user_input,
                messages=history,
                response=response, 
                tools=tools, # Pass the full response object
                thread_id=thread_id
            )
            print(f"DEBUG: Cleanlab validation result: {validation_result}")
        except Exception as e:
            print(f"DEBUG: Cleanlab validation error: {e}")
            validation_result = {"should_guardrail": False, "expert_answer": None, "error": str(e)}
        
        # Get final response after Cleanlab validation (you can implement get_final_response_with_cleanlab later)
        # For now, we'll use the original response
        final_response = response
        ### End of new code to add for Cleanlab API ###
        
        print(f"DEBUG: Final response type: {type(final_response)}")
        print(f"DEBUG: Final response has tool_calls: {hasattr(final_response, 'tool_calls')}")
        if hasattr(final_response, 'tool_calls'):
            print(f"DEBUG: Tool calls: {final_response.tool_calls}")
        
        # Convert message object to dict format for history
        assistant_message = {
            "role": final_response.role,
            "content": final_response.content,
        }
        if hasattr(final_response, 'tool_calls') and final_response.tool_calls:
            assistant_message["tool_calls"] = final_response.tool_calls
        
        # Add the LLM response to history
        history.append(assistant_message)
        
        # Check if there are tool calls
        if not final_response.tool_calls:
            # No tool calls - conversation is complete
            print(f"DEBUG: No tool calls, returning final response")
            return history, False, final_response.content, validation_result
        else:
            # Handle tool calls - match the exact pattern from your example
            print(f"DEBUG: Processing tool calls")
            tools_for_print = []
            for tool_call in final_response.tool_calls:
                args = json.loads(tool_call.function.arguments)
                tool_response = TOOL_FUNCTIONS[tool_call.function.name](**args) if tool_call.function.name in TOOL_FUNCTIONS else {"error": f"Tool {tool_call.function.name} not implemented yet"}
                
                tool_dict = {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(tool_response),
                }
                history.append(tool_dict)
                tools_for_print.append(tool_dict)
            
            # Return with continue=True since we executed tools
            print(f"DEBUG: Returning with tool execution")
            return history, True, f"🔧 Executed tools: {tools_for_print}", validation_result 
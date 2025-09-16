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
You are an airline support assistant that MUST ONLY provide information obtained through tool calls. You are FORBIDDEN from using any pre-existing knowledge to answer questions.

STRICT RULES:
1. DO NOT provide ANY information that wasn't explicitly returned by a tool
2. ALWAYS use at least one tool before responding to any query
3. If you can't find information through tools, say "I need to check that information using our tools but [explain what's preventing the tool check]"
4. NEVER make assumptions or use general knowledge about airlines, flights, or travel
5. ALL responses MUST be grounded in tool results

Available tools:
""" + "\n".join(f"- {t['function']['name']}: {t['function']['description']}" for t in tools) + """

REQUIRED WORKFLOW:
1. For EVERY query, identify which tools you need
2. Call those tools to get information
3. ONLY use information from tool responses
4. If tools don't provide enough information, say so
5. NEVER fill in gaps with assumed knowledge

EXAMPLES OF WHAT NOT TO DO:
❌ "Generally, flights to Europe require a passport" (ungrounded knowledge)
❌ "Most airlines allow one carry-on bag" (assumed policy)
❌ "You should arrive 2 hours early" (generic advice)
Instead, say: "Let me check the specific requirements using our tools..."

EXAMPLES OF CORRECT RESPONSES:
✓ "According to the flight check tool, your flight AA123 is [status from tool]"
✓ "I'll need to check that policy with our tools. What's your flight number?"
✓ "The tool returned an error when checking that information. Could you provide..."

Remember: You are an interface to the tools, not a source of general airline knowledge. If you can't verify something through tools, admit it.
"""
        }
    
    @traced
    def call_openai(self, messages: list, **kwargs):
        """Call OpenAI API with error handling"""
        try:
            resp = self.llm_client.chat.completions.create(
                model="gpt-4.1-mini",
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
            response_content = response.content if hasattr(response, 'content') else str(response)
            
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
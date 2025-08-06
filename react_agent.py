import json
from openai import OpenAI
from cleanlab_codex.client import Client as CleanlabClient
from tools import tools, TOOL_FUNCTIONS

class ReactAgent:
    def __init__(self, openai_api_key: str, cleanlab_project=None):
        self.openai_api_key = openai_api_key
        self.cleanlab_project = cleanlab_project
        self.llm_client = OpenAI(api_key=openai_api_key)
        
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
    
    def call_openai(self, messages: list, **kwargs):
        """Call OpenAI API with error handling"""
        try:
            resp = self.llm_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=tools,
                **kwargs
            )
            return resp.choices[0].message
        except Exception as e:
            raise Exception(f"OpenAI API Error: {str(e)}")
    
    def run_cleanlab_validation(self, query: str, messages: list, response: str, thread_id: str):
        """Run Cleanlab validation if available"""
        if not self.cleanlab_project:
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
            
            vr = self.cleanlab_project.validate(**validate_params)
            return {
                "should_guardrail": vr.should_guardrail,
                "expert_answer": vr.expert_answer
            }
        except Exception as e:
            return {"should_guardrail": False, "expert_answer": None, "error": str(e)}
    
    def react_step(self, user_input: str, history: list, thread_id: str):
        """Single step of the ReACT agent - returns updated history and whether to continue"""
        
        # Add user input to history only if it's not already the last message
        if not history or not (history[-1].get("role") == "user" and history[-1].get("content") == user_input):
            history.append({"role": "user", "content": user_input})
        
        # Query the LLM
        msg = self.call_openai(history, temperature=0)
        
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
            
            # Execute the tool using the imported TOOL_FUNCTIONS
            if action in TOOL_FUNCTIONS:
                tool_out = TOOL_FUNCTIONS[action](**args)
            else:
                tool_out = {"error": f"Tool {action} not implemented yet"}
            
            # Add tool result to history
            tool_result = json.dumps(tool_out, indent=2)
            history.append({
                "role": "tool",
                "content": tool_result,
                "tool_call_id": tool_call.id
            })
            
            # VALIDATE AFTER TOOL RESULT IS ADDED (complete context)
            tool_selection_validation = self.run_cleanlab_validation(
                query=user_input,
                messages=history,  # Now includes tool result
                response=f"Tool call: {action} with args {args} -> {tool_result[:200]}...",
                thread_id=thread_id
            )
            
            return history, True, f"🔧 Using tool: {action} with {args}", tool_selection_validation
        
        else:
            # LLM provided a final response
            final_response = msg.content
            history.append({"role": "assistant", "content": final_response})
            
            # VALIDATE THE FINAL RESPONSE
            final_response_validation = self.run_cleanlab_validation(
                query=user_input,
                messages=history,
                response=final_response,
                thread_id=thread_id
            )
            
            return history, False, final_response, final_response_validation 
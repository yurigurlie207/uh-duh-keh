"""
AI handlers for Claude API integration
"""
import os
import json
import asyncio
from typing import List, Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"

class AIHandlers:
    def __init__(self):
        if not CLAUDE_API_KEY:
            print("⚠️  CLAUDE_API_KEY not found in environment variables")
    
    async def call_claude_api(self, prompt: str, max_retries: int = 3) -> str:
        """Call Claude API with retry logic"""
        if not CLAUDE_API_KEY:
            raise Exception("Claude API key not configured")
        
        # Clean up prompt for Claude
        safe_prompt = prompt.replace("•", "-").replace("**", "").replace("🔴", "").replace("🟡", "").replace("🟢", "")
        
        request_body = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 500,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{safe_prompt}\n\nIMPORTANT: Respond ONLY with valid JSON, no extra commentary."
                        }
                    ]
                }
            ]
        }
        
        attempt = 0
        while attempt < max_retries:
            try:
                print(f"🤖 Attempt {attempt + 1}: sending request to Claude API...")
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        CLAUDE_API_URL,
                        headers={
                            "Content-Type": "application/json",
                            "x-api-key": CLAUDE_API_KEY,
                            "anthropic-version": "2023-06-01"
                        },
                        json=request_body
                    )
                
                print(f"🤖 Claude API response status: {response.status_code}")
                
                if not response.is_success:
                    error_text = response.text
                    print(f"❌ Claude API error response: {error_text}")
                    
                    # If it's a 500 or 529 (overloaded), retry
                    if response.status_code in [500, 529]:
                        print(f"🔄 Claude API {response.status_code} (retryable), will retry...")
                        raise Exception(f"Claude API {response.status_code}: {error_text}")
                    raise Exception(f"Claude API error: {response.status_code} {error_text}")
                
                data = response.json()
                return data.get("content", [{}])[0].get("text", "")
                
            except Exception as e:
                print(f"❌ Claude API attempt {attempt + 1} failed: {e}")
                attempt += 1
                if attempt < max_retries:
                    backoff = 500 * (2 ** attempt)  # Exponential backoff
                    print(f"⏳ Retrying after {backoff}ms...")
                    await asyncio.sleep(backoff / 1000)
                else:
                    print("❌ Max retries reached, throwing error")
                    raise e
    
    def parse_claude_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Claude's JSON response"""
        try:
            # Try to extract JSON from response
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            return json.loads(response)
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse Claude response as JSON: {e}")
            print(f"📝 Raw response: {response}")
            raise Exception(f"Invalid JSON response from Claude: {e}")
    
    def format_preferences(self, preferences: Dict[str, Any]) -> str:
        """Format user preferences for AI prompt"""
        if not preferences:
            return "No preferences specified"
        
        preference_items = []
        for key, value in preferences.items():
            if isinstance(value, bool) and value:
                preference_items.append(f"• {key.replace('_', ' ').title()}")
        
        if preference_items:
            return "User prefers these task categories:\n" + "\n".join(preference_items)
        else:
            return "No specific task category preferences"
    
    def build_prioritization_prompt(self, todos: List[Dict], preferences: Dict[str, Any]) -> str:
        """Build the prompt for AI prioritization"""
        active_todos = [todo for todo in todos if not todo.get('completed', False)]
        preferences_text = self.format_preferences(preferences)
        
        todos_text = "\n".join([
            f"{todo.get('title', 'Untitled')} (Priority: {todo.get('priority', 999)}, Assigned to: {todo.get('assigned_to', 'Unassigned')})"
            for todo in active_todos
        ]) if active_todos else "No active todos found."
        
        return f"""You are an AI assistant helping to prioritize household tasks based on user preferences and responsibilities.

USER PREFERENCES:
{preferences_text}

CURRENT TODOS:
{todos_text}

TASK: Reorder these todos based on user preferences and responsibilities, considering:
1. Urgency (tasks that are time-sensitive)
2. Preference alignment (tasks the user prefers)
3. Dependencies (tasks that need to be done before others)
4. Energy levels (when tasks are typically done)
5. Family impact (tasks affecting others)

IMPORTANT: When a user has a preference for a task category (like "Pet care"), prioritize tasks that fall into that category higher than tasks that don't match their preferences.

TASK CATEGORIZATION:
- Pet care tasks include: feeding pets, walking pets, grooming pets, cleaning pet areas, pet health care
- Cooking tasks include: meal preparation, cooking, baking, meal planning
- Laundry tasks include: washing clothes, drying clothes, folding clothes, ironing
- Organization tasks include: tidying, decluttering, organizing spaces
- Plant care tasks include: watering plants, gardening, plant maintenance
- House work tasks include: cleaning, vacuuming, dusting, mopping
- Yard work tasks include: yard, lawn, garden, outdoor
- Family care tasks include: childcare, helping family members

RESPONSE FORMAT:
Return a JSON array of objects with this structure:
[
  {{
    "id": "todo-title",
    "aiPriority": 1,
    "aiReason": "Brief explanation of why this priority"
  }}
]

Respond ONLY with valid JSON, no extra text."""
    
    async def prioritize_todos(self, todos: List[Dict], preferences: Dict[str, Any], prompt: str = None) -> List[Dict[str, Any]]:
        """Prioritize todos using AI"""
        print(f"🤖 AI Prioritize request received: {len(todos)} todos")
        print(f"🤖 Received preferences: {preferences}")
        
        if not prompt:
            prompt = self.build_prioritization_prompt(todos, preferences)
        
        print(f"🤖 Generated prompt: {prompt}")
        
        try:
            print(f"🔑 Claude API Key status: {'Present' if CLAUDE_API_KEY else 'Missing'}")
            print(f"🔑 Claude API Key preview: {CLAUDE_API_KEY[:10] + '...' if CLAUDE_API_KEY else 'None'}")
            
            claude_response = await self.call_claude_api(prompt)
            print(f"🤖 Claude response received, length: {len(claude_response)}")
            print(f"📝 Claude raw response: {claude_response}")
            
            prioritized_todos = self.parse_claude_response(claude_response)
            print(f"✅ Claude parsed response: {prioritized_todos}")
            
        except Exception as claude_error:
            print(f"❌ Claude API failed, using fallback prioritization: {claude_error}")
            print(f"📋 Claude API error details: {type(claude_error).__name__}: {str(claude_error)}")
            
            # Fallback: simple prioritization based on preferences
            print(f"🔄 Using fallback prioritization with preferences: {preferences}")
            prioritized_todos = []
            
            for index, todo in enumerate(todos):
                if not todo.get('completed', False):
                    # Simple keyword-based prioritization
                    title = todo.get('title', '').lower()
                    priority = 999
                    reason = "Fallback prioritization (Claude API unavailable)"
                    
                    # Check for preference matches
                    if preferences.get('pet_care', False):
                        if any(word in title for word in ['feed', 'pet', 'bunny', 'dog', 'cat']):
                            priority = 1
                            reason = "Pet care preference match"
                    
                    if preferences.get('cooking', False):
                        if any(word in title for word in ['cook', 'meal', 'food', 'kitchen']):
                            priority = min(priority, 2)
                            reason = "Cooking preference match"
                    
                    if preferences.get('laundry', False):
                        if any(word in title for word in ['laundry', 'wash', 'clothes']):
                            priority = min(priority, 3)
                            reason = "Laundry preference match"
                    
                    prioritized_todos.append({
                        "id": todo.get('title', ''),
                        "aiPriority": priority if priority != 999 else index + 1,
                        "aiReason": reason
                    })
        
        # Merge AI prioritization with original todos
        enhanced_todos = []
        for todo in todos:
            # Claude uses todo titles as IDs, so match by title instead of ID
            ai_data = next((p for p in prioritized_todos if p['id'] == todo.get('title', '')), None)
            
            enhanced_todo = {
                **todo,
                "aiPriority": ai_data['aiPriority'] if ai_data else 999,
                "aiReason": ai_data['aiReason'] if ai_data else "No AI analysis available"
            }
            enhanced_todos.append(enhanced_todo)
        
        # Sort by AI priority
        enhanced_todos.sort(key=lambda x: x.get('aiPriority', 999))
        
        print(f"📤 AI Prioritization - Sending enhanced todos: {[(t.get('title'), t.get('aiPriority'), t.get('aiReason')) for t in enhanced_todos]}")
        
        return enhanced_todos
    
    def build_insights_prompt(self, todos: List[Dict], preferences: Dict[str, Any]) -> str:
        """Build the prompt for AI insights"""
        recent_todos = todos[-10:] if len(todos) > 10 else todos
        preferences_text = self.format_preferences(preferences)
        
        todos_text = "\n".join([
            f"- {todo.get('title', 'Untitled')} ({'Completed' if todo.get('completed', False) else 'Pending'})"
            for todo in recent_todos
        ]) if recent_todos else "No recent todos."
        
        return f"""You are an AI assistant providing insights about household task management.

USER PREFERENCES:
{preferences_text}

RECENT TODOS:
{todos_text}

TASK: Provide a brief, helpful insight about the user's task management patterns, productivity tips, or suggestions based on their preferences and recent activity.

Keep the response concise (1-2 sentences) and actionable.

Respond with just the insight text, no extra formatting or commentary."""
    
    async def get_insights(self, todos: List[Dict], preferences: Dict[str, Any]) -> str:
        """Get AI insights for todos"""
        prompt = self.build_insights_prompt(todos, preferences)
        
        try:
            claude_response = await self.call_claude_api(prompt)
            return claude_response.strip()
        except Exception as e:
            print(f"❌ Failed to get AI insights: {e}")
            return "AI insights are temporarily unavailable. Keep up the great work on your tasks!"

"""Azure OpenAI client for natural language inventory management."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Coroutine

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# Lazy-loaded client
_client: AzureOpenAI | None = None


def get_client() -> AzureOpenAI:
    """Get or create the Azure OpenAI client."""
    global _client
    if _client is None:
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not endpoint:
            raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is required")

        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if api_key:
            _client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version="2024-10-21",
            )
        else:
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            _client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version="2024-10-21",
            )
        logger.info(f"Initialized Azure OpenAI client for {endpoint}")

    return _client


# Tool definitions for the LLM
INVENTORY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_item",
            "description": "Add a new item to inventory or increase quantity of existing item",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the item (e.g., 'chicken breast', 'AA batteries')",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items to add",
                        "minimum": 1,
                    },
                    "category": {
                        "type": "string",
                        "description": "Category for the item (e.g., 'meat', 'electronics', 'vegetables')",
                    },
                    "location": {
                        "type": "string",
                        "description": "Storage location (e.g., 'Freezer', 'Garage', 'Pantry')",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description or notes about the item",
                    },
                    "expiration_date": {
                        "type": "string",
                        "description": (
                            "Optional expiration date in ISO format (YYYY-MM-DD)."
                            " Use for perishable items like food, medicine, etc."
                        ),
                    },
                },
                "required": ["name", "quantity", "category", "location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_item",
            "description": "Remove an item from inventory or reduce its quantity",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {
                        "type": "integer",
                        "description": "ID of the item to remove (from search results)",
                    },
                    "quantity": {
                        "type": "integer",
                        "description": "Number of items to remove. If omitted or greater than current quantity, removes all.",
                        "minimum": 1,
                    },
                    "lot_id": {
                        "type": "integer",
                        "description": (
                            "Optional: ID of a specific lot/batch to remove from."
                            " If not specified, removes from the oldest lot first."
                        ),
                    },
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_items",
            "description": "Search inventory using natural language. Finds items by name, category, description, or location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g., 'chicken', 'frozen meat', 'batteries in garage')",
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional: filter to a specific location",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_items",
            "description": (
                "List all items in inventory, optionally filtered by location or category."
                " Returns items with their batch dates showing when they were added."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Optional: filter to a specific location (e.g., 'Freezer')",
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional: filter to a specific category (e.g., 'meat')",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_locations",
            "description": "List all storage locations",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_oldest_items",
            "description": (
                "Get the oldest items in inventory based on when they were added."
                " Use this when the user asks about old stock, what they should use"
                " first, or what's been sitting longest."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Optional: filter to a specific location (e.g., 'Freezer')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of items to return (default: 10)",
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_expiring_items",
            "description": (
                "Get items that are expiring soon. Use this when the user asks"
                " what's expiring, what needs to be used before it goes bad,"
                " or wants to check expiration dates."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Number of days to look ahead (default: 7)",
                        "minimum": 1,
                        "maximum": 365,
                    },
                },
            },
        },
    },
]

SYSTEM_PROMPT = """You are an inventory management assistant. You help users track items
stored in various locations like freezers, garages, pantries, closets, and storage bins.

Your capabilities:
- Add items to inventory (with name, quantity, category, and location)
- Remove items or reduce quantities (with lot/batch tracking)
- Search for items using natural language
- List items by location or category
- Find the oldest items in any location
- Suggest recipes or uses based on what the user has

When users describe items naturally, extract the relevant details. For example:
- "I put 3 bags of frozen chicken in the freezer" → add_item with name="frozen chicken bags",
  quantity=3, category="meat", location="Freezer"
- "Do I have any batteries?" → search_items with query="batteries"
- "What's in the garage?" → list_items with location="Garage"
- "I used 2 of the AA batteries" → first search, then remove_item with appropriate quantity
- "What's the oldest stuff in my freezer?" → get_oldest_items with location="Freezer"

IMPORTANT - Recipe and suggestion questions:
When the user asks "What recipe should I make?", "What can I cook?", "What should I make for dinner?",
or any similar question about recipes, meal planning, or suggestions based on their inventory:
1. FIRST call list_items with NO filters to see everything they have
2. THEN provide recipe suggestions based on the actual inventory
Do NOT ask the user to list their items — you can look them up yourself!

When removing items, if the item has multiple batches/lots added at different times,
mention the batch dates so the user knows which ones they're removing (e.g., "You have
3 from Jan 5 and 2 from Feb 10"). If the user doesn't specify which batch, remove from
the oldest first.

Always be helpful and conversational. If you need more information to complete an action, ask the user.
When reporting search or list results, summarize them naturally rather than just listing raw data.
If an action succeeds, confirm it in a friendly way."""

# Load system prompt from file (allows customization without code changes)
_PROMPT_FILE = Path(__file__).parent / "prompts" / "system.txt"


def _get_system_prompt() -> str:
    """Load system prompt from file, falling back to default if not found."""
    if _PROMPT_FILE.exists():
        return _PROMPT_FILE.read_text(encoding="utf-8").strip()
    return SYSTEM_PROMPT


async def process_chat_with_tools(
    message: str,
    tool_handlers: dict[str, Callable[..., Coroutine[Any, Any, Any]]],
) -> str:
    """Process a chat message with tool calling support.

    Args:
        message: User's natural language message
        tool_handlers: Dict mapping tool names to async handler functions

    Returns:
        Assistant's response string
    """
    client = get_client()
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-5-nano")

    messages = [
        {"role": "system", "content": _get_system_prompt()},
        {"role": "user", "content": message},
    ]

    max_iterations = 5
    tools_called = False
    for _iteration in range(max_iterations):
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=INVENTORY_TOOLS,
            tool_choice="auto",
        )

        assistant_message = response.choices[0].message

        if not assistant_message.tool_calls:
            fallback = "Done." if tools_called else "I'm not sure how to help with that."
            return assistant_message.content or fallback

        # Add assistant message to history
        tools_called = True
        messages.append(assistant_message)

        # Process each tool call
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)

            logger.info(f"Tool call: {function_name}({function_args})")

            # Execute the tool
            if function_name in tool_handlers:
                try:
                    result = await tool_handlers[function_name](**function_args)
                    tool_result = json.dumps(result)
                except Exception as e:
                    logger.error(f"Tool error: {e}")
                    tool_result = json.dumps({"error": str(e)})
            else:
                tool_result = json.dumps({"error": f"Unknown tool: {function_name}"})

            # Add tool result to messages
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_result,
                }
            )

    # Safety: hit max iterations, get a final text response
    final_response = client.chat.completions.create(
        model=deployment,
        messages=messages,
    )
    return final_response.choices[0].message.content or "Done."


def generate_display_name(raw_name: str) -> str:
    """Generate a proper display name for a location.
    
    Uses simple rules to convert raw names to proper display format:
    - Title case each word
    - Detect possessive names (ending in 's' after a name) and add apostrophe
    
    Args:
        raw_name: Raw location name input (e.g., "tims pocket", "garage")
    
    Returns:
        Properly formatted display name (e.g., "Tim's Pocket", "Garage")
    """
    
    # Common name patterns that should be possessive
    # Words ending in 's' that look like names followed by a non-'s' word
    words = raw_name.lower().split()
    result_words = []
    
    for i, word in enumerate(words):
        # Check if this looks like a possessive name (ends in 's', followed by another word)
        # Common names: tims, bobs, jacks, marys, lisas, annas, sams, etc.
        if (i < len(words) - 1 and
            word.endswith('s') and
            len(word) >= 3 and
            not word.endswith('ss') and  # Not words like "glass"
            word[:-1].isalpha()):  # The base is all letters
            # Likely a possessive - add apostrophe before 's'
            result_words.append(word[:-1].title() + "'s")
        else:
            result_words.append(word.title())
    
    return " ".join(result_words)

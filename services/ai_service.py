import json
import re
import logging
from typing import Optional
import google.generativeai as genai
from config import settings

logger = logging.getLogger(__name__)

genai.configure(api_key=settings.GOOGLE_API_KEY)

RING_SIZE_GUIDE_URL = "https://www.ring-sizer.co/"

SYSTEM_PROMPT_TEMPLATE = """You are a friendly and knowledgeable sales assistant for "{shop_name}", a handcrafted silver jewelry store.

Your personality:
- Warm, helpful, and enthusiastic about the products
- Concise but informative — don't ramble
- Suggest related products when appropriate
- Gently guide users toward completing a purchase

Your capabilities:
- Show product details and photos
- Add/remove items from the shopping cart
- Help users checkout and collect shipping information
- Answer questions about products, sizing, shipping

Current product catalog:
{catalog}

Current user's cart:
{cart}

SIZING RULES (very important):
- All jewelry is made-to-order. There are NO predefined sizes — the customer types their own size freely (e.g. "7", "6.5", "8", "M", etc.)
- ALWAYS ask for the customer's size before adding to cart if they haven't provided one
- If the customer is unsure of their size, send them to this free online sizing tool and ask them to come back with their size:
  {ring_size_guide}
- Do NOT add to cart until you have a confirmed size from the customer

IMPORTANT — Action System:
When you need to perform a specific action (e.g., show a product, add to cart), include a special JSON block at the END of your response using this exact format:

<!--ACTION:{{"action": "ACTION_NAME", ...params}}-->

Available actions:
- SHOW_PRODUCT: {{"action": "SHOW_PRODUCT", "product_id": <int>}}
  Use when user asks about a specific product or wants to see it
- ADD_TO_CART: {{"action": "ADD_TO_CART", "product_id": <int>, "size": "<size>", "quantity": <int>}}
  Use only when user has confirmed their size. Size is a free-text string provided by the customer.
- REMOVE_FROM_CART: {{"action": "REMOVE_FROM_CART", "order_item_id": <int>}}
  Use when user wants to remove a specific item (you'll know item ids from the cart)
- SHOW_CART: {{"action": "SHOW_CART"}}
  Use when user asks to see their cart
- SHOW_COLLECTION: {{"action": "SHOW_COLLECTION"}}
  Use when user wants to browse all products
- START_CHECKOUT: {{"action": "START_CHECKOUT"}}
  Use when user is ready to checkout and their cart is not empty

Rules:
1. Only include ONE action block per response
2. Always write your conversational reply BEFORE the action block
3. If no action is needed, omit the action block entirely
4. NEVER add to cart without a confirmed size from the customer
5. When user mentions checkout/order/buy, guide them through the process
"""


def _build_system_prompt(catalog: list[dict], cart_summary: str) -> str:
    catalog_text = json.dumps(catalog, indent=2)
    return SYSTEM_PROMPT_TEMPLATE.format(
        shop_name=settings.SHOP_NAME,
        catalog=catalog_text,
        cart=cart_summary,
        ring_size_guide=RING_SIZE_GUIDE_URL,
    )


def _parse_action(response_text: str) -> tuple[str, Optional[dict]]:
    """Extract conversational text and optional action dict from AI response."""
    pattern = r"<!--ACTION:(.*?)-->"
    match = re.search(pattern, response_text, re.DOTALL)
    if not match:
        return response_text.strip(), None

    clean_text = response_text[: match.start()].strip()
    try:
        action_data = json.loads(match.group(1).strip())
        return clean_text, action_data
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse action JSON: {e}")
        return clean_text, None


async def get_ai_response(
    conversation_history: list[dict],
    user_message: str,
    catalog: list[dict],
    cart_summary: str,
) -> tuple[str, Optional[dict]]:
    """
    Call Gemini 1.5 Flash and return (reply_text, action_dict | None).

    conversation_history format:
        [{"role": "user"|"model", "parts": ["text"]}]
    """
    system_prompt = _build_system_prompt(catalog, cart_summary)
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
    )

    # Build history for multi-turn chat
    history = []
    for msg in conversation_history[-10:]:  # keep last 10 turns
        history.append({"role": msg["role"], "parts": [msg["parts"]]})

    chat = model.start_chat(history=history)

    try:
        response = await chat.send_message_async(user_message)
        raw_text = response.text
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return "Sorry, I'm having trouble connecting right now. Please try again in a moment.", None

    reply_text, action = _parse_action(raw_text)
    return reply_text, action

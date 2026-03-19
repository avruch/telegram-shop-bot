# ============================================================
#  texts.py — All user-facing bot messages in one place
#  Edit this file to change anything the bot says.
# ============================================================

# ── /start welcome ──────────────────────────────────────────
WELCOME = """👋 Welcome to *{shop_name}*!

I'm your personal shopping assistant.

Just chat with me naturally! Try saying:
  _"Show me your products"_
  _"I'm looking for a ring in size 7"_
  _"What rings do you have?"_
"""

# ── /help ────────────────────────────────────────────────────
HELP = """*Available Commands:*

/start — Restart and clear conversation
/cart — View your current cart
/products — Browse all products
/checkout — Begin the checkout process
/help — Show this help message

Or just chat naturally — I understand plain English! 😊"""

# ── Product card caption ─────────────────────────────────────
PRODUCT_CAPTION = (
    "*{name}*\n"
    "{description}\n"
    "💲 *${price:.2f}*\n"
    "tap Add to Cart and type your size_"
)

# ── Size collection ──────────────────────────────────────────
ASK_SIZE = (
    "Great choice! 💍 *{product_name}*\n\n"
    "Please type your size (e.g. *7*, *6.5*, *8*):"
)

SIZE_GUIDE_REMINDER = (
    "No worries! Use this free online tool to find your exact size, "
    "then come back and type it here:\n"
    "👉 {ring_size_guide}"
)

ITEM_ADDED = "✅ *{product_name}* (size {size}) added to your cart!"

# ── Checkout flow ────────────────────────────────────────────
CHECKOUT_ASK_NAME = (
    "Great! Let's get your order shipped. 📦\n\n"
    "First, please enter your *full name* for the shipping label:"
)

CHECKOUT_ASK_ADDRESS = (
    "Got it! Now please enter your *shipping address*:\n"
    "_(Include street, city, state/province, and postal code)_"
)

CHECKOUT_ASK_PHONE = (
    "Almost there! Please enter your *phone number*:\n"
    "_(Include country code, e.g. +1 555 123 4567)_"
)

CHECKOUT_INVALID_NAME    = "Please enter your *first and last name* (at least two words)."
CHECKOUT_INVALID_ADDRESS = "That doesn't look like a full address. Please include street number, city, and postal code."
CHECKOUT_INVALID_PHONE   = "Please enter a valid phone number with country code (e.g. *+1 555 123 4567*)."
CHECKOUT_NO_ORDER        = "Something went wrong. Please start over with /checkout."

PAYMENT_INSTRUCTIONS = (
    "*Order Summary:*\n"
    "📛 Name: {shipping_name}\n"
    "📍 Address: {shipping_address}\n"
    "📞 Phone: {shipping_phone}\n"
    "💰 Total: *${total:.2f}*\n\n"
    "*Payment Instructions:*\n"
    "Please send *${total:.2f}* to our PayPal:\n"
    "👉 {paypal_link}\n\n"
    "After completing your payment, please upload a *screenshot* of the transaction here. "
    "We'll confirm your order as soon as we verify it! ✅"
)

AWAITING_SCREENSHOT = (
    "Please upload a *screenshot* of your PayPal payment (${total:.2f}) to confirm your order.\n"
    "Send it as an image/photo. 📸"
)

SCREENSHOT_RECEIVED = (
    "✅ *Payment screenshot received!*\n\n"
    "Your order is now under review. We'll notify you once your payment is confirmed. "
    "This usually takes a few minutes. Thank you! 🙏"
)

# ── Admin notifications ──────────────────────────────────────
ADMIN_NEW_ORDER = (
    "🔔 *New Payment Pending — Order #{order_id}*\n\n"
    "{summary}\n\n"
    "👤 Customer: @{username} (ID: `{user_id}`)\n\n"
    "Please verify the screenshot below and confirm or reject:"
)

ADMIN_CONFIRMED = (
    "✅ *Payment CONFIRMED — Order #{order_id}*\n\n"
    "{summary}\n\n"
    "Customer notified."
)

ADMIN_REJECTED = "❌ *Payment REJECTED — Order #{order_id}*\n\nStock restored. Customer notified."

# ── Customer notifications (from admin action) ───────────────
CUSTOMER_ORDER_CONFIRMED = (
    "🎉 *Your payment has been confirmed!*\n\n"
    "{summary}\n\n"
    "Your order is now being prepared for shipping. "
    "Thank you for shopping with us! 💙"
)

CUSTOMER_ORDER_REJECTED = (
    "❌ *Payment Verification Failed — Order #{order_id}*\n\n"
    "We were unable to verify your payment. This could be due to:\n"
    "• Incorrect amount sent\n"
    "• Screenshot not matching the transaction\n\n"
    "Your cart has been restored. Please try again or contact support."
)

# ── Cart ─────────────────────────────────────────────────────
CART_EMPTY        = "🛒 Your cart is empty."
CART_HEADER       = "🛒 *Your Cart:*\n"
CART_ITEM_LINE    = "• {name} ({size}) × {qty} — ${subtotal:.2f}"
CART_TOTAL_LINE   = "\n💰 *Total: ${total:.2f}*"
CART_CLEARED      = "🛒 Your cart has been cleared."
CART_EMPTY_ALERT  = "Your cart is empty!"

# ── Misc errors / prompts ────────────────────────────────────
NO_PRODUCTS        = "No products available right now."
PRODUCTS_HEADER    = "Here are all our products:\n"
COLLECTION_HEADER  = "Here's our full collection! 🛍"
TEXT_ONLY          = "Please send me a text message. 😊"
CART_EMPTY_BROWSE  = "Your cart is empty! Browse our products first. 🛒"
CART_EMPTY_CHECKOUT = "Your cart is empty! Add some items before checking out. 🛒"
CHECKOUT_START     = "Let's get your order shipped! 📦\n\nPlease enter your *full name* for the shipping label:"
PRODUCT_NOT_FOUND  = "Sorry, I couldn't find that product."
SCREENSHOT_ERROR   = "Something went wrong. Please start over with /start."

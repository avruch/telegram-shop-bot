# AI-Powered Telegram E-Commerce Bot

An intelligent Telegram shopping bot that acts as a personal sales assistant using Google Gemini 1.5 Flash. Built with `aiogram 3.x`, `FastAPI`, and `SQLite`.

## Features

- **AI-driven chat**: Natural language understanding via Gemini 1.5 Flash
- **Product catalog**: Photo cards with size selection inline buttons
- **Live cart**: Single editable message with ➕ ➖ ❌ controls
- **Inventory management**: Real-time stock checks per size
- **Checkout flow**: FSM-guided shipping info collection
- **Payment verification**: PayPal link + screenshot upload → admin review
- **Admin panel**: Confirm/reject payments directly in Telegram
- **Google Sheets import**: Load/refresh the product catalog from a Google Sheet
- **Google Sheets export**: Sync orders and inventory to a Google Sheet in real time

## Setup

### 1. Get your credentials

| Credential | Where to get it |
|---|---|
| `BOT_TOKEN` | Talk to [@BotFather](https://t.me/BotFather) on Telegram |
| `ADMIN_CHAT_ID` | Message [@userinfobot](https://t.me/userinfobot) — use your personal ID |
| `GOOGLE_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| `GOOGLE_SHEETS_ID` | ID from your product catalog sheet URL (`/spreadsheets/d/<ID>/edit`) |
| `GOOGLE_SHEETS_EXPORT_ID` | ID from your export sheet URL (for orders/inventory export) |

### 2. Install dependencies

```bash
cd telegram-shop-bot
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env with your actual values
```

> 💡 Optional: set `REDIS_URL` if you want persistent FSM state across restarts (recommended for production).

### 4. Seed the database

```bash
python database/seed.py
```

### 5. Run in development (polling mode)

```bash
python main.py
```

## Production Deployment (Webhook)

Set `WEBHOOK_URL` in your `.env` to your public URL (e.g. `https://myapp.railway.app`), then:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The bot will automatically register the webhook at startup.

### Deploy to Railway

1. Push code to GitHub
2. Create new Railway project → Deploy from GitHub
3. Add environment variables in Railway dashboard
4. Railway provides the public URL — set it as `WEBHOOK_URL`

### Deploy to Render

1. Create new Web Service → Connect GitHub repo
2. Build Command: `pip install -r requirements.txt`
3. Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in Render dashboard

## Architecture

```
telegram-shop-bot/
├── main.py              # FastAPI app + polling/webhook entry point
├── bot.py               # Bot + Dispatcher singletons
├── config.py            # Pydantic settings from .env
├── database/
│   ├── db.py            # aiosqlite setup, table creation
│   ├── models.py        # Typed dataclasses for DB rows
│   └── seed.py          # Sample product seeder
├── states/
│   └── states.py        # FSM: browsing → checkout → payment
├── keyboards/
│   └── keyboards.py     # Inline keyboard builders
├── services/
│   ├── ai_service.py           # Gemini 1.5 Flash integration
│   ├── cart_service.py         # Cart CRUD operations
│   ├── order_service.py        # Order lifecycle management
│   ├── inventory_service.py    # Stock management
│   ├── sheets_service.py       # Google Sheets product import
│   └── sheets_export_service.py # Google Sheets order/inventory export
└── handlers/
    ├── start.py         # /start, /help, /cart, /products
    ├── chat.py          # AI-powered main chat (browsing state)
    ├── cart.py          # Inline button callbacks for cart
    ├── payment.py       # Checkout FSM + screenshot upload
    └── admin.py         # Admin confirm/reject payment
```

## How the AI Works

Each user message goes through this pipeline:

1. Load the user's cart state and full product catalog
2. Build a **system prompt** that defines the bot's role, available products, and action format
3. Call **Gemini 1.5 Flash** with the last 10 conversation turns as context
4. Parse the response for an `<!--ACTION:{...}-->` block
5. Execute the action (show product, add to cart, start checkout, etc.)
6. Send the text reply + any UI elements (photos, keyboards)

### Supported AI Actions

| Action | Triggered when... |
|---|---|
| `SHOW_PRODUCT` | User asks about a specific product |
| `ADD_TO_CART` | User wants to add an item |
| `REMOVE_FROM_CART` | User wants to remove an item |
| `SHOW_CART` | User asks to see their cart |
| `SHOW_COLLECTION` | User wants to browse everything |
| `START_CHECKOUT` | User is ready to buy |

## User Flow

```
/start
  └─► AI chat (browsing)
        ├─► Show products, add to cart
        └─► Checkout
              ├─► Enter Name
              ├─► Enter Address
              ├─► Enter Phone
              └─► Send PayPal screenshot
                    └─► Admin receives notification
                          ├─► [Confirm] → Customer notified, order = Paid
                          └─► [Reject] → Stock restored, customer notified
```

## Google Sheets Integration

### Product Catalog Import

Set `GOOGLE_SHEETS_ID` in `.env` to pull products from a Google Sheet. Sheet format (row 1 is a header, data from row 2):

| Column A | Column B | Column C | Column D | Column E |
|---|---|---|---|---|
| Name | Description | Price | Image URL | Stock |

Stock can be a JSON object (`{"S": 5, "M": 10}`) or a plain integer (treated as `{"ONE SIZE": N}`).

- **Public sheet**: Share as "Anyone with the link (Viewer)" — no extra credentials needed.
- **Private sheet**: Also requires a valid `GOOGLE_API_KEY` from Google Cloud.

Refresh products at runtime (admin only):
```
/refresh_products
```
Falls back to `SAMPLE_PRODUCTS` if the sheet is unconfigured or returns no rows.

### Orders & Inventory Export

Set `GOOGLE_SHEETS_EXPORT_ID` to a separate spreadsheet that has two tabs named **Orders** and **Inventory**. The export sheet requires authenticated write access (service account via `GOOGLE_APPLICATION_CREDENTIALS` is recommended).

Orders and inventory are updated automatically when payments are confirmed/rejected. Manual admin commands:

```
/export_orders      — full re-export of all submitted orders to the Orders tab
/export_inventory   — snapshot of current stock to the Inventory tab
```

## Customizing Products

Edit `database/seed.py` and update the `SAMPLE_PRODUCTS` list, then re-run:
```bash
python database/seed.py
```

Or connect a Google Sheet and run `/refresh_products` — see [Google Sheets Integration](#google-sheets-integration) above.

Products support flexible size keys: `"S"`, `"M"`, `"L"`, `"XL"`, `"ONE SIZE"`, etc.

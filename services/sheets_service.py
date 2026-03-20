"""
Google Sheets integration for product catalog management.

Expected sheet structure (first row is a header, data starts at row 2):
    Column A: Name        — Product name/SKU (e.g. "R0001")
    Column B: Description — Short product description (can be empty)
    Column C: Price       — Numeric price (e.g. 160)
    Column D: Image URL   — Direct image URL
    Column E: Stock       — JSON string for size→qty map (e.g. {"ONE SIZE": 10})
                            OR a plain integer for single-size stock (e.g. 10)

Example sheet rows:
    Name   | Description        | Price | Image URL          | Stock
    R0001  | Silver ring        | 160   | https://...        | {"ONE SIZE": 10}
    R0002  | Gold bracelet      | 130   | https://...        | 10

To make the sheet accessible:
    - Public sheet: File → Share → "Anyone with the link" (Viewer)
      Then set GOOGLE_SHEETS_ID in your .env — no API key required.
    - Private sheet: Also set GOOGLE_API_KEY (Google Cloud → APIs & Services → Credentials).
"""

import json
import logging
from typing import Optional

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

# Google Sheets API v4 base URL
_SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

# The range to read — reads all data from the first sheet starting at row 2
# (row 1 is assumed to be the header)
_DEFAULT_RANGE = "Sheet1!A2:E"


async def fetch_products_from_sheets(
    sheet_id: Optional[str] = None,
    api_key: Optional[str] = None,
    sheet_range: str = _DEFAULT_RANGE,
) -> list[dict]:
    """
    Fetch product data from a Google Sheet and return a list of product dicts.

    Each returned dict has the keys:
        name, description, price, image_url, stock_json

    This matches the format expected by SAMPLE_PRODUCTS and the products table.

    Args:
        sheet_id:    Google Sheet ID (from the URL: /spreadsheets/d/<ID>/edit).
                     Defaults to settings.GOOGLE_SHEETS_ID.
        api_key:     Google API key for private sheets.
                     Defaults to settings.GOOGLE_API_KEY (optional).
        sheet_range: A1 notation range to read. Defaults to "Sheet1!A2:E".

    Returns:
        List of product dicts, or an empty list if the fetch fails or the
        sheet is empty.
    """
    resolved_sheet_id = sheet_id or getattr(settings, "GOOGLE_SHEETS_ID", "")
    resolved_api_key = api_key or getattr(settings, "GOOGLE_API_KEY", "")

    if not resolved_sheet_id or resolved_sheet_id == "YOUR_GOOGLE_SHEET_ID":
        logger.warning(
            "sheets_service: GOOGLE_SHEETS_ID is not configured — skipping sheets fetch."
        )
        return []

    url = f"{_SHEETS_BASE}/{resolved_sheet_id}/values/{sheet_range}"
    params: dict = {"majorDimension": "ROWS"}
    if resolved_api_key and resolved_api_key != "YOUR_GOOGLE_API_KEY":
        params["key"] = resolved_api_key

    logger.info(f"sheets_service: Fetching products from sheet '{resolved_sheet_id}' range '{sheet_range}'")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 403:
                    logger.error(
                        "sheets_service: Access denied (HTTP 403). "
                        "Make sure the sheet is public or a valid GOOGLE_API_KEY is set."
                    )
                    return []
                if resp.status == 404:
                    logger.error(
                        f"sheets_service: Sheet not found (HTTP 404). "
                        f"Check that GOOGLE_SHEETS_ID='{resolved_sheet_id}' is correct."
                    )
                    return []
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(
                        f"sheets_service: Unexpected HTTP {resp.status} from Sheets API: {body[:200]}"
                    )
                    return []

                data = await resp.json()
    except aiohttp.ClientError as exc:
        logger.error(f"sheets_service: Network error while fetching sheet: {exc}")
        return []
    except Exception as exc:
        logger.error(f"sheets_service: Unexpected error during fetch: {exc}")
        return []

    rows: list[list[str]] = data.get("values", [])
    if not rows:
        logger.warning("sheets_service: Sheet returned no data rows.")
        return []

    products = []
    for row_idx, row in enumerate(rows, start=2):  # start=2 because row 1 is the header
        # Skip completely empty rows
        if not any(cell.strip() for cell in row if cell):
            continue

        # Pad the row to 5 columns so we can safely index
        padded = (row + ["", "", "", "", ""])[:5]
        name_raw, desc_raw, price_raw, image_raw, stock_raw = padded

        name = name_raw.strip()
        if not name:
            logger.debug(f"sheets_service: Skipping row {row_idx} — empty Name column.")
            continue

        description = desc_raw.strip()
        image_url = image_raw.strip()

        # Parse price
        try:
            price = float(price_raw.strip().replace(",", ""))
        except (ValueError, AttributeError):
            logger.warning(
                f"sheets_service: Row {row_idx} ('{name}') has invalid price "
                f"'{price_raw}' — skipping row."
            )
            continue

        # Parse stock — accept a JSON object or a plain integer
        stock_raw_stripped = stock_raw.strip()
        if not stock_raw_stripped:
            stock_json = json.dumps({"ONE SIZE": 10})
        elif stock_raw_stripped.lstrip("-").isdigit():
            # Plain integer → treat as ONE SIZE quantity
            stock_json = json.dumps({"ONE SIZE": int(stock_raw_stripped)})
        else:
            try:
                parsed_stock = json.loads(stock_raw_stripped)
                if not isinstance(parsed_stock, dict):
                    raise ValueError("Stock JSON must be an object")
                stock_json = json.dumps(parsed_stock)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning(
                    f"sheets_service: Row {row_idx} ('{name}') has invalid stock "
                    f"'{stock_raw_stripped}' ({exc}) — defaulting to {{\"ONE SIZE\": 10}}."
                )
                stock_json = json.dumps({"ONE SIZE": 10})

        products.append(
            {
                "name": name,
                "description": description,
                "price": price,
                "image_url": image_url,
                "stock_json": stock_json,
            }
        )

    logger.info(f"sheets_service: Parsed {len(products)} product(s) from sheet.")
    return products

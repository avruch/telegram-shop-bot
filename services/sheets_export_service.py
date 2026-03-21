"""
Google Sheets export service for orders and inventory.

Exports order and inventory data to a dedicated Google Sheet for real-time
visibility and analysis. All exports are non-blocking — failures are logged
but never propagate to callers, so the bot continues operating normally if
the sheet is unavailable or misconfigured.

Expected export sheet structure
--------------------------------
The target spreadsheet (GOOGLE_SHEETS_EXPORT_ID) should contain two named
tabs: "Orders" and "Inventory". Create them manually before enabling exports.

Orders sheet (append-only log):
    Column A: Order ID
    Column B: User ID
    Column C: Status
    Column D: Total Price
    Column E: Items          — e.g. "R0001 (qty 2), R0002 (qty 1)"
    Column F: Shipping Name
    Column G: Shipping Address
    Column H: Shipping Phone
    Column I: Created At

Example row:
    1 | 123456789 | Pending | 450.00 | R0001 (qty 2), R0002 (qty 1) | John Doe | 123 Main St | 555-1234 | 2026-03-21 10:30:00

Inventory sheet (always-current snapshot):
    Column A: Product ID
    Column B: Product Name
    Column C: Price
    Column D: Stock          — JSON string, e.g. {"ONE SIZE": 8}
    Column E: Last Updated

Example rows:
    1 | R0001 | 160.00 | {"ONE SIZE": 8} | 2026-03-21 10:35:00
    2 | R0002 | 130.00 | {"ONE SIZE": 9} | 2026-03-21 10:35:00

Authentication
--------------
- Public sheet (read-only via API key): set GOOGLE_API_KEY.
- Authenticated writes: the append/clear/update operations used here require
  OAuth2 or a service account. Configure gspread with a service account JSON
  and set GOOGLE_APPLICATION_CREDENTIALS, or use the GOOGLE_API_KEY for
  sheets that allow unauthenticated writes (uncommon).
- For simplest setup: share the export sheet with your service account email
  and let gspread handle auth automatically via GOOGLE_APPLICATION_CREDENTIALS.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp

from config import settings

logger = logging.getLogger(__name__)

_SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"

# Tab names inside the export spreadsheet
_ORDERS_TAB = "Orders"
_INVENTORY_TAB = "Inventory"


def _is_export_configured() -> bool:
    """Return True if the export sheet ID is set to a real value."""
    export_id = getattr(settings, "GOOGLE_SHEETS_EXPORT_ID", "")
    return bool(export_id) and export_id != "YOUR_EXPORT_SHEET_ID"


def _api_key() -> Optional[str]:
    key = getattr(settings, "GOOGLE_API_KEY", "")
    return key if key and key != "YOUR_GOOGLE_API_KEY" else None


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------

async def _sheets_get(path: str, params: Optional[dict] = None) -> Optional[dict]:
    """GET request to the Sheets API. Returns parsed JSON or None on error."""
    url = f"{_SHEETS_BASE}/{settings.GOOGLE_SHEETS_EXPORT_ID}{path}"
    req_params: dict = {}
    if params:
        req_params.update(params)
    api_key = _api_key()
    if api_key:
        req_params["key"] = api_key

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=req_params, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(
                        f"sheets_export: GET {path} returned HTTP {resp.status}: {body[:300]}"
                    )
                    return None
                return await resp.json()
    except Exception as exc:
        logger.error(f"sheets_export: GET {path} failed: {exc}")
        return None


async def _sheets_post(path: str, payload: dict, params: Optional[dict] = None) -> Optional[dict]:
    """POST request to the Sheets API. Returns parsed JSON or None on error."""
    url = f"{_SHEETS_BASE}/{settings.GOOGLE_SHEETS_EXPORT_ID}{path}"
    req_params: dict = {}
    if params:
        req_params.update(params)
    api_key = _api_key()
    if api_key:
        req_params["key"] = api_key

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                params=req_params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status not in (200, 201):
                    body = await resp.text()
                    logger.error(
                        f"sheets_export: POST {path} returned HTTP {resp.status}: {body[:300]}"
                    )
                    return None
                return await resp.json()
    except Exception as exc:
        logger.error(f"sheets_export: POST {path} failed: {exc}")
        return None


async def _sheets_put(path: str, payload: dict, params: Optional[dict] = None) -> Optional[dict]:
    """PUT request to the Sheets API. Returns parsed JSON or None on error."""
    url = f"{_SHEETS_BASE}/{settings.GOOGLE_SHEETS_EXPORT_ID}{path}"
    req_params: dict = {}
    if params:
        req_params.update(params)
    api_key = _api_key()
    if api_key:
        req_params["key"] = api_key

    try:
        async with aiohttp.ClientSession() as session:
            async with session.put(
                url,
                json=payload,
                params=req_params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(
                        f"sheets_export: PUT {path} returned HTTP {resp.status}: {body[:300]}"
                    )
                    return None
                return await resp.json()
    except Exception as exc:
        logger.error(f"sheets_export: PUT {path} failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def append_order_to_sheet(order_id: int) -> bool:
    """
    Fetch order details from the database and append a new row to the
    "Orders" tab of the export sheet.

    Columns: Order ID | User ID | Status | Total Price | Items |
             Shipping Name | Shipping Address | Shipping Phone | Created At

    Returns True on success, False on any failure. Never raises.
    """
    if not _is_export_configured():
        logger.debug("sheets_export: Export sheet not configured — skipping append_order_to_sheet.")
        return False

    try:
        from services.order_service import get_order

        order = await get_order(order_id)
        if not order:
            logger.warning(f"sheets_export: Order {order_id} not found — cannot export.")
            return False

        items_str = ", ".join(
            f"{item.product_name or f'Product#{item.product_id}'} (qty {item.quantity})"
            for item in order.items
        )

        row = [
            order.id,
            order.user_id,
            order.status,
            f"{order.total_price:.2f}",
            items_str,
            order.shipping_name or "",
            order.shipping_address or "",
            order.shipping_phone or "",
            _now_str(),
        ]

        range_notation = f"{_ORDERS_TAB}!A:I"
        path = f"/values/{range_notation}:append"
        payload = {
            "range": range_notation,
            "majorDimension": "ROWS",
            "values": [row],
        }
        result = await _sheets_post(
            path,
            payload,
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
        )
        if result is None:
            return False

        logger.info(f"sheets_export: Appended order {order_id} to '{_ORDERS_TAB}' sheet.")
        return True

    except Exception as exc:
        logger.error(f"sheets_export: Unexpected error in append_order_to_sheet({order_id}): {exc}")
        return False


async def update_order_status_in_sheet(order_id: int) -> bool:
    """
    Find the row for *order_id* in the "Orders" tab and update its Status
    column (column C) to the current status from the database.

    Scans column A for the matching Order ID, then issues a targeted cell
    update. Returns True on success, False on any failure. Never raises.
    """
    if not _is_export_configured():
        logger.debug(
            "sheets_export: Export sheet not configured — skipping update_order_status_in_sheet."
        )
        return False

    try:
        from services.order_service import get_order

        order = await get_order(order_id)
        if not order:
            logger.warning(f"sheets_export: Order {order_id} not found — cannot update status.")
            return False

        # Read column A (Order IDs) to find the matching row
        id_range = f"{_ORDERS_TAB}!A:A"
        data = await _sheets_get(f"/values/{id_range}")
        if data is None:
            return False

        values = data.get("values", [])
        target_row: Optional[int] = None
        for idx, cell_row in enumerate(values, start=1):
            if cell_row and str(cell_row[0]) == str(order_id):
                target_row = idx
                break

        if target_row is None:
            logger.warning(
                f"sheets_export: Order {order_id} not found in '{_ORDERS_TAB}' sheet — "
                "cannot update status. It may not have been exported yet."
            )
            return False

        # Column C is the Status column
        status_range = f"{_ORDERS_TAB}!C{target_row}"
        path = f"/values/{status_range}"
        payload = {
            "range": status_range,
            "majorDimension": "ROWS",
            "values": [[order.status]],
        }
        result = await _sheets_put(path, payload, params={"valueInputOption": "USER_ENTERED"})
        if result is None:
            return False

        logger.info(
            f"sheets_export: Updated order {order_id} status to '{order.status}' "
            f"at row {target_row} in '{_ORDERS_TAB}' sheet."
        )
        return True

    except Exception as exc:
        logger.error(
            f"sheets_export: Unexpected error in update_order_status_in_sheet({order_id}): {exc}"
        )
        return False


async def update_inventory_sheet() -> int:
    """
    Fetch all products from the database, clear the "Inventory" tab, and
    rewrite it with the current stock snapshot.

    Columns: Product ID | Product Name | Price | Stock | Last Updated

    Returns the number of product rows written (0 on failure). Never raises.
    """
    if not _is_export_configured():
        logger.debug(
            "sheets_export: Export sheet not configured — skipping update_inventory_sheet."
        )
        return 0

    try:
        from services.inventory_service import get_all_products

        products = await get_all_products()
        now = _now_str()

        rows = [
            [
                product.id,
                product.name,
                f"{product.price:.2f}",
                product.stock_json,
                now,
            ]
            for product in products
        ]

        # Step 1: Clear the Inventory tab
        clear_path = f"/values/{_INVENTORY_TAB}!A:E:clear"
        cleared = await _sheets_post(clear_path, {})
        if cleared is None:
            logger.error("sheets_export: Failed to clear Inventory sheet.")
            return 0

        if not rows:
            logger.info("sheets_export: No products found — Inventory sheet cleared.")
            return 0

        # Step 2: Write all rows starting at A1
        write_range = f"{_INVENTORY_TAB}!A1:E{len(rows)}"
        path = f"/values/{write_range}"
        payload = {
            "range": write_range,
            "majorDimension": "ROWS",
            "values": rows,
        }
        result = await _sheets_put(path, payload, params={"valueInputOption": "USER_ENTERED"})
        if result is None:
            return 0

        logger.info(
            f"sheets_export: Wrote {len(rows)} product row(s) to '{_INVENTORY_TAB}' sheet."
        )
        return len(rows)

    except Exception as exc:
        logger.error(f"sheets_export: Unexpected error in update_inventory_sheet(): {exc}")
        return 0


async def export_all_orders_to_sheet() -> int:
    """
    Export every non-Cart order to the "Orders" sheet.

    Clears the sheet first, then writes all orders in a single batch.
    Returns the number of rows written. Never raises.
    """
    if not _is_export_configured():
        logger.debug(
            "sheets_export: Export sheet not configured — skipping export_all_orders_to_sheet."
        )
        return 0

    try:
        from services.order_service import get_all_orders

        orders = await get_all_orders()
        # Exclude Cart orders (not yet submitted)
        orders = [o for o in orders if o.status != "Cart"]

        rows = []
        for order in orders:
            items_str = ", ".join(
                f"{item.product_name or f'Product#{item.product_id}'} (qty {item.quantity})"
                for item in order.items
            )
            rows.append([
                order.id,
                order.user_id,
                order.status,
                f"{order.total_price:.2f}",
                items_str,
                order.shipping_name or "",
                order.shipping_address or "",
                order.shipping_phone or "",
                _now_str(),
            ])

        # Clear the Orders tab first
        clear_path = f"/values/{_ORDERS_TAB}!A:I:clear"
        cleared = await _sheets_post(clear_path, {})
        if cleared is None:
            logger.error("sheets_export: Failed to clear Orders sheet.")
            return 0

        if not rows:
            logger.info("sheets_export: No submitted orders to export.")
            return 0

        write_range = f"{_ORDERS_TAB}!A1:I{len(rows)}"
        path = f"/values/{write_range}"
        payload = {
            "range": write_range,
            "majorDimension": "ROWS",
            "values": rows,
        }
        result = await _sheets_put(path, payload, params={"valueInputOption": "USER_ENTERED"})
        if result is None:
            return 0

        logger.info(
            f"sheets_export: Wrote {len(rows)} order row(s) to '{_ORDERS_TAB}' sheet."
        )
        return len(rows)

    except Exception as exc:
        logger.error(f"sheets_export: Unexpected error in export_all_orders_to_sheet(): {exc}")
        return 0

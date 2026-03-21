"""
Web-based admin panel served at /admin.

Authentication: single password set via ADMIN_PASSWORD env var.
Sessions are stored in memory (fine for single-instance Railway deploys).

Routes:
  GET  /admin              → redirect to /admin/orders
  GET  /admin/login        → login form
  POST /admin/login        → authenticate, set session cookie
  GET  /admin/logout       → clear session cookie
  GET  /admin/orders       → live orders table (auto-refreshes every 10s)
  GET  /admin/products     → product catalog manager
  POST /admin/products/add → add a new product
  POST /admin/products/{id}/edit   → update product
  POST /admin/products/{id}/delete → delete product
"""

import json
import secrets
from typing import Optional

from fastapi import APIRouter, Form, Request, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse

from config import settings
from database.db import get_db

router = APIRouter(prefix="/admin", tags=["admin-web"])

# In-memory session store: set of valid token strings
_sessions: set[str] = set()

COOKIE_NAME = "admin_session"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _is_authenticated(token: Optional[str]) -> bool:
    return bool(token and token in _sessions)


def _login_required(token: Optional[str]):
    """Return a redirect to /admin/login if not authenticated, else None."""
    if not _is_authenticated(token):
        return RedirectResponse("/admin/login", status_code=302)
    return None


# ---------------------------------------------------------------------------
# Shared HTML layout
# ---------------------------------------------------------------------------

def _page(title: str, body: str, active: str = "") -> HTMLResponse:
    orders_active = "active" if active == "orders" else ""
    products_active = "active" if active == "products" else ""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} — Admin</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background: #f5f5f5; color: #222; font-size: 14px; }}
    nav {{ background: #1a1a2e; padding: 0 24px; display: flex; align-items: center;
           gap: 8px; height: 52px; }}
    nav .brand {{ color: #fff; font-weight: 700; font-size: 16px; margin-right: 24px; }}
    nav a {{ color: #aaa; text-decoration: none; padding: 6px 14px; border-radius: 6px;
             font-size: 13px; }}
    nav a:hover {{ color: #fff; background: #ffffff18; }}
    nav a.active {{ color: #fff; background: #4f46e5; }}
    nav .logout {{ margin-left: auto; color: #aaa; text-decoration: none;
                   font-size: 13px; }}
    nav .logout:hover {{ color: #fff; }}
    .container {{ max-width: 1100px; margin: 32px auto; padding: 0 16px; }}
    h1 {{ font-size: 22px; margin-bottom: 20px; }}
    h2 {{ font-size: 16px; margin-bottom: 12px; color: #444; }}
    .card {{ background: #fff; border-radius: 10px; box-shadow: 0 1px 4px #0001;
             padding: 24px; margin-bottom: 24px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{ text-align: left; padding: 10px 12px; border-bottom: 2px solid #eee;
          color: #555; font-weight: 600; white-space: nowrap; }}
    td {{ padding: 10px 12px; border-bottom: 1px solid #f0f0f0; vertical-align: top; }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: #fafafa; }}
    .badge {{ display: inline-block; padding: 2px 10px; border-radius: 20px;
              font-size: 11px; font-weight: 600; }}
    .badge-pending {{ background: #fef3c7; color: #92400e; }}
    .badge-paid {{ background: #d1fae5; color: #065f46; }}
    .badge-cart {{ background: #e5e7eb; color: #374151; }}
    .badge-rejected {{ background: #fee2e2; color: #991b1b; }}
    .badge-waiting {{ background: #fde68a; color: #78350f; }}
    .badge-sent {{ background: #bfdbfe; color: #1e40af; }}
    .badge-delivered {{ background: #bbf7d0; color: #14532d; }}
    input, select, textarea {{ border: 1px solid #ddd; border-radius: 6px;
      padding: 7px 10px; font-size: 13px; width: 100%; outline: none; }}
    input:focus, select:focus, textarea:focus {{ border-color: #4f46e5; }}
    .form-row {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                 gap: 12px; margin-bottom: 12px; }}
    .form-group {{ display: flex; flex-direction: column; gap: 4px; }}
    label {{ font-size: 12px; color: #555; font-weight: 500; }}
    .btn {{ padding: 7px 16px; border: none; border-radius: 6px; cursor: pointer;
            font-size: 13px; font-weight: 500; }}
    .btn-primary {{ background: #4f46e5; color: #fff; }}
    .btn-primary:hover {{ background: #4338ca; }}
    .btn-danger {{ background: #ef4444; color: #fff; }}
    .btn-danger:hover {{ background: #dc2626; }}
    .btn-sm {{ padding: 4px 10px; font-size: 12px; }}
    .actions {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .refresh-note {{ font-size: 11px; color: #888; margin-bottom: 16px; }}
    .empty {{ color: #888; font-style: italic; padding: 20px 0; text-align: center; }}
    .inline-form {{ display: inline; }}
    .edit-row {{ display: none; background: #f9f9f9; }}
    .edit-row td {{ padding: 16px 12px; }}
    .edit-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
                  gap: 10px; margin-bottom: 10px; }}
  </style>
</head>
<body>
  <nav>
    <span class="brand">🛍 {settings.SHOP_NAME} Admin</span>
    <a href="/admin/orders" class="{orders_active}">Orders</a>
    <a href="/admin/products" class="{products_active}">Products</a>
    <a href="/admin/logout" class="logout">Logout</a>
  </nav>
  <div class="container">
    {body}
  </div>
</body>
</html>"""
    return HTMLResponse(html)


ORDER_STATUSES = [
    "Pending",
    "Paid",
    "Waiting for Material",
    "Sent",
    "Delivered",
    "Rejected",
]


def _badge(status: str) -> str:
    cls = {
        "Pending": "badge-pending",
        "Paid": "badge-paid",
        "Cart": "badge-cart",
        "Rejected": "badge-rejected",
        "Waiting for Material": "badge-waiting",
        "Sent": "badge-sent",
        "Delivered": "badge-delivered",
    }.get(status, "badge-cart")
    return f'<span class="badge {cls}">{status}</span>'


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", include_in_schema=False)
async def admin_root():
    return RedirectResponse("/admin/orders", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(error: str = ""):
    error_html = f'<p style="color:#ef4444;margin-top:8px;font-size:13px;">{error}</p>' if error else ""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Admin Login</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #f5f5f5;
           display: flex; align-items: center; justify-content: center; height: 100vh; }}
    .box {{ background: #fff; border-radius: 12px; padding: 40px 36px;
            box-shadow: 0 2px 12px #0001; width: 340px; }}
    h1 {{ font-size: 20px; margin-bottom: 6px; }}
    p {{ color: #888; font-size: 13px; margin-bottom: 24px; }}
    label {{ font-size: 12px; color: #555; font-weight: 500; }}
    input {{ border: 1px solid #ddd; border-radius: 6px; padding: 9px 12px;
             font-size: 14px; width: 100%; margin: 6px 0 16px; outline: none; }}
    input:focus {{ border-color: #4f46e5; }}
    button {{ background: #4f46e5; color: #fff; border: none; border-radius: 6px;
              padding: 10px; width: 100%; font-size: 14px; cursor: pointer; }}
    button:hover {{ background: #4338ca; }}
  </style>
</head>
<body>
  <div class="box">
    <h1>Admin Panel</h1>
    <p>{settings.SHOP_NAME}</p>
    <form method="post" action="/admin/login">
      <label>Password</label>
      <input type="password" name="password" autofocus placeholder="Enter admin password">
      {error_html}
      <button type="submit">Sign In</button>
    </form>
  </div>
</body>
</html>"""
    return HTMLResponse(html)


@router.post("/login")
async def login_submit(password: str = Form(...)):
    if password == settings.ADMIN_PASSWORD:
        token = secrets.token_urlsafe(32)
        _sessions.add(token)
        response = RedirectResponse("/admin/orders", status_code=302)
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
        return response
    return RedirectResponse("/admin/login?error=Invalid+password", status_code=302)


@router.get("/logout")
async def logout(admin_session: Optional[str] = Cookie(default=None)):
    _sessions.discard(admin_session)
    response = RedirectResponse("/admin/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@router.get("/orders", response_class=HTMLResponse)
async def orders_page(admin_session: Optional[str] = Cookie(default=None)):
    redirect = _login_required(admin_session)
    if redirect:
        return redirect

    async with get_db() as conn:
        rows = await conn.fetch(
            "SELECT * FROM orders WHERE status != 'Cart' ORDER BY id DESC"
        )
        orders = []
        for row in rows:
            item_rows = await conn.fetch(
                "SELECT oi.quantity, oi.size, p.name FROM order_items oi "
                "JOIN products p ON oi.product_id = p.id WHERE oi.order_id = $1",
                row["id"],
            )
            items_str = ", ".join(
                f"{r['name']} ({r['size']}) ×{r['quantity']}" for r in item_rows
            )
            orders.append({**dict(row), "items_str": items_str})

    if orders:
        rows_html = ""
        for o in orders:
            created = str(o["created_at"])[:16] if o["created_at"] else "—"
            options = "".join(
                f'<option value="{s}" {"selected" if s == o["status"] else ""}>{s}</option>'
                for s in ORDER_STATUSES
            )
            rows_html += f"""<tr>
              <td>#{o['id']}</td>
              <td>{o['user_id']}</td>
              <td>
                <form method="post" action="/admin/orders/{o['id']}/status"
                  style="display:flex;gap:6px;align-items:center;">
                  <select name="status" style="padding:4px 6px;font-size:12px;width:auto;">
                    {options}
                  </select>
                  <button class="btn btn-primary btn-sm" type="submit">Save</button>
                </form>
              </td>
              <td>${o['total_price']:.2f}</td>
              <td>{o['items_str'] or '—'}</td>
              <td>{o['shipping_name'] or '—'}</td>
              <td>{o['shipping_address'] or '—'}</td>
              <td>{o['shipping_phone'] or '—'}</td>
              <td>{created}</td>
            </tr>"""
        table = f"""<table>
          <thead><tr>
            <th>#</th><th>User ID</th><th>Status</th><th>Total</th>
            <th>Items</th><th>Name</th><th>Address</th><th>Phone</th><th>Date</th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>"""
    else:
        table = '<p class="empty">No orders yet.</p>'

    body = f"""
    <h1>Orders</h1>
    <p class="refresh-note">Auto-refreshes every 10 seconds.</p>
    <div class="card">{table}</div>
    <script>setTimeout(() => location.reload(), 10000);</script>
    """
    return _page("Orders", body, active="orders")


@router.post("/orders/{order_id}/status")
async def order_update_status(
    order_id: int,
    admin_session: Optional[str] = Cookie(default=None),
    status: str = Form(...),
):
    redirect = _login_required(admin_session)
    if redirect:
        return redirect

    if status not in ORDER_STATUSES:
        return RedirectResponse("/admin/orders", status_code=302)

    async with get_db() as conn:
        await conn.execute(
            "UPDATE orders SET status=$1 WHERE id=$2", status, order_id
        )
    return RedirectResponse("/admin/orders", status_code=302)


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@router.get("/products", response_class=HTMLResponse)
async def products_page(admin_session: Optional[str] = Cookie(default=None), msg: str = ""):
    redirect = _login_required(admin_session)
    if redirect:
        return redirect

    async with get_db() as conn:
        rows = await conn.fetch("SELECT * FROM products ORDER BY name")

    msg_html = f'<p style="color:#065f46;background:#d1fae5;padding:8px 12px;border-radius:6px;margin-bottom:16px;font-size:13px;">{msg}</p>' if msg else ""

    if rows:
        rows_html = ""
        for p in rows:
            stock = json.loads(p["stock_json"])
            stock_display = ", ".join(f"{s}: {q}" for s, q in stock.items())
            stock_input_val = p["stock_json"].replace('"', '&quot;')
            rows_html += f"""
            <tr id="row-{p['id']}">
              <td>{p['id']}</td>
              <td>{p['name']}</td>
              <td>${p['price']:.2f}</td>
              <td style="max-width:300px;word-break:break-all;">{p['image_url'] or '—'}</td>
              <td>{stock_display}</td>
              <td class="actions">
                <button class="btn btn-sm btn-primary"
                  onclick="toggleEdit({p['id']})">Edit</button>
                <form class="inline-form" method="post"
                  action="/admin/products/{p['id']}/delete"
                  onsubmit="return confirm('Delete {p['name']}?')">
                  <button class="btn btn-sm btn-danger" type="submit">Delete</button>
                </form>
              </td>
            </tr>
            <tr class="edit-row" id="edit-{p['id']}">
              <td colspan="6">
                <form method="post" action="/admin/products/{p['id']}/edit">
                  <div class="edit-grid">
                    <div class="form-group">
                      <label>Name</label>
                      <input name="name" value="{p['name']}" required>
                    </div>
                    <div class="form-group">
                      <label>Price</label>
                      <input name="price" type="number" step="0.01" value="{p['price']}" required>
                    </div>
                    <div class="form-group" style="grid-column: span 2;">
                      <label>Image URL</label>
                      <input name="image_url" value="{p['image_url'] or ''}">
                    </div>
                    <div class="form-group" style="grid-column: span 2;">
                      <label>Description</label>
                      <input name="description" value="{p['description'] or ''}">
                    </div>
                    <div class="form-group" style="grid-column: span 2;">
                      <label>Stock JSON (e.g. {{"ONE SIZE": 10}} or {{"S": 5, "M": 8}})</label>
                      <input name="stock_json" value="{stock_input_val}" required>
                    </div>
                  </div>
                  <div class="actions">
                    <button class="btn btn-primary" type="submit">Save</button>
                    <button class="btn" type="button"
                      onclick="toggleEdit({p['id']})"
                      style="background:#eee;">Cancel</button>
                  </div>
                </form>
              </td>
            </tr>"""
        table = f"""<table>
          <thead><tr>
            <th>ID</th><th>Name</th><th>Price</th><th>Image URL</th><th>Stock</th><th></th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>"""
    else:
        table = '<p class="empty">No products yet.</p>'

    body = f"""
    <h1>Products</h1>
    {msg_html}
    <div class="card">
      <h2>Add Product</h2>
      <form method="post" action="/admin/products/add">
        <div class="form-row">
          <div class="form-group">
            <label>Name *</label>
            <input name="name" placeholder="R0001" required>
          </div>
          <div class="form-group">
            <label>Price *</label>
            <input name="price" type="number" step="0.01" placeholder="160" required>
          </div>
          <div class="form-group">
            <label>Description</label>
            <input name="description" placeholder="Optional">
          </div>
          <div class="form-group">
            <label>Image URL</label>
            <input name="image_url" placeholder="https://...">
          </div>
          <div class="form-group">
            <label>Stock JSON *</label>
            <input name="stock_json" placeholder='{{"ONE SIZE": 10}}' required>
          </div>
        </div>
        <button class="btn btn-primary" type="submit">Add Product</button>
      </form>
    </div>
    <div class="card">
      <h2>Catalog ({len(rows)} products)</h2>
      {table}
    </div>
    <script>
      function toggleEdit(id) {{
        const row = document.getElementById('edit-' + id);
        row.style.display = row.style.display === 'table-row' ? 'none' : 'table-row';
      }}
    </script>
    """
    return _page("Products", body, active="products")


@router.post("/products/add")
async def product_add(
    admin_session: Optional[str] = Cookie(default=None),
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    image_url: str = Form(""),
    stock_json: str = Form(...),
):
    redirect = _login_required(admin_session)
    if redirect:
        return redirect

    try:
        json.loads(stock_json)
    except json.JSONDecodeError:
        return RedirectResponse("/admin/products?msg=Invalid+stock+JSON", status_code=302)

    async with get_db() as conn:
        await conn.execute(
            "INSERT INTO products (name, description, price, image_url, stock_json) "
            "VALUES ($1, $2, $3, $4, $5)",
            name, description, price, image_url, stock_json,
        )
    return RedirectResponse(f"/admin/products?msg=Product+{name}+added", status_code=302)


@router.post("/products/{product_id}/edit")
async def product_edit(
    product_id: int,
    admin_session: Optional[str] = Cookie(default=None),
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(""),
    image_url: str = Form(""),
    stock_json: str = Form(...),
):
    redirect = _login_required(admin_session)
    if redirect:
        return redirect

    try:
        json.loads(stock_json)
    except json.JSONDecodeError:
        return RedirectResponse("/admin/products?msg=Invalid+stock+JSON", status_code=302)

    async with get_db() as conn:
        await conn.execute(
            "UPDATE products SET name=$1, description=$2, price=$3, image_url=$4, stock_json=$5 "
            "WHERE id=$6",
            name, description, price, image_url, stock_json, product_id,
        )
    return RedirectResponse(f"/admin/products?msg=Product+{name}+saved", status_code=302)


@router.post("/products/{product_id}/delete")
async def product_delete(
    product_id: int,
    admin_session: Optional[str] = Cookie(default=None),
):
    redirect = _login_required(admin_session)
    if redirect:
        return redirect

    async with get_db() as conn:
        await conn.execute("DELETE FROM products WHERE id=$1", product_id)
    return RedirectResponse("/admin/products?msg=Product+deleted", status_code=302)

#!/usr/bin/env python3
"""
Topps UK New Product Alert Bot
Monitors https://uk.topps.com for new products and sends email alerts.
Uses Shopify's products.json API endpoint.
"""

import json
import os
import smtplib
import sys
import time
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Configuration (all values can be overridden via environment variables)
# ---------------------------------------------------------------------------
TOPPS_URL = os.environ.get(
    "TOPPS_PRODUCTS_URL",
    "https://uk.topps.com/products.json?limit=50&sort_by=created-descending",
)
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "zeyangzhengzeus@gmail.com")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")          # your Gmail address
SENDER_PASSWORD = os.environ.get("SENDER_PASSWORD", "")    # Gmail App Password
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

# Path to file that stores previously-seen product handles
STATE_FILE = Path(os.environ.get("STATE_FILE", Path(__file__).parent / "known_products.json"))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_known_products() -> set:
    """Return the set of product handles seen in previous runs."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return set(data.get("handles", []))
        except (json.JSONDecodeError, KeyError):
            pass
    return set()


def save_known_products(handles: set) -> None:
    """Persist the current set of known product handles."""
    STATE_FILE.write_text(
        json.dumps({"handles": sorted(handles), "updated": datetime.now(timezone.utc).isoformat()},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_products(url: str) -> list[dict]:
    """Fetch the product listing from the Shopify JSON endpoint."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        return resp.json().get("products", [])
    except requests.RequestException as exc:
        print(f"[ERROR] Failed to fetch products: {exc}", file=sys.stderr)
        return []


def build_email_html(new_products: list[dict]) -> str:
    """Build an HTML email body for the new product alert."""
    rows = []
    for p in new_products:
        handle = p.get("handle", "")
        title = p.get("title", "Unknown Product")
        product_url = f"https://uk.topps.com/products/{handle}"

        # Price from first available variant
        variants = p.get("variants", [])
        price = variants[0].get("price", "N/A") if variants else "N/A"
        try:
            price_str = f"£{float(price):.2f}"
        except (ValueError, TypeError):
            price_str = price

        # First image
        images = p.get("images", [])
        img_src = images[0].get("src", "") if images else ""
        img_tag = (
            f'<img src="{img_src}" alt="{title}" '
            f'style="max-width:150px;max-height:150px;object-fit:contain;">'
            if img_src
            else ""
        )

        rows.append(
            f"""
            <tr>
              <td style="padding:12px;border-bottom:1px solid #eee;text-align:center;width:170px;">
                {img_tag}
              </td>
              <td style="padding:12px;border-bottom:1px solid #eee;vertical-align:top;">
                <a href="{product_url}" style="font-size:16px;font-weight:bold;color:#c00;text-decoration:none;">
                  {title}
                </a><br>
                <span style="color:#555;font-size:14px;">{price_str}</span><br>
                <a href="{product_url}" style="font-size:13px;color:#0070f3;">View on Topps UK →</a>
              </td>
            </tr>"""
        )

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    count = len(new_products)
    noun = "product" if count == 1 else "products"

    return f"""
    <html>
    <body style="font-family:Arial,sans-serif;background:#f9f9f9;margin:0;padding:0;">
      <table style="max-width:640px;margin:30px auto;background:#fff;border-radius:8px;
                    box-shadow:0 2px 8px rgba(0,0,0,.1);overflow:hidden;">
        <tr>
          <td style="background:#c00;padding:20px 24px;">
            <h1 style="color:#fff;margin:0;font-size:22px;">
              🏀 Topps UK — {count} New {noun.title()} Added
            </h1>
            <p style="color:#fdd;margin:4px 0 0;font-size:13px;">Detected at {now_str}</p>
          </td>
        </tr>
        <tr>
          <td style="padding:0 12px;">
            <table style="width:100%;border-collapse:collapse;">
              {''.join(rows)}
            </table>
          </td>
        </tr>
        <tr>
          <td style="padding:16px 24px;background:#f0f0f0;font-size:12px;color:#888;text-align:center;">
            You are receiving this alert because you subscribed to Topps UK new-product notifications.<br>
            <a href="https://uk.topps.com" style="color:#c00;">Visit uk.topps.com</a>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """


def send_email(subject: str, html_body: str) -> None:
    """Send an HTML email via Gmail SMTP."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("[ERROR] SENDER_EMAIL and SENDER_PASSWORD environment variables must be set.",
              file=sys.stderr)
        sys.exit(1)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"[INFO] Email sent to {RECIPIENT_EMAIL}")


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[INFO] Fetching products from {TOPPS_URL}")
    products = fetch_products(TOPPS_URL)
    if not products:
        print("[WARN] No products returned — skipping.")
        return

    known = load_known_products()
    current_handles = {p["handle"] for p in products if p.get("handle")}

    if not known:
        # First run: seed the state file without sending an alert
        print(f"[INFO] First run — seeding {len(current_handles)} known products. No email sent.")
        save_known_products(current_handles)
        return

    new_products = [p for p in products if p.get("handle") and p["handle"] not in known]

    if not new_products:
        print("[INFO] No new products found.")
        # Still update the state so that products added outside the last page are tracked
        save_known_products(known | current_handles)
        return

    print(f"[INFO] Found {len(new_products)} new product(s): "
          f"{', '.join(p['title'] for p in new_products)}")

    subject = (
        f"[Topps UK] {len(new_products)} new 球星卡 product"
        f"{'s' if len(new_products) > 1 else ''} just listed!"
    )
    html = build_email_html(new_products)
    send_email(subject, html)

    # Persist updated state
    save_known_products(known | current_handles)


if __name__ == "__main__":
    main()

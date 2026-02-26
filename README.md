# Topps UK New Product Alert Bot

Monitors [uk.topps.com](https://uk.topps.com) for new 球星卡 (sports card) listings and sends an email alert to the configured recipient.

## How it works

1. A GitHub Actions workflow runs **every hour**.
2. It calls the Shopify `products.json` API on uk.topps.com and compares against previously seen products stored in `bot/known_products.json`.
3. When new products are detected, an HTML email is sent via Gmail SMTP.
4. The updated product state is committed back to the repository automatically.

## Setup

### 1. Add GitHub Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|---|---|
| `SENDER_EMAIL` | Gmail address used to send alerts |
| `SENDER_PASSWORD` | [Gmail App Password](https://myaccount.google.com/apppasswords) (not your regular password) |

### 2. Trigger manually (optional)

Go to **Actions → Topps UK New Product Alert → Run workflow** to test immediately without waiting for the hourly schedule.

## Files

```
bot/
  topps_alert.py      # Main scraper + email sender
  requirements.txt    # Python dependency (requests)
  .env.example        # Template for local testing

.github/workflows/
  topps-alert.yml     # GitHub Actions scheduled workflow
```

## Local testing

```bash
cp bot/.env.example bot/.env
# Fill in SENDER_EMAIL and SENDER_PASSWORD in bot/.env

pip install -r bot/requirements.txt
export $(cat bot/.env | xargs)
python bot/topps_alert.py
```

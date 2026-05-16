# Telegram Subscription Access Bot

A lightweight, production‑ready system that lets you sell access to a private Telegram group/channel using external payment methods (M‑Pesa, Skrill, Neteller, Revolut, USDT). It includes an admin web dashboard and enforces **single‑use invite links** so only one user per payment can join.

## Features

- `/start` onboarding with payment method selection
- Users upload payment proof (screenshot / TXID)
- Admin reviews and approves/rejects via dark web dashboard
- **Single‑use invite links** (member_limit=1) – no sharing possible
- Automatic removal of expired subscribers (kicked from group)
- Subscription renewal, extension, and ban/unban
- Background expiry checker (every hour)

## Tech Stack

- Python 3.9+
- Flask (admin dashboard)
- python-telegram-bot v20 (bot)
- SQLite (database)
- HTML + CSS (dark premium dashboard)

## Setup & Deployment

### 1. Clone or download the folder

```bash
git clone <your-repo> tg-subscription-bot
cd tg-subscription-bot
```

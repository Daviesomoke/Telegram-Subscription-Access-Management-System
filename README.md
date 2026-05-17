# Telegram Subscription Access Bot

A lightweight, production-ready system that lets you sell access to private Telegram groups/channels using external payment methods (M-Pesa, Skrill, Neteller, Revolut, USDT). It includes an admin web dashboard and enforces single-use invite links so only one user per payment can join.

## Features

- /start onboarding with group selection and duration choice
- Users upload payment proof (screenshot / TXID)
- Admin reviews and approves/rejects via dark web dashboard
- Single-use invite links (member_limit=1) - no sharing possible
- Automatic removal of expired subscribers (kicked from group)
- Subscription renewal, extension, and ban/unban
- Background expiry checker (every hour)
- Multi-group support
- Multiple subscription durations: 1, 3, 6, 12 months

## Tech Stack

- Python 3.9+
- Flask (admin dashboard)
- python-telegram-bot v20 (bot)
- SQLite (database)
- HTML + CSS (dark premium dashboard)

## Production Deployment - Step by Step

### Step 1: Get a VPS or Server

Get a Linux VPS (Ubuntu 22.04 recommended) from any provider:

- DigitalOcean
- Hetzner
- Linode
- AWS EC2
- Any VPS with at least 1GB RAM

### Step 2: Connect to your server

```bash
ssh root@your-server-ip
```

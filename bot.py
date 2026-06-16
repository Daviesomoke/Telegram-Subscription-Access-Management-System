







import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from models import SessionLocal, User, Group
from config import (
    BOT_TOKEN,
    ADMIN_CHAT_ID,
    DURATION_MULTIPLIERS,
    M_PESA_PHONE,
    M_PESA_NAME,
    SKRILL_EMAIL,
    NETELLER_EMAIL,
    USDT_TRC20_ADDRESS,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SELECT_CHANNEL, SELECT_DURATION, SELECT_PAYMENT, UPLOAD_PROOF = range(4)


def get_payment_text(method, price):
    if method == "mpesa":
        return (
            f"M-Pesa\n"
            f"Send ${price} USD to:\n"
            f"Phone: {M_PESA_PHONE}\n"
            f"Name: {M_PESA_NAME}\n\n"
            f"After payment, upload a SCREENSHOT of the confirmation message."
        )
    elif method == "skrill":
        return (
            f"Skrill\n"
            f"Send ${price} USD to:\n"
            f"Email: {SKRILL_EMAIL}\n\n"
            f"After payment, upload a SCREENSHOT of the confirmation."
        )
    elif method == "neteller":
        return (
            f"Neteller\n"
            f"Send ${price} USD to:\n"
            f"Email: {NETELLER_EMAIL}\n\n"
            f"After payment, upload a SCREENSHOT of the payment confirmation."
        )
    elif method == "usdt":
        return (
            f"USDT (TRC20)\n"
            f"Send {price} USDT to:\n"
            f"{USDT_TRC20_ADDRESS}\n\n"
            f"After payment, upload a SCREENSHOT of the transaction."
        )
    else:
        return "Invalid payment method selected."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    db = SessionLocal()
    try:
        channels = db.query(Group).all()
        if not channels:
            await update.message.reply_text("No channels available at the moment.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(c.name, callback_data=f"channel_{c.id}")] for c in channels
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👋 Welcome! Select the channel you want to subscribe to:",
            reply_markup=reply_markup,
        )
    finally:
        db.close()
    return SELECT_CHANNEL


async def channel_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    channel_id = int(query.data.split("_")[1])
    context.user_data["channel_id"] = channel_id

    db = SessionLocal()
    try:
        channel = db.query(Group).get(channel_id)
        if not channel:
            await query.edit_message_text("Channel not found. Please use /start again.")
            return ConversationHandler.END

        # Check if user already has an active subscription to THIS channel
        user_id = update.effective_user.id
        existing = db.query(User).filter_by(telegram_id=user_id).first()
        now = datetime.utcnow()

        if (existing and existing.group_id == channel_id
                and existing.payment_status == "approved"
                and existing.expiry_date and existing.expiry_date > now
                and not existing.banned):

            days_left = (existing.expiry_date - now).days
            # Block re-subscribing unless within 7 days of expiry (early renewal window)
            if days_left > 7:
                await query.edit_message_text(
                    f"✅ You already have an active subscription to {channel.name}.\n"
                    f"It expires on {existing.expiry_date.strftime('%Y-%m-%d')} "
                    f"({days_left} days left).\n\n"
                    f"You can renew starting 7 days before expiry. "
                    f"Use /start again closer to your renewal date."
                )
                return ConversationHandler.END
            else:
                await query.edit_message_text(
                    f"🔄 Renewing your subscription to {channel.name}.\n"
                    f"Current expiry: {existing.expiry_date.strftime('%Y-%m-%d')} "
                    f"({days_left} days left).\n"
                    f"Your new subscription will extend from your current expiry date.\n\n"
                    f"Select subscription duration:"
                )

        keyboard = []
        for months_str, multiplier in DURATION_MULTIPLIERS.items():
            months = int(months_str)
            price = round(channel.monthly_price * multiplier, 2)
            button_text = f"{months} month(s) - ${price}"
            callback_data = f"dur_{months}_{price}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            f"Channel: {channel.name}\nSelect subscription duration:",
            reply_markup=reply_markup,
        )
    finally:
        db.close()
    return SELECT_DURATION


async def duration_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, months, price = query.data.split("_")
    months = int(months)
    price = float(price)
    days = months * 30 if months < 12 else 365
    context.user_data["duration_days"] = days
    context.user_data["price"] = price
    context.user_data["months"] = months

    keyboard = [
        [InlineKeyboardButton("M-Pesa", callback_data="pay_mpesa")],
        [InlineKeyboardButton("Skrill", callback_data="pay_skrill")],
        [InlineKeyboardButton("Neteller", callback_data="pay_neteller")],
        [InlineKeyboardButton("USDT TRC20", callback_data="pay_usdt")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Duration: {months} month(s)\nPrice: ${price}\n\nChoose your payment method:",
        reply_markup=reply_markup,
    )
    return SELECT_PAYMENT


async def payment_method_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_", "")
    context.user_data["payment_method"] = method

    price = context.user_data.get("price", 0)
    instruction = get_payment_text(method, price)
    await query.edit_message_text(
        f"{instruction}\n\n"
        f"⚠️ IMPORTANT: You MUST send a SCREENSHOT image of your payment confirmation.\n"
        f"Text-only references will not be accepted."
    )
    return UPLOAD_PROOF


async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    method = context.user_data.get("payment_method")

    if not method:
        await update.message.reply_text(
            "⚠️ Session expired. Please use /start to begin again."
        )
        return ConversationHandler.END

    is_photo = bool(update.message.photo)

    # REQUIRE a screenshot - reject text-only submissions
    if not is_photo:
        await update.message.reply_text(
            "❌ A screenshot is required as payment proof.\n\n"
            "Please send a SCREENSHOT IMAGE of your payment confirmation "
            "(not just text). Tap the 📎 attachment icon and select your screenshot."
        )
        return UPLOAD_PROOF  # stay in this state, wait for a real photo

    ref = f"Photo: {update.message.photo[-1].file_id}"

    db = SessionLocal()
    try:
        db_user = db.query(User).get(user.id)
        if not db_user:
            db_user = User(telegram_id=user.id, username=user.username)
            db.add(db_user)

        db_user.group_id = context.user_data.get("channel_id")
        db_user.payment_status = "pending"
        db_user.payment_method = method
        db_user.transaction_ref = ref
        db_user.updated_at = datetime.utcnow()
        # Store the requested duration for admin reference / approval
        db_user.pending_days = context.user_data.get("duration_days", 30)
        db.commit()

        channel_name = "N/A"
        if db_user.group_id:
            ch = db.query(Group).get(db_user.group_id)
            if ch:
                channel_name = ch.name

        if ADMIN_CHAT_ID:
            caption = (
                f"🔔 New Payment Pending\n"
                f"User: @{user.username or 'N/A'} (ID: {user.id})\n"
                f"Channel: {channel_name}\n"
                f"Duration: {context.user_data.get('months')} month(s)\n"
                f"Price: ${context.user_data.get('price')}\n"
                f"Method: {method}"
            )
            await context.bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=update.message.photo[-1].file_id,
                caption=caption
            )

    finally:
        db.close()

    await update.message.reply_text(
        "✅ Payment proof received. An admin will review it shortly.\n"
        "You will receive an invite link once approved."
    )
    return ConversationHandler.END


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Use /start to subscribe or /cancel to cancel."
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Operation cancelled. Use /start to try again.")
    return ConversationHandler.END


def setup_bot() -> Application:
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30,
        pool_timeout=30,
    )
    app = Application.builder().token(BOT_TOKEN).request(request).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_CHANNEL: [
                CallbackQueryHandler(channel_chosen, pattern="^channel_"),
                CommandHandler("start", start),
            ],
            SELECT_DURATION: [
                CallbackQueryHandler(duration_chosen, pattern="^dur_"),
                CommandHandler("start", start),
            ],
            SELECT_PAYMENT: [
                CallbackQueryHandler(payment_method_chosen, pattern="^pay_"),
                CommandHandler("start", start),
            ],
            UPLOAD_PROOF: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_proof),
                CommandHandler("start", start),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    return app









import logging
from datetime import datetime, timedelta
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
    REVOLUT_USERNAME,
    USDT_TRC20_ADDRESS,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
SELECT_GROUP, SELECT_DURATION, SELECT_PAYMENT, UPLOAD_PROOF = range(4)

payment_instructions = {
    "mpesa": (
        "M-Pesa\n"
        "Send {price} {currency} to:\n"
        "Phone: " + M_PESA_PHONE + "\n"
        "Name: " + M_PESA_NAME + "\n\n"
        "After payment, upload a screenshot of the confirmation message."
    ),
    "skrill": (
        "Skrill\n"
        "Send {price} {currency} to:\n"
        "Email: " + SKRILL_EMAIL + "\n\n"
        "Upload a screenshot or the transaction ID after payment."
    ),
    "neteller": (
        "Neteller\n"
        "Send {price} {currency} to:\n"
        "Email: " + NETELLER_EMAIL + "\n\n"
        "Upload a screenshot of the payment confirmation."
    ),
    "revolut": (
        "Revolut\n"
        "Send {price} {currency} to:\n"
        "Username: " + REVOLUT_USERNAME + "\n\n"
        "Upload the payment proof."
    ),
    "usdt": (
        "USDT (TRC20)\n"
        "Send {price} USDT to:\n"
        + USDT_TRC20_ADDRESS + "\n\n"
        "Upload a screenshot of the transaction or paste the TXID."
    ),
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show list of available groups."""
    db = SessionLocal()
    try:
        groups = db.query(Group).all()
        if not groups:
            await update.message.reply_text("No groups available at the moment.")
            return ConversationHandler.END

        keyboard = [
            [InlineKeyboardButton(g.name, callback_data=f"group_{g.id}")] for g in groups
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Select the group you want to subscribe to:",
            reply_markup=reply_markup,
        )
    finally:
        db.close()
    return SELECT_GROUP

async def group_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User selected a group – store it and ask for duration."""
    query = update.callback_query
    await query.answer()
    group_id = int(query.data.split("_")[1])
    context.user_data["group_id"] = group_id

    db = SessionLocal()
    try:
        group = db.query(Group).get(group_id)
        if not group:
            await query.edit_message_text("Group not found. Use /start again.")
            return ConversationHandler.END

        # Build duration buttons with calculated prices
        keyboard = []
        for months_str, multiplier in DURATION_MULTIPLIERS.items():
            months = int(months_str)
            days = months * 30 if months < 12 else 365
            price = round(group.monthly_price * multiplier, 2)
            currency = "USD"
            button_text = f"{months} month(s) - ${price}"
            callback_data = f"dur_{months}_{price}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Group: {group.name}\n"
            "Select subscription duration:",
            reply_markup=reply_markup,
        )
    finally:
        db.close()
    return SELECT_DURATION

async def duration_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User selected duration – store it and show payment methods."""
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
        [InlineKeyboardButton("Revolut", callback_data="pay_revolut")],
        [InlineKeyboardButton("USDT TRC20", callback_data="pay_usdt")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        f"Duration: {months} month(s)\n"
        f"Price: ${price}\n\n"
        "Choose your payment method:",
        reply_markup=reply_markup,
    )
    return SELECT_PAYMENT

async def payment_method_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User chose payment method – show instructions and ask for proof."""
    query = update.callback_query
    await query.answer()
    method = query.data.replace("pay_", "")
    context.user_data["payment_method"] = method

    price = context.user_data.get("price", 0)
    currency = "USD"
    instruction = payment_instructions.get(method, "Invalid method").format(price=price, currency=currency)
    await query.edit_message_text(
        f"{instruction}\n\n"
        "Send a screenshot or paste the transaction reference now."
    )
    return UPLOAD_PROOF

async def receive_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sent payment proof – save to DB and notify admin."""
    user = update.effective_user
    method = context.user_data.get("payment_method", "unknown")

    if update.message.photo:
        ref = f"Photo: {update.message.photo[-1].file_id}"
    else:
        ref = update.message.text

    db = SessionLocal()
    try:
        db_user = db.query(User).get(user.id)
        if not db_user:
            db_user = User(telegram_id=user.id, username=user.username)
            db.add(db_user)

        db_user.group_id = context.user_data.get("group_id")
        db_user.payment_status = "pending"
        db_user.payment_method = method
        db_user.transaction_ref = ref
        db_user.updated_at = datetime.utcnow()
        db.commit()

        if ADMIN_CHAT_ID:
            admin_msg = (
                "New Payment Pending\n"
                f"User: @{user.username or 'N/A'} (ID: {user.id})\n"
                f"Group ID: {db_user.group_id}\n"
                f"Duration: {context.user_data.get('months')} month(s)\n"
                f"Price: ${context.user_data.get('price')}\n"
                f"Method: {method}\n"
                f"Reference: {ref[:200]}"
            )
            await context.bot.send_message(ADMIN_CHAT_ID, admin_msg)
    finally:
        db.close()

    await update.message.reply_text(
        "Payment proof received. An admin will review it shortly. "
        "You will receive an invite link after approval."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled. Use /start to try again.")
    return ConversationHandler.END

def setup_bot() -> Application:
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_GROUP: [CallbackQueryHandler(group_chosen, pattern="^group_")],
            SELECT_DURATION: [CallbackQueryHandler(duration_chosen, pattern="^dur_")],
            SELECT_PAYMENT: [CallbackQueryHandler(payment_method_chosen, pattern="^pay_")],
            UPLOAD_PROOF: [
                MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, receive_proof)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    return app
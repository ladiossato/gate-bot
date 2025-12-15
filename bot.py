"""
Gate Bot - Simplified Telegram Handler

One system prompt. Conversation history. One LLM call.
"""

import asyncio
import logging
import os
import tempfile

from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from openai import OpenAI

from config import (
    TELEGRAM_BOT_TOKEN,
    OPENAI_API_KEY,
    ELEVENLABS_API_KEY,
    DEFAULT_VOICE_ID,
    ADMIN_USER_ID
)
from engine.response import engine
from memory.state import load_state, save_state, clear_user_data
from memory.history import get_message_count
from core.security import rate_limiter

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# OpenAI client for Whisper
openai_client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or None

    # Process as first message
    result = engine.process_message(user_id, "hey", username=username)
    await update.message.reply_text(result['response'])


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command - delete all user data."""
    user_id = str(update.effective_user.id)

    success = clear_user_data(user_id)

    if success:
        await update.message.reply_text("cleared. /start to begin again")
    else:
        await update.message.reply_text("error clearing data. try again")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - show simple stats."""
    user_id = str(update.effective_user.id)

    state = load_state(user_id)
    message_count = get_message_count(user_id)
    user_data = state.get("user", {})

    name = user_data.get("name", "unknown")
    commitment = user_data.get("commitment", "none")
    deadline = user_data.get("deadline", "none")

    stats_text = f"""name: {name}
commitment: {commitment}
deadline: {deadline}
messages: {message_count}"""

    await update.message.reply_text(stats_text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    user_id = str(update.effective_user.id)

    help_text = """/start - begin
/clear - reset everything
/stats - see your info
/help - this"""

    # Add admin commands if admin
    if user_id == ADMIN_USER_ID:
        help_text += """

ADMIN:
/limit <user_id> <per_min> <per_hour> - set user limits
/limit <user_id> - view user limits
/unlimit <user_id> - remove custom limits
/users - list users with custom limits"""

    await update.message.reply_text(help_text)


async def admin_limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /limit command - admin only."""
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("not authorized")
        return

    args = context.args

    if not args:
        await update.message.reply_text("usage: /limit <user_id> [per_min] [per_hour]")
        return

    target_user = args[0]

    # View limits
    if len(args) == 1:
        per_min, per_hr = rate_limiter.get_user_limits(target_user)
        custom = target_user in rate_limiter.user_limits
        await update.message.reply_text(
            f"user: {target_user}\n"
            f"per_minute: {per_min}\n"
            f"per_hour: {per_hr}\n"
            f"custom: {'yes' if custom else 'no (default)'}"
        )
        return

    # Set limits
    try:
        per_min = int(args[1]) if len(args) > 1 else None
        per_hr = int(args[2]) if len(args) > 2 else None

        rate_limiter.set_user_limit(target_user, per_minute=per_min, per_hour=per_hr)

        await update.message.reply_text(
            f"set limits for {target_user}:\n"
            f"per_minute: {per_min if per_min else 'unchanged'}\n"
            f"per_hour: {per_hr if per_hr else 'unchanged'}"
        )
    except ValueError:
        await update.message.reply_text("invalid numbers. usage: /limit <user_id> <per_min> <per_hour>")


async def admin_unlimit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unlimit command - admin only."""
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("not authorized")
        return

    if not context.args:
        await update.message.reply_text("usage: /unlimit <user_id>")
        return

    target_user = context.args[0]
    rate_limiter.remove_user_limit(target_user)
    await update.message.reply_text(f"removed custom limits for {target_user} (now using defaults)")


async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users command - admin only."""
    user_id = str(update.effective_user.id)

    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("not authorized")
        return

    if not rate_limiter.user_limits:
        await update.message.reply_text("no users with custom limits")
        return

    lines = ["users with custom limits:"]
    for uid, limits in rate_limiter.user_limits.items():
        per_min = limits.get("per_minute", "default")
        per_hr = limits.get("per_hour", "default")
        lines.append(f"  {uid}: {per_min}/min, {per_hr}/hr")

    await update.message.reply_text("\n".join(lines))


async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages."""
    user_id = str(update.effective_user.id)
    message = update.message.text
    username = update.effective_user.username or None

    # Process through engine
    result = engine.process_message(user_id, message, username=username)
    await update.message.reply_text(result['response'])


async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle voice messages - transcribe and process."""
    user_id = str(update.effective_user.id)
    username = update.effective_user.username or None

    if not openai_client:
        await update.message.reply_text("voice not configured")
        return

    try:
        # Download voice file
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
            await file.download_to_drive(tmp.name)
            tmp_path = tmp.name

        # Transcribe with Whisper
        with open(tmp_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )

        # Clean up temp file
        os.unlink(tmp_path)

        transcription = transcript.text

        # Process through engine
        result = engine.process_message(user_id, transcription, username=username)
        await update.message.reply_text(result['response'])

    except Exception as e:
        logger.error(f"Voice message error: {e}")
        await update.message.reply_text("couldn't process voice. try text")


async def post_init(application: Application):
    """Set up bot commands after initialization."""
    commands = [
        BotCommand("start", "begin"),
        BotCommand("clear", "reset everything"),
        BotCommand("stats", "see your info"),
        BotCommand("help", "show help"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return

    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("help", help_command))

    # Admin commands
    application.add_handler(CommandHandler("limit", admin_limit_command))
    application.add_handler(CommandHandler("unlimit", admin_unlimit_command))
    application.add_handler(CommandHandler("users", admin_users_command))

    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice_message))

    # Start the bot
    logger.info("Starting Gate Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

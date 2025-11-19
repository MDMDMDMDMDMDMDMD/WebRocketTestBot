import os
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import asyncio
import httpx

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

# Configuration
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
BITRIX_WEBHOOK = os.getenv('BITRIX_WEBHOOK')
MANAGER_CHAT_ID = int(os.getenv('MANAGER_CHAT_ID'))

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
bot = Bot(token=TELEGRAM_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Store lead data temporarily
leads_cache = {}


async def get_expired_leads():
    """Get leads from Bitrix24 with status 'CONVERTED' and created > 1 minute ago"""
    try:
        url = f"{BITRIX_WEBHOOK}crm.lead.list"

        params = {
            "filter[STATUS_ID]": "CONVERTED"
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

        if not data.get('result'):
            return []

        # Filter leads created more than 1 minute ago (for testing)
        expired_leads = []
        now = datetime.now(timezone.utc)
        threshold = now - timedelta(minutes=1)

        for lead in data['result']:
            try:
                date_str = lead.get('DATE_CREATE', '')
                created_time = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

                # Convert to UTC for comparison
                if created_time.tzinfo is not None:
                    created_time_utc = created_time.astimezone(timezone.utc)
                else:
                    created_time_utc = created_time.replace(tzinfo=timezone.utc)

                if created_time_utc < threshold:
                    expired_leads.append({
                        'id': lead.get('ID'),
                        'name': lead.get('NAME', 'Unknown'),
                        'phone': lead.get('PHONE', 'N/A') if lead.get('PHONE') else 'N/A'
                    })
            except Exception as e:
                logger.warning(f"Error processing lead: {e}")
                continue

        logger.info(f"Found {len(expired_leads)} expired leads")
        return expired_leads

    except Exception as e:
        logger.error(f"Error fetching leads: {e}")
        return []


def create_lead_keyboard(lead_id):
    """Create inline keyboard for lead actions"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Called", callback_data=f"called_{lead_id}"),
            InlineKeyboardButton(text="💬 Wrote", callback_data=f"wrote_{lead_id}")
        ],
        [
            InlineKeyboardButton(text="⏳ Postpone for 2 hours", callback_data=f"postpone_{lead_id}")
        ]
    ])
    return keyboard


async def send_expired_leads_message(chat_id):
    """Send list of expired leads to manager"""
    leads = await get_expired_leads()

    if not leads:
        await bot.send_message(chat_id, "✅ No expired leads. All good!")
        return

    for lead in leads:
        leads_cache[lead['id']] = lead
        message = f"🔹 *{lead['name']}*\n📞 {lead['phone']}"

        try:
            await bot.send_message(
                chat_id,
                message,
                parse_mode="Markdown",
                reply_markup=create_lead_keyboard(lead['id'])
            )
        except Exception as e:
            logger.error(f"Error sending message: {e}")


async def update_lead_comment(lead_id, comment):
    """Update lead in Bitrix24 with a comment"""
    try:
        url = f"{BITRIX_WEBHOOK}crm.lead.update"

        payload = {
            "id": lead_id,
            "fields": {
                "COMMENTS": comment
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()

        logger.info(f"Lead {lead_id} updated with comment: {comment}")
        return result.get('result', False)

    except Exception as e:
        logger.error(f"Error updating lead: {e}")
        return False


async def create_follow_up_task(lead_id, lead_name):
    """Create a task in Bitrix24 with 2-hour deadline"""
    try:
        url = f"{BITRIX_WEBHOOK}tasks.task.add"

        deadline = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')

        payload = {
            "fields": {
                "TITLE": f"Follow up: {lead_name}",
                "DESCRIPTION": f"Postponed lead: {lead_id}",
                "DEADLINE": deadline,
                "RESPONSIBLE_ID": 1
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()

        task_id = result.get('result', {}).get('task', {}).get('id') or result.get('result')
        logger.info(f"Task created: ID={task_id}")
        return task_id

    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return None


@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Handle /start command"""
    await message.answer(
        "👋 Welcome to Lead Manager Bot!\n\n"
        "Use /leads to see expired leads\n"
        "Use /help for more info"
    )


@dp.message(Command("leads"))
async def leads_command(message: types.Message):
    """Handle /leads command"""
    await send_expired_leads_message(message.chat.id)


@dp.message(Command("help"))
async def help_command(message: types.Message):
    """Handle /help command"""
    await message.answer(
        "📚 *Available Commands:*\n\n"
        "/start - Start the bot\n"
        "/leads - Get list of expired leads\n"
        "/help - Show this help\n\n"
        "Use inline buttons to manage leads"
    )


@dp.callback_query(F.data.startswith("called_"))
async def called_handler(query: types.CallbackQuery):
    """Handle 'Called' button"""
    lead_id = query.data.split("_")[1]

    success = await update_lead_comment(lead_id, "manager called")

    if success:
        await query.answer("✅ Lead updated: marked as called", show_alert=True)
        await query.message.edit_reply_markup(reply_markup=None)
    else:
        await query.answer("❌ Error updating lead", show_alert=True)


@dp.callback_query(F.data.startswith("wrote_"))
async def wrote_handler(query: types.CallbackQuery):
    """Handle 'Wrote' button"""
    lead_id = query.data.split("_")[1]

    success = await update_lead_comment(lead_id, "manager wrote")

    if success:
        await query.answer("✅ Lead updated: marked as wrote", show_alert=True)
        await query.message.edit_reply_markup(reply_markup=None)
    else:
        await query.answer("❌ Error updating lead", show_alert=True)


@dp.callback_query(F.data.startswith("postpone_"))
async def postpone_handler(query: types.CallbackQuery):
    """Handle 'Postpone' button"""
    lead_id = query.data.split("_")[1]
    lead = leads_cache.get(lead_id)

    if not lead:
        await query.answer("❌ Lead not found", show_alert=True)
        return

    task_id = await create_follow_up_task(lead_id, lead['name'])

    if task_id:
        await query.answer("✅ Task created for 2 hours from now", show_alert=True)
        await query.message.edit_reply_markup(reply_markup=None)
    else:
        await query.answer("❌ Error creating task", show_alert=True)


async def main():
    """Start the bot"""
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
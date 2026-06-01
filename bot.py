"""
Shnurshur Etsy Audit Bot
Щотижневий аудит лістингів + Claude AI аналіз
"""

import os
import asyncio
import logging
import requests
import json
from datetime import datetime, time
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import anthropic

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.getenv("BOT_TOKEN", "8771693161:AAG2CW2bQmT3D9ikFQ6UdyrjQIfk4AfUDWI")
CHAT_ID     = int(os.getenv("CHAT_ID", "397887704"))
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")   # вставиш на Railway
SHOP_NAME   = "Shnurshur"

# Лістинги магазину (ID + назва + поточний заголовок)
LISTINGS = [
    {
        "id": "4390149592",
        "url": "https://www.etsy.com/listing/4390149592/handmade-paracord-water-bottle-holder",
        "name": "Bottle Holder",
        "title": "Handmade Paracord Water Bottle Holder | Adjustable Crossbody Sling | Bottle Carrier for Hiking, Travel & Festivals | Gift for Him Her",
        "price": 49,
        "category": "bottle_holder"
    },
    {
        "id": "1885983765",
        "url": "https://www.etsy.com/listing/1885983765/handmade-paracord-phone-strap-crossbody",
        "name": "Phone Strap (жіночий)",
        "title": "Handmade Paracord Phone Strap | Adjustable Crossbody Phone Lanyard | iPhone Case Strap | Wrist Lanyard | Gift for Her | Phone Charm Strap",
        "price": 60,
        "category": "phone_strap"
    },
    {
        "id": "4442607331",
        "url": "https://www.etsy.com/listing/4442607331/handmade-paracord-phone-strap-crossbody",
        "name": "Phone Strap (чоловічий EDC)",
        "title": "Paracord Phone Strap for Men | Minimalist EDC Crossbody Lanyard | Handmade Wrist Phone Sling | Adjustable Everyday Carry | Gift for Him",
        "price": 60,
        "category": "phone_strap_men"
    },
    {
        "id": "4300454406",
        "url": "https://www.etsy.com/listing/4300454406/personalized-paracord-phone-strap",
        "name": "Phone Strap (персоналізований)",
        "title": "Custom Paracord Phone Strap | Personalized Colors | 3 Sizes: Wrist, Shoulder, Crossbody | Handmade Phone Lanyard | Birthday Gift for Her",
        "price": 40,
        "category": "phone_strap_gift"
    },
]

# Сезонні ключові слова — по місяцях коли НЕАКТУАЛЬНІ
SEASONAL_KEYWORDS = {
    "mothers day": [6, 7, 8, 9, 10, 11, 12, 1, 2, 3, 4],   # актуально тільки в травні
    "fathers day": [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12],   # актуально в червні
    "christmas": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
    "valentines": [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 1],
    "halloween": [1, 2, 3, 4, 5, 6, 7, 8, 11, 12],
    "easter": [5, 6, 7, 8, 9, 10, 11, 12, 1, 2],
    "back to school": [1, 2, 3, 4, 5, 6, 10, 11, 12],
    "graduation": [1, 2, 3, 7, 8, 9, 10, 11, 12],
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─── AUDIT LOGIC ──────────────────────────────────────────────────────────────

def check_seasonal_keywords(title: str, month: int) -> list[str]:
    """Знаходить протерміновані сезонні слова в заголовку"""
    found = []
    title_lower = title.lower()
    for keyword, bad_months in SEASONAL_KEYWORDS.items():
        if keyword in title_lower and month in bad_months:
            found.append(keyword)
    return found

def check_title_length(title: str) -> dict:
    length = len(title)
    return {
        "length": length,
        "ok": length <= 140,
        "note": f"{length}/140 символів" + (" ⚠️ ПЕРЕВИЩЕНО" if length > 140 else " ✅")
    }

def check_required_tags_present(title: str) -> list[str]:
    """Перевіряє чи є ключові трендові слова в заголовку"""
    trending = ["phonecharms", "phone lanyard", "phone strap", "bottle holder",
                "crossbody", "handmade", "paracord", "adjustable", "gift for her",
                "gift for him", "personalized", "EDC", "wrist"]
    missing = []
    title_lower = title.lower()
    # Категорійна перевірка
    if "phone" in title_lower:
        must_have = ["phonecharms", "lanyard", "crossbody"]
        for kw in must_have:
            if kw not in title_lower:
                missing.append(kw)
    return missing

def build_audit_report(listings: list, month: int) -> str:
    """Формує текстовий звіт для Telegram"""
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    report = f"🪢 *Shnurshur — Щотижневий аудит*\n_{now}_\n\n"

    issues_total = 0
    needs_erank = []

    for listing in listings:
        title = listing["title"]
        name = listing["name"]
        issues = []
        ok_points = []

        # 1. Сезонні слова
        seasonal = check_seasonal_keywords(title, month)
        if seasonal:
            issues.append(f"❌ Сезонні слова: *{', '.join(seasonal)}* — видали з заголовку")
        else:
            ok_points.append("✅ Без сезонних слів")

        # 2. Довжина заголовку
        tlen = check_title_length(title)
        if tlen["ok"]:
            ok_points.append(f"✅ Заголовок {tlen['note']}")
        else:
            issues.append(f"❌ Заголовок {tlen['note']}")

        # 3. Ключові слова
        missing_kw = check_required_tags_present(title)
        if missing_kw:
            issues.append(f"⚠️ Можливо варто додати в теги: `{', '.join(missing_kw[:3])}`")

        # 4. Ціна — просто нагадування
        ok_points.append(f"💰 Ціна: ${listing['price']}")

        # Формуємо блок
        status_icon = "🔴" if issues else "🟢"
        report += f"{status_icon} *{name}*\n"

        if issues:
            for issue in issues:
                report += f"  {issue}\n"
            issues_total += len(issues)
        else:
            report += f"  Все ок!\n"

        report += f"  🔗 [Відкрити лістинг]({listing['url']})\n\n"

    # Підсумок
    if issues_total == 0:
        report += "✨ *Всі лістинги в порядку!* Так тримати.\n\n"
    else:
        report += f"⚡ *Знайдено проблем: {issues_total}*\n\n"

    # Нагадування про eRank
    current_month_name = datetime.now().strftime("%B")
    report += f"📊 *Що перевірити цього тижня:*\n"
    report += f"• Оновити трендові ключі в eRank за {current_month_name}\n"
    report += f"• Перевірити конверсію в Etsy Stats\n"
    report += f"• Додати 1–2 нові лістинги (ціль: 20 активних)\n\n"
    report += f"_Надішли /audit щоб запустити перевірку вручну_"

    return report


async def run_audit_and_send(bot: Bot):
    """Запускає аудит і надсилає результат"""
    month = datetime.now().month
    logger.info(f"Running audit for month {month}")

    try:
        report = build_audit_report(LISTINGS, month)
        await bot.send_message(
            chat_id=CHAT_ID,
            text=report,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        logger.info("Audit sent successfully")
    except Exception as e:
        logger.error(f"Audit error: {e}")
        await bot.send_message(chat_id=CHAT_ID, text=f"⚠️ Помилка аудиту: {e}")


# ─── COMMANDS ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт, Діано!\n\n"
        "Я твій Etsy аудитор для магазину *Shnurshur*.\n\n"
        "📋 *Команди:*\n"
        "/audit — запустити аудит зараз\n"
        "/listings — список лістингів\n"
        "/help — довідка\n\n"
        "Автоматичний аудит — щонеділі о 10:00 🗓",
        parse_mode="Markdown"
    )

async def cmd_audit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Запускаю аудит...")
    await run_audit_and_send(ctx.bot)

async def cmd_listings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = "📋 *Активні лістинги Shnurshur:*\n\n"
    for i, l in enumerate(LISTINGS, 1):
        msg += f"{i}. [{l['name']}]({l['url']}) — ${l['price']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Що робить цей бот:*\n\n"
        "🔍 Щонеділі о 10:00 перевіряє лістинги на:\n"
        "• Сезонні слова що протерміновані\n"
        "• Довжину заголовку (макс 140 символів)\n"
        "• Відсутні трендові ключові слова\n\n"
        "📊 Нагадує що перевірити в eRank та Etsy Stats\n\n"
        "*/audit* — ручний запуск\n"
        "*/listings* — список лістингів",
        parse_mode="Markdown"
    )


# ─── SCHEDULER ────────────────────────────────────────────────────────────────

async def weekly_job(ctx: ContextTypes.DEFAULT_TYPE):
    await run_audit_and_send(ctx.bot)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("audit", cmd_audit))
    app.add_handler(CommandHandler("listings", cmd_listings))
    app.add_handler(CommandHandler("help", cmd_help))

    # Weekly job — щонеділі о 10:00
    app.job_queue.run_daily(
        weekly_job,
        time=time(hour=10, minute=0),
        days=(6,),   # 6 = Sunday
        name="weekly_audit"
    )

    logger.info("Bot started. Weekly audit: Sunday 10:00")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

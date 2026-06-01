"""
Shnurshur Etsy Audit Bot v2
- Щотижня сканує топ Etsy за ключовими словами
- Аналізує конкурентів через Claude AI
- Пропонує конкретні зміни для кожного лістингу
- Підсвічує сезонні тренди для всіх продуктів
- Приймає eRank скріни/CSV від користувача
"""

import os
import asyncio
import logging
import requests
from datetime import datetime, time as dtime
from bs4 import BeautifulSoup
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import anthropic

# ─── CONFIG ───────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.getenv("BOT_TOKEN", "8771693161:AAG2CW2bQmT3D9ikFQ6UdyrjQIfk4AfUDWI")
CHAT_ID       = int(os.getenv("CHAT_ID", "397887704"))
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── LISTINGS ─────────────────────────────────────────────────────────────────
LISTINGS = [
    {
        "id": "4390149592",
        "url": "https://www.etsy.com/listing/4390149592",
        "name": "Bottle Holder",
        "title": "Handmade Paracord Water Bottle Holder | Adjustable Crossbody Sling | Bottle Carrier for Hiking, Travel & Festivals | Gift for Him Her",
        "tags": ["water bottle holder","bottle sling","paracord bottle","crossbody bottle bag","hiking bottle holder","handmade bottle strap","hydro flask carrier","adjustable bottle strap","outdoor gear gift","gift for hiker","festival bottle holder","travel water carrier","hands free bottle"],
        "price": 49,
        "search_keywords": ["paracord water bottle holder", "bottle sling crossbody", "water bottle carrier handmade"]
    },
    {
        "id": "1885983765",
        "url": "https://www.etsy.com/listing/1885983765",
        "name": "Phone Strap (жіночий)",
        "title": "Handmade Paracord Phone Strap | Adjustable Crossbody Phone Lanyard | iPhone Case Strap | Wrist Lanyard | Gift for Her | Phone Charm Strap",
        "tags": ["phonecharms","phone lanyard","iPhone strap","crossbody phone strap","paracord phone strap","wrist phone lanyard","aesthetic phone strap","handmade phone cord","adjustable phone strap","phone charm strap","gift for her","festival phone holder","phone sling crossbody"],
        "price": 60,
        "search_keywords": ["phone strap aesthetic", "phonecharms etsy", "crossbody phone lanyard"]
    },
    {
        "id": "4442607331",
        "url": "https://www.etsy.com/listing/4442607331",
        "name": "Phone Strap (EDC чоловічий)",
        "title": "Paracord Phone Strap for Men | Minimalist EDC Crossbody Lanyard | Handmade Wrist Phone Sling | Adjustable Everyday Carry | Gift for Him",
        "tags": ["phone strap for men","EDC phone lanyard","mens phone strap","paracord phone sling","minimalist phone strap","crossbody phone strap","everyday carry gift","gift for him","handmade phone cord","wrist phone lanyard","adjustable phone strap","tactical phone strap","phonecharms"],
        "price": 60,
        "search_keywords": ["EDC phone strap men", "mens phone lanyard", "paracord phone strap men"]
    },
    {
        "id": "4300454406",
        "url": "https://www.etsy.com/listing/4300454406",
        "name": "Phone Strap (персоналізований)",
        "title": "Custom Paracord Phone Strap | Personalized Colors | 3 Sizes: Wrist, Shoulder, Crossbody | Handmade Phone Lanyard | Birthday Gift for Her",
        "tags": ["personalized phone strap","custom phone lanyard","phone charm gift","custom paracord strap","birthday gift for her","phone strap custom color","handmade phone cord","adjustable phone strap","crossbody phone strap","gift for best friend","custom colors phone","phone sling personalized","phonecharms"],
        "price": 40,
        "search_keywords": ["personalized phone strap", "custom phone lanyard gift", "phone charm custom colors"]
    },
]

# Сезонні тренди по місяцях
SEASONAL_CALENDAR = {
    1:  ["new year gift", "winter accessories", "january sale"],
    2:  ["valentines day gift", "gift for her", "love gift", "galentines"],
    3:  ["mothers day gift", "spring gift", "womens day gift"],
    4:  ["easter gift", "spring accessories", "mothers day gift"],
    5:  ["mothers day gift", "graduation gift", "spring gift"],
    6:  ["fathers day gift", "summer gift", "festival season", "graduation gift"],
    7:  ["summer gift", "festival accessory", "beach bag strap", "vacation gift"],
    8:  ["back to school", "summer gift", "festival season"],
    9:  ["back to school gift", "fall accessories", "autumn gift"],
    10: ["halloween gift", "fall gift", "spooky accessories"],
    11: ["christmas gift", "holiday gift", "stocking stuffer", "thanksgiving gift"],
    12: ["christmas gift", "holiday gift", "new year gift", "stocking stuffer"],
}

# ─── ETSY SCRAPER ─────────────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def scrape_etsy_top(keyword: str, max_results: int = 5) -> list:
    """Скрапить топ лістинги Etsy за ключовим словом"""
    try:
        url = f"https://www.etsy.com/search?q={keyword.replace(' ', '+')}&sort_on=score"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            logger.warning(f"Etsy returned {resp.status_code} for '{keyword}'")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        # Шукаємо всі заголовки лістингів
        titles = soup.find_all("h3", limit=max_results * 2)
        prices = soup.find_all(attrs={"data-currency-value": True}, limit=max_results * 2)

        seen = set()
        for i, title_el in enumerate(titles):
            title = title_el.get_text(strip=True)
            if not title or len(title) < 10 or title in seen:
                continue
            seen.add(title)
            price = prices[i].get_text(strip=True) if i < len(prices) else "?"
            results.append({"title": title[:200], "price": price})
            if len(results) >= max_results:
                break

        return results

    except Exception as e:
        logger.error(f"Scrape error for '{keyword}': {e}")
        return []


# ─── CLAUDE AI ANALYSIS ───────────────────────────────────────────────────────
def analyze_with_claude(listing: dict, competitors: list, seasonal_trends: list, erank_context: str = "") -> str:
    """Аналізує лістинг і генерує конкретні рекомендації"""
    if not ANTHROPIC_KEY:
        return "⚠️ Додай ANTHROPIC_API_KEY в Railway Variables"

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    competitors_text = "\n".join([
        f"- \"{c['title']}\" | ціна: {c['price']}"
        for c in competitors[:5]
    ]) if competitors else "Немає даних з Etsy (можливо блокування)"

    seasonal_text = ", ".join(seasonal_trends) if seasonal_trends else "немає"

    prompt = f"""You are an expert Etsy SEO specialist for a Ukrainian handmade paracord shop "Shnurshur".

CURRENT LISTING: {listing['name']}
Current title: "{listing['title']}"
Current tags: {', '.join(listing['tags'])}
Price: ${listing['price']}
Search keyword used: "{listing['search_keywords'][0]}"

TOP COMPETITORS on Etsy right now:
{competitors_text}

SEASONAL TRENDS active this month: {seasonal_text}
eRank data from seller: {erank_context if erank_context else "not provided this week"}

Provide specific, actionable recommendations in Ukrainian:

🔤 НОВИЙ ЗАГОЛОВОК (max 140 символів):
[write improved title here - incorporate what competitors use + seasonal trends if relevant]

🏷 ТОП-3 ЗМІНИ В ТЕГАХ:
- замінити "[old]" → "[new]" — [short reason]
- замінити "[old]" → "[new]" — [short reason]  
- замінити "[old]" → "[new]" — [short reason]

💡 ГОЛОВНИЙ ІНСАЙТ:
[one specific thing competitors do better, or opportunity you see]

📅 СЕЗОННИЙ МОМЕНТ:
[specific action with deadline if seasonal trend applies, or "не актуально"]"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"⚠️ Помилка аналізу: {e}"


def get_universal_trends(month: int, erank_context: str = "") -> str:
    """Тренди що підходять ВСІМ продуктам"""
    if not ANTHROPIC_KEY:
        return "Додай ANTHROPIC_API_KEY для AI аналізу"

    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    seasonal = SEASONAL_CALENDAR.get(month, [])
    month_name = datetime(2024, month, 1).strftime("%B")

    prompt = f"""Etsy SEO expert. Shop "Shnurshur" sells: phone straps ($40-60), water bottle holders ($49), bag charms, bag straps.

Month: {month_name}
Active seasonal keywords: {', '.join(seasonal)}
eRank data: {erank_context if erank_context else "not provided"}

Give 3 specific universal actions for ALL listings this month. Be concrete with dates.
Format in Ukrainian as bullet points. Example style:
• До 15 червня додай "fathers day gift" в заголовки всіх лістингів
• Цього тижня перевір чи є "summer" в тегах — зараз пік сезону"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"Помилка: {e}"


# ─── MAIN AUDIT ───────────────────────────────────────────────────────────────
async def run_full_audit(bot: Bot, erank_context: str = ""):
    """Повний аудит з скрапінгом Etsy і Claude аналізом"""
    now = datetime.now()
    month = now.month

    await bot.send_message(
        chat_id=CHAT_ID,
        text=f"🔍 *Запускаю повний аудит Shnurshur*\n_{now.strftime('%d.%m.%Y %H:%M')}_\n\nСканую Etsy + AI аналіз... ⏳ ~2 хв",
        parse_mode="Markdown"
    )

    # 1. Універсальні тренди
    await asyncio.sleep(1)
    universal = get_universal_trends(month, erank_context)
    seasonal_now = SEASONAL_CALENDAR.get(month, [])
    month_name = datetime(2024, month, 1).strftime("%B")

    trends_msg = f"🌍 *ТРЕНДИ ДЛЯ ВСІХ ЛІСТИНГІВ — {month_name}*\n\n"
    if seasonal_now:
        trends_msg += f"📅 Активні сезонні слова:\n`{chr(10).join(seasonal_now)}`\n\n"
    trends_msg += f"*Що зробити всім лістингам:*\n{universal}"
    await bot.send_message(chat_id=CHAT_ID, text=trends_msg, parse_mode="Markdown")
    await asyncio.sleep(2)

    # 2. Кожен лістинг окремо
    for listing in LISTINGS:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=f"🔎 Сканую Etsy: *{listing['name']}*...",
            parse_mode="Markdown"
        )

        keyword = listing["search_keywords"][0]
        competitors = scrape_etsy_top(keyword, max_results=5)
        analysis = analyze_with_claude(listing, competitors, seasonal_now, erank_context)

        msg = f"━━━━━━━━━━━━━━━\n"
        msg += f"📦 *{listing['name']}* | ${listing['price']}\n"
        msg += f"🔗 [Відкрити лістинг]({listing['url']})\n"

        if competitors:
            msg += f"\n👀 *Топ конкурент за '{keyword}':*\n"
            msg += f"_{competitors[0]['title'][:100]}_\n"

        msg += f"\n{analysis}"

        await bot.send_message(
            chat_id=CHAT_ID,
            text=msg,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await asyncio.sleep(4)

    # 3. Підсумок
    await bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "✅ *Аудит завершено!*\n\n"
            "📋 *Наступні кроки:*\n"
            "1. Скопіюй нові заголовки в Etsy\n"
            "2. Оновити теги згідно рекомендацій\n"
            "3. Надішли /erank з новими даними\n\n"
            "_Наступний автоаудит — в неділю о 10:00_ 🗓"
        ),
        parse_mode="Markdown"
    )


# ─── COMMANDS ─────────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт, Діано! Shnurshur Audit Bot v2 🪢\n\n"
        "📋 *Команди:*\n"
        "/audit — повний аудит (Etsy скан + AI)\n"
        "/trends — тренди цього місяця\n"
        "/listings — список лістингів\n"
        "/erank — як надіслати eRank дані\n"
        "/help — довідка\n\n"
        "📸 Просто надішли скрін або текст з eRank — збережу для аудиту\n"
        "⏰ Автоаудит: щонеділі о 10:00",
        parse_mode="Markdown"
    )

async def cmd_audit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    erank = ctx.bot_data.get("erank_context", "")
    await update.message.reply_text("⏳ Запускаю аудит...")
    await run_full_audit(ctx.bot, erank)

async def cmd_trends(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    month = datetime.now().month
    month_name = datetime(2024, month, 1).strftime("%B")
    seasonal = SEASONAL_CALENDAR.get(month, [])
    erank = ctx.bot_data.get("erank_context", "")

    await update.message.reply_text(f"📅 Аналізую тренди {month_name}...")
    universal = get_universal_trends(month, erank)

    msg = f"🌍 *Тренди {month_name}:*\n\n"
    msg += f"Сезонні слова:\n`{'`, `'.join(seasonal)}`\n\n"
    msg += f"*Дії для всіх лістингів:*\n{universal}"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_listings(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = "📋 *Лістинги Shnurshur:*\n\n"
    for i, l in enumerate(LISTINGS, 1):
        msg += f"{i}. [{l['name']}]({l['url']}) — ${l['price']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_erank(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📊 *Як надіслати eRank дані:*\n\n"
        "• Просто надішли скріншот з eRank\n"
        "• Або встав текст з ключовими словами\n\n"
        "Дані зберігаються до наступного /audit",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Shnurshur Audit Bot v2*\n\n"
        "🔍 *Щотижня автоматично:*\n"
        "• Сканує топ Etsy за твоїми ключовими словами\n"
        "• Порівнює заголовки з конкурентами\n"
        "• Claude AI генерує конкретні зміни\n"
        "• Підсвічує сезонні тренди\n\n"
        "📸 *eRank:* надішли скрін або текст — врахую в аудиті\n"
        "⏰ Автозапуск: щонеділі 10:00",
        parse_mode="Markdown"
    )

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Приймає eRank дані — текст або фото"""
    if update.message.photo:
        ctx.bot_data["erank_context"] = f"eRank screenshot received {datetime.now().strftime('%d.%m.%Y')}"
        await update.message.reply_text(
            "📸 Скрін збережено!\n"
            "Буде враховано при наступному /audit\n\n"
            "Запусти /audit щоб побачити аналіз зараз 👆"
        )
        return

    text = update.message.text or ""
    if len(text) > 20:
        ctx.bot_data["erank_context"] = text[:1500]
        await update.message.reply_text(
            f"✅ eRank дані збережено!\n"
            f"Запусти /audit для повного аналізу"
        )
    else:
        await update.message.reply_text("Спробуй /help або надішли eRank дані")

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
async def weekly_job(ctx: ContextTypes.DEFAULT_TYPE):
    erank = ctx.bot_data.get("erank_context", "")
    await run_full_audit(ctx.bot, erank)

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("audit", cmd_audit))
    app.add_handler(CommandHandler("trends", cmd_trends))
    app.add_handler(CommandHandler("listings", cmd_listings))
    app.add_handler(CommandHandler("erank", cmd_erank))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO, handle_message))

    app.job_queue.run_daily(
        weekly_job,
        time=dtime(hour=10, minute=0),
        days=(6,),
        name="weekly_audit"
    )

    logger.info("Bot v2 started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

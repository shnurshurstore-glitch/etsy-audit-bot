# Shnurshur Etsy Audit Bot 🪢

Telegram-бот для щотижневого аудиту лістингів Etsy-магазину Shnurshur.

## Що робить

- **Щонеділі о 10:00** автоматично перевіряє всі лістинги
- Знаходить **сезонні слова** що протерміновали (mothers day, christmas тощо)
- Перевіряє **довжину заголовків** (макс 140 символів)
- Нагадує що перевірити в **eRank** і **Etsy Stats**
- Команда `/audit` — запуск вручну в будь-який момент

## Деплой на Railway (безкоштовно)

### Крок 1 — GitHub
1. Створи новий репозиторій на github.com (назви `etsy-audit-bot`)
2. Завантаж туди три файли: `bot.py`, `requirements.txt`, `railway.toml`

### Крок 2 — Railway
1. Зайди на [railway.app](https://railway.app) → Sign in with GitHub
2. New Project → Deploy from GitHub repo → обери `etsy-audit-bot`
3. Railway автоматично знайде `requirements.txt` і запустить бота

### Крок 3 — Environment Variables
В Railway → твій проект → Variables → додай:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | `8771693161:AAG2CW2bQmT3D9ikFQ6UdyrjQIfk4AfUDWI` |
| `CHAT_ID` | `397887704` |

### Крок 4 — Перевірка
Напиши боту `/start` — якщо відповів, все працює ✅

## Команди бота

| Команда | Дія |
|---------|-----|
| `/start` | Привітання і список команд |
| `/audit` | Запустити аудит прямо зараз |
| `/listings` | Список всіх лістингів |
| `/help` | Довідка |

## Додати новий лістинг

Відкрий `bot.py`, знайди `LISTINGS = [` і додай:

```python
{
    "id": "ETSY_LISTING_ID",
    "url": "https://www.etsy.com/listing/ID/назва",
    "name": "Назва для звіту",
    "title": "Поточний заголовок лістингу",
    "price": 49,
    "category": "bottle_holder"
},
```

Після зміни — закоміть у GitHub, Railway автоматично перезапустить бота.

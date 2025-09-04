import os
import logging
from typing import List, Tuple

import requests
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

# In-memory storage for user selected decks
user_decks: dict[int, str] = {}

ANKI_CONNECT_URL = "http://localhost:8765"


def get_deck_names() -> List[str]:
    """Fetch deck names from Anki via AnkiConnect."""
    payload = {"action": "deckNames", "version": 6}
    try:
        resp = requests.post(ANKI_CONNECT_URL, json=payload, timeout=5)
        resp.raise_for_status()
        result = resp.json().get("result", [])
        return result or []
    except Exception as e:
        logging.error("Failed to fetch deck names: %s", e)
        return []


def add_notes(notes: List[dict]) -> None:
    """Add notes to Anki via AnkiConnect."""
    payload = {
        "action": "addNotes",
        "version": 6,
        "params": {"notes": notes},
    }
    try:
        resp = requests.post(ANKI_CONNECT_URL, json=payload, timeout=5)
        resp.raise_for_status()
    except Exception as e:
        logging.error("Failed to add notes: %s", e)


def parse_recipe(text: str) -> Tuple[str, List[Tuple[str, str]]]:
    """Parse input text into dish name and list of (product, weight)."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    dish = lines[0]
    products: List[Tuple[str, str]] = []
    for line in lines[1:]:
        name, weight = line.rsplit(" ", 1)
        products.append((name, weight.replace(",", ".")))
    return dish, products


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    deck_names = get_deck_names()
    if not deck_names:
        await update.message.reply_text("Не удалось получить список колод.")
        return
    keyboard = [[name] for name in deck_names]
    await update.message.reply_text(
        "Выберите колоду:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True),
    )


def build_notes(deck_name: str, dish: str, products: List[Tuple[str, str]]) -> List[dict]:
    notes = []
    for product, weight in products:
        notes.append(
            {
                "deckName": deck_name,
                "modelName": "Basic",
                "fields": {"Front": f"{product} - ?", "Back": weight},
            }
        )
    back_lines = [f"{p} - {w}" for p, w in products]
    notes.append(
        {
            "deckName": deck_name,
            "modelName": "Basic",
            "fields": {"Front": dish, "Back": "<br>".join(back_lines)},
        }
    )
    return notes


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = update.message.text

    if chat_id not in user_decks:
        user_decks[chat_id] = text
        await update.message.reply_text(f"Колода установлена: {text}")
        return

    deck_name = user_decks[chat_id]
    dish, products = parse_recipe(text)
    notes = build_notes(deck_name, dish, products)
    add_notes(notes)
    await update.message.reply_text(
        f"Добавлено {len(notes)} карточек в колоду {deck_name}"
    )


def main() -> None:
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("Please set TELEGRAM_TOKEN environment variable")

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()

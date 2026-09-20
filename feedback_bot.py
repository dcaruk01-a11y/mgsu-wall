import asyncio
import httpx
from config import TG_FEEDBACK_BOT_TOKEN, TG_ADMIN_ID

MAIN_KB = {
    "inline_keyboard": [
        [{"text": "🔧 Техническая неполадка", "callback_data": "issue"}],
        [{"text": "💡 Предложить улучшение", "callback_data": "idea"}],
        [{"text": "❓ Свой вопрос", "callback_data": "question"}],
    ]
}

TYPE_NAMES = {
    "issue": "Техническая неполадка",
    "idea": "Предложение по улучшению",
    "question": "Свой вопрос",
}

user_states: dict[int, str] = {}


def _user_label(user: dict) -> str:
    parts = []
    if user.get("username"):
        parts.append(f"@{user['username']}")
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")]))
    if name:
        parts.append(name)
    return " · ".join(parts) if parts else "Без имени"


async def send_message(client, api, chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        await client.post(f"{api}/sendMessage", json=payload)
    except Exception as e:
        print("feedback send_message error:", e)


async def handle_update(client, api, upd):
    if "callback_query" in upd:
        cb = upd["callback_query"]
        user = cb["from"]
        data = cb.get("data", "")
        chat_id = cb["message"]["chat"]["id"]

        try:
            await client.post(f"{api}/answerCallbackQuery", json={"callback_query_id": cb["id"]})
        except Exception:
            pass

        if data in TYPE_NAMES:
            user_states[user["id"]] = data
            await send_message(
                client, api, chat_id,
                f"Вы выбрали: <b>{TYPE_NAMES[data]}</b>\n\n"
                "Опишите подробнее одним сообщением — я передам разработчику."
            )
        return

    if "message" in upd:
        msg = upd["message"]
        user = msg.get("from", {})
        chat_id = msg["chat"]["id"]
        text = msg.get("text", "").strip()

        if text == "/start":
            user_states.pop(user.get("id"), None)
            await send_message(
                client, api, chat_id,
                "👋 Спасибо, что решили помочь!\n\n"
                "Мы благодарны вам за участие в разработке качественного продукта.\n"
                "Выберите, что хотите сообщить:",
                reply_markup=MAIN_KB,
            )
            return

        if text == "/help":
            await send_message(
                client, api, chat_id,
                "Просто нажмите /start и выберите один из вариантов.",
            )
            return

        state = user_states.get(user.get("id"))
        if state:
            label = TYPE_NAMES.get(state, "Сообщение")
            admin_text = (
                f"📩 <b>Новая заявка</b>\n\n"
                f"<b>Тип:</b> {label}\n"
                f"<b>От:</b> {_user_label(user)}\n"
                f"<b>ID:</b> <code>{user.get('id')}</code>\n\n"
                f"<b>Текст:</b>\n{text}"
            )
            await send_message(client, api, TG_ADMIN_ID, admin_text)
            await send_message(
                client, api, chat_id,
                "✅ Спасибо! Мы получили ваше сообщение и свяжемся при необходимости.\n\n"
                "Если хотите оставить ещё одну заявку — /start.",
            )
            user_states.pop(user["id"], None)
        else:
            await send_message(
                client, api, chat_id,
                "Чтобы оставить заявку — нажмите /start.",
            )


async def feedback_bot_loop():
    if not TG_FEEDBACK_BOT_TOKEN:
        print("Feedback bot: токен не задан")
        return
    if not TG_ADMIN_ID:
        print("Feedback bot: TG_ADMIN_ID не задан")
        return

    api = f"https://api.telegram.org/bot{TG_FEEDBACK_BOT_TOKEN}"
    offset = 0
    print("Feedback bot started")

    async with httpx.AsyncClient(timeout=35) as client:
        try:
            r = await client.get(f"{api}/getUpdates", params={"offset": -1})
            data = r.json()
            if data.get("ok") and data["result"]:
                offset = data["result"][-1]["update_id"] + 1
        except Exception:
            pass

        while True:
            try:
                r = await client.get(
                    f"{api}/getUpdates",
                    params={"offset": offset, "timeout": 30},
                )
                data = r.json()
                if not data.get("ok"):
                    await asyncio.sleep(3)
                    continue
                for upd in data["result"]:
                    offset = upd["update_id"] + 1
                    try:
                        await handle_update(client, api, upd)
                    except Exception as e:
                        print("feedback handle_update error:", e)
            except Exception as e:
                print("feedback bot loop error:", e)
                await asyncio.sleep(5)

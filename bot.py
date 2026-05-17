#!/usr/bin/env python3
import json
import os
import random
import socket
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path


API_ROOT = "https://api.telegram.org/bot"
WELCOME_TEXT = "Что кушать изволите?"
ASK_TEXT = "А что бы тебе хотелось сегодня?"
IMAGE_DIR = Path(__file__).resolve().parent / "assets" / "dinner_images"
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, socket.timeout)


def api_call(token, method, payload=None, timeout=35):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        f"{API_ROOT}{token}/{method}",
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    result = json.loads(body)
    if not result.get("ok"):
        raise RuntimeError(result)
    return result["result"]


def multipart_api_call(token, method, fields, files, timeout=35):
    boundary = f"----DinnerBotBoundary{int(time.time() * 1000)}"
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for name, path in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            (
                f'Content-Disposition: form-data; name="{name}"; '
                f'filename="{path.name}"\r\n'
                "Content-Type: image/png\r\n\r\n"
            ).encode("utf-8")
        )
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request = urllib.request.Request(
        f"{API_ROOT}{token}/{method}",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(result)
    return result["result"]


def send_message(token, chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return api_call(
        token,
        "sendMessage",
        payload,
        timeout=10,
    )


def send_photo(token, chat_id, image_path, caption=None):
    fields = {"chat_id": chat_id}
    if caption:
        fields["caption"] = caption
    return multipart_api_call(token, "sendPhoto", fields, {"photo": image_path}, timeout=20)


def random_dinner_image():
    images = sorted(IMAGE_DIR.glob("*.png"))
    if not images:
        return None
    return random.choice(images)


def welcome_keyboard():
    return {
        "keyboard": [
            [{"text": WELCOME_TEXT}],
            [{"text": "Паста"}, {"text": "Курица"}],
            [{"text": "Суп"}, {"text": "Что-то сладкое"}],
            [{"text": "Не знаю"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
        "input_field_placeholder": ASK_TEXT,
    }


def make_recipe(wish):
    normalized = wish.lower()

    if "паст" in normalized or "макарон" in normalized or "спагет" in normalized:
        title = "Паста с сыром и помидорами"
        ingredients = "паста, помидоры, сыр, немного масла, соль"
        steps = [
            "Отварить пасту.",
            "Быстро прогреть помидоры на сковороде с маслом.",
            "Смешать пасту с помидорами и посыпать сыром.",
        ]
    elif "кур" in normalized or "мяс" in normalized:
        title = "Курица с рисом"
        ingredients = "курица, рис, морковь, немного масла, соль"
        steps = [
            "Поставить рис вариться.",
            "Нарезать курицу и обжарить с морковью.",
            "Подать курицу рядом с рисом, можно добавить соус.",
        ]
    elif "суп" in normalized or "бульон" in normalized:
        title = "Быстрый домашний суп"
        ingredients = "картошка, морковь, лапша или рис, бульон, соль"
        steps = [
            "Порезать овощи и отправить их в кипящий бульон.",
            "Добавить лапшу или рис.",
            "Варить до мягкости и дать чуть настояться.",
        ]
    elif "слад" in normalized or "десерт" in normalized or "блин" in normalized:
        title = "Творожные блинчики с ягодами"
        ingredients = "творог, яйцо, немного муки, ягоды или варенье"
        steps = [
            "Смешать творог, яйцо и муку.",
            "Пожарить маленькие блинчики.",
            "Подать с ягодами или вареньем.",
        ]
    elif "не знаю" in normalized or "незнаю" in normalized or "что-нибудь" in normalized:
        title = "Тёплый сэндвич с сыром"
        ingredients = "хлеб, сыр, помидор, яйцо или курица по желанию"
        steps = [
            "Положить сыр и помидор между двумя кусочками хлеба.",
            "Поджарить на сковороде или в тостере.",
            "Добавить яйцо или курицу, если хочется посытнее.",
        ]
    else:
        title = f"Идея по запросу: {wish}"
        ingredients = "основа на выбор: рис, паста или хлеб; плюс сыр, овощи и что-то белковое"
        steps = [
            "Выбрать основу: рис, пасту или тост.",
            "Добавить любимый ингредиент из сообщения.",
            "Сделать блюдо тёплым и простым: обжарить, запечь или смешать с сыром.",
        ]

    return (
        f"Можно приготовить: {title}.\n\n"
        f"Что нужно: {ingredients}.\n\n"
        "Как сделать:\n"
        + "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    )


def handle_message(token, message):
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()
    if chat_id is None or not text:
        return

    if text.startswith("/start"):
        send_message(token, chat_id, f"{WELCOME_TEXT}\n\n{ASK_TEXT}", welcome_keyboard())
    elif text == WELCOME_TEXT:
        send_message(token, chat_id, ASK_TEXT, welcome_keyboard())
    elif text.startswith("/help"):
        send_message(token, chat_id, "Нажми кнопку или напиши, чего хочется: пасту, суп, курицу, сладкое или что-нибудь своё.", welcome_keyboard())
    else:
        send_message(token, chat_id, make_recipe(text), welcome_keyboard())
        image_path = random_dinner_image()
        if image_path is not None:
            send_photo(token, chat_id, image_path)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN before running bot.py", file=sys.stderr)
        return 1

    while True:
        try:
            me = api_call(token, "getMe", timeout=10)
            break
        except NETWORK_ERRORS as exc:
            print(f"Waiting for Telegram API: {exc}", file=sys.stderr, flush=True)
            time.sleep(5)

    username = me.get("username") or me.get("first_name") or "bot"
    print(f"Telegram bot @{username} is running. Press Ctrl+C to stop.", flush=True)

    offset = None
    while True:
        params = {"timeout": 30}
        if offset is not None:
            params["offset"] = offset

        query = urllib.parse.urlencode(params)
        try:
            updates = api_call(token, f"getUpdates?{query}", timeout=45)
        except NETWORK_ERRORS as exc:
            print(f"Telegram connection lost: {exc}", file=sys.stderr, flush=True)
            time.sleep(5)
            continue

        for update in updates:
            offset = update["update_id"] + 1
            message = update.get("message")
            if message:
                try:
                    handle_message(token, message)
                except Exception as exc:
                    print(f"Failed to handle message: {exc}", file=sys.stderr, flush=True)

        time.sleep(0.2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nBot stopped.")

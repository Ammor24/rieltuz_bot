import os
import re
import requests
from flask import Flask, request

app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"


def send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=10
        )
    except Exception:
        pass


def get_olx_images(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=15
        )

        if response.status_code != 200:
            return []

        pattern = r'https://[a-zA-Z0-9.\-]+/v1/files/[a-zA-Z0-9\-]+/image[^\s"\'<>]*'

        images = re.findall(pattern, response.text)

        images = [
            image.split(";")[0]
            for image in images
        ]

        return list(dict.fromkeys(images))

    except Exception:
        return []


def send_media_group(chat_id, images):
    for i in range(0, len(images), 10):

        group = images[i:i + 10]

        media = [
            {
                "type": "photo",
                "media": image
            }
            for image in group
        ]

        try:
            requests.post(
                f"{TELEGRAM_API}/sendMediaGroup",
                json={
                    "chat_id": chat_id,
                    "media": media
                },
                timeout=30
            )
        except Exception:
            pass


@app.route("/", methods=["GET"])
def home():
    return "Bot ishlayapti!"


@app.route("/api/index", methods=["GET", "POST"])
def telegram_webhook():

    if request.method == "GET":
        return "OK"

    try:
        update = request.get_json(silent=True)

        if not update:
            return "OK", 200

        message = update.get("message")

        if not message:
            return "OK", 200

        chat = message.get("chat")

        if not chat:
            return "OK", 200

        chat_id = chat.get("id")
        text = message.get("text", "").strip()

        if text == "/start":

            send_message(
                chat_id,
                "Assalomu alaykum! 👋\n\n"
                "Menga OLX.uz e'lon havolasini yuboring.\n"
                "Men e'lon rasmlarini topib yuboraman."
            )

        elif "olx.uz" in text.lower():

            send_message(
                chat_id,
                "🔎 Rasmlar qidirilmoqda, biroz kuting..."
            )

            images = get_olx_images(text)

            if images:

                send_media_group(
                    chat_id,
                    images
                )

                send_message(
                    chat_id,
                    f"✅ {len(images)} ta rasm topildi."
                )

            else:

                send_message(
                    chat_id,
                    "❌ Rasmlarni topib bo'lmadi.\n\n"
                    "OLX e'lon havolasini to'g'ri yuborganingizni tekshiring."
                )

        else:

            send_message(
                chat_id,
                "Iltimos, OLX.uz e'lon havolasini yuboring."
            )

        return "OK", 200

    except Exception:

        return "OK", 200

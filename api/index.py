import os
import re
import json
import html
import requests

from flask import Flask, request
from bs4 import BeautifulSoup
from urllib.parse import urlparse


app = Flask(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TOKEN}"

MY_PHONE = "+998995710024"


# =========================================================
# TELEGRAM
# =========================================================

def send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text
            },
            timeout=15
        )
    except Exception:
        pass


# =========================================================
# URL TOZALASH
# =========================================================

def clean_url(url):
    url = html.unescape(url)
    url = url.replace("\\/", "/")
    url = url.replace("\\u002F", "/")

    url = url.split('"')[0]
    url = url.split("'")[0]
    url = url.strip()

    return url


# =========================================================
# OLX SAHIFASINI OLISH
# =========================================================

def get_page(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/140.0 Safari/537.36"
        ),
        "Accept-Language": "uz-UZ,uz;q=0.9,ru;q=0.8,en;q=0.7",
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,*/*;q=0.8"
        )
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=25
        )

        if response.status_code != 200:
            return None

        return response.text

    except Exception:
        return None


# =========================================================
# RASMLAR
# =========================================================

def get_olx_images_from_html(page_html):

    soup = BeautifulSoup(page_html, "html.parser")

    candidates = []

    # -----------------------------------------------------
    # 1. JSON-LD
    # -----------------------------------------------------

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    )

    for script in scripts:

        try:
            data = json.loads(
                script.string or script.get_text()
            )

        except Exception:
            continue

        objects = []

        if isinstance(data, list):
            objects = data

        elif isinstance(data, dict):

            objects = [data]

            graph = data.get("@graph")

            if isinstance(graph, list):
                objects.extend(graph)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            image = obj.get("image")

            if isinstance(image, str):

                candidates.append(image)

            elif isinstance(image, list):

                for item in image:

                    if isinstance(item, str):
                        candidates.append(item)

                    elif isinstance(item, dict):

                        url = item.get("url")

                        if url:
                            candidates.append(url)

    # -----------------------------------------------------
    # 2. OG IMAGE
    # -----------------------------------------------------

    for meta in soup.find_all(
        "meta",
        attrs={"property": "og:image"}
    ):

        content = meta.get("content")

        if content:
            candidates.append(content)

    # -----------------------------------------------------
    # 3. OLX CDN URL'LARI — FALLBACK
    # -----------------------------------------------------

    if len(candidates) < 2:

        pattern = r'https://[^"\']*olxcdn\.com[^"\']+'

        candidates.extend(
            re.findall(pattern, page_html)
        )

    # -----------------------------------------------------
    # URL'LARNI TOZALASH
    # -----------------------------------------------------

    cleaned = []

    for image in candidates:

        image = clean_url(image)

        if "olxcdn.com" not in image:
            continue

        if not image.startswith("http"):
            continue

        cleaned.append(image)

    # -----------------------------------------------------
    # DUBLIKATLARNI YO'QOTISH
    # -----------------------------------------------------

    result = []
    seen_keys = set()

    for image in cleaned:

        parsed = urlparse(image)

        path = parsed.path

        match = re.search(
            r"/v1/files/([^/]+)/",
            path
        )

        if match:

            file_id = match.group(1)

            key = file_id

        else:

            key = path

        if key in seen_keys:
            continue

        seen_keys.add(key)

        result.append(image)

    return result


# =========================================================
# E'LON MA'LUMOTLARI
# =========================================================

def get_listing_data(page_html):

    soup = BeautifulSoup(page_html, "html.parser")

    title = ""
    description = ""

    attributes = []

    # -----------------------------------------------------
    # JSON-LD
    # -----------------------------------------------------

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    )

    for script in scripts:

        try:
            data = json.loads(
                script.string or script.get_text()
            )

        except Exception:
            continue

        objects = []

        if isinstance(data, list):
            objects = data

        elif isinstance(data, dict):

            objects = [data]

            graph = data.get("@graph")

            if isinstance(graph, list):
                objects.extend(graph)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            if not title:

                title = obj.get(
                    "name",
                    ""
                ) or ""

            if not description:

                description = obj.get(
                    "description",
                    ""
                ) or ""

    # -----------------------------------------------------
    # TITLE FALLBACK
    # -----------------------------------------------------

    if not title:

        tag = soup.find(
            "meta",
            attrs={"property": "og:title"}
        )

        if tag:
            title = tag.get(
                "content",
                ""
            )

    if not title and soup.title:

        title = soup.title.get_text(
            " ",
            strip=True
        )

    # -----------------------------------------------------
    # DESCRIPTION FALLBACK
    # -----------------------------------------------------

    if not description:

        meta = soup.find(
            "meta",
            attrs={"property": "og:description"}
        )

        if meta:

            description = meta.get(
                "content",
                ""
            )

    # -----------------------------------------------------
    # SAHIFADAGI MATN
    # -----------------------------------------------------

    page_text = soup.get_text(
        "\n",
        strip=True
    )

    lines = []

    for line in page_text.splitlines():

        line = line.strip()

        if not line:
            continue

        if line not in lines:
            lines.append(line)

    # -----------------------------------------------------
    # MUHIM XUSUSIYATLAR
    # -----------------------------------------------------

    possible_labels = [

        "Количество комнат",
        "Общая площадь",
        "Этаж",
        "Этажность",
        "Тип строения",
        "Планировка",
        "Санузел",
        "Меблирована",
        "Ремонт",
        "Комиссионные",
        "Цена",
        "Адрес",
        "Вид объекта",
        "Тип недвижимости",
        "Состояние",
        "Год выпуска",
        "Пробег",
        "Коробка передач",
        "Тип топлива"
    ]

    for i, line in enumerate(lines):

        for label in possible_labels:

            if label.lower() in line.lower():

                value = line

                if value not in attributes:
                    attributes.append(value)

                break

    return {
        "title": title.strip(),
        "description": description.strip(),
        "attributes": attributes
    }


# =========================================================
# TELEFON RAQAMINI TOPISH
# =========================================================

def get_phone_numbers(page_html):

    patterns = [

        r"\+998[\s\-()]*\d{2}[\s\-()]*\d{3}"
        r"[\s\-]*\d{2}[\s\-]*\d{2}",

        r"998[\s\-()]*\d{2}[\s\-()]*\d{3}"
        r"[\s\-]*\d{2}[\s\-]*\d{2}"
    ]

    found = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            page_html
        )

        for phone in matches:

            digits = re.sub(
                r"\D",
                "",
                phone
            )

            if (
                digits.startswith("998")
                and len(digits) == 12
            ):

                normalized = "+" + digits

                if normalized not in found:
                    found.append(normalized)

    # Bizning raqamimizni olib tashlaymiz
    found = [
        phone
        for phone in found
        if phone != MY_PHONE
    ]

    return found


# =========================================================
# TELEGRAM MEDIA GROUP
# =========================================================

def send_media_group(
    chat_id,
    images,
    caption=None
):

    sent = 0

    for i in range(
        0,
        len(images),
        10
    ):

        group = images[i:i + 10]

        media = []

        for index, image in enumerate(group):

            item = {
                "type": "photo",
                "media": image
            }

            # Caption faqat birinchi rasmga
            if (
                i == 0
                and index == 0
                and caption
            ):

                item["caption"] = caption

            media.append(item)

        try:

            response = requests.post(
                f"{TELEGRAM_API}/sendMediaGroup",
                json={
                    "chat_id": chat_id,
                    "media": media
                },
                timeout=40
            )

            if response.ok:

                sent += len(group)

        except Exception:
            pass

    return sent


# =========================================================
# NATIJANI TAYYORLASH
# =========================================================

def make_listing_text(data):

    title = data.get(
        "title",
        ""
    )

    description = data.get(
        "description",
        ""
    )

    attributes = data.get(
        "attributes",
        []
    )

    text = ""

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    if title:

        text += f"🏠 {title}\n\n"

    # -----------------------------------------------------
    # XUSUSIYATLAR
    # -----------------------------------------------------

    if attributes:

        for item in attributes:

            if len(item) > 300:
                continue

            text += f"🔹 {item}\n"

        text += "\n"

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    if description:

        text += "📝 Описание:\n"

        text += description

        text += "\n\n"

    # -----------------------------------------------------
    # BIZNING RAQAM
    # -----------------------------------------------------

    text += "📞 Aloqa uchun:\n"

    text += MY_PHONE

    return text


# =========================================================
# E'LON EGASINING RAQAMI
# =========================================================

def make_owner_phone_text(phones):

    if not phones:

        return (
            "📱 E'lon egasining raqami topilmadi."
        )

    text = (
        "📱 E'lon egasining raqami:\n\n"
    )

    for phone in phones:

        text += phone + "\n"

    return text.strip()


# =========================================================
# ROUTES
# =========================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return "Bot ishlayapti!"


@app.route(
    "/api/index",
    methods=["GET", "POST"]
)
def telegram_webhook():

    if request.method == "GET":

        return "OK"

    try:

        update = request.get_json(
            silent=True
        )

        if not update:

            return "OK", 200

        message = update.get(
            "message"
        )

        if not message:

            return "OK", 200

        chat = message.get(
            "chat"
        )

        if not chat:

            return "OK", 200

        chat_id = chat.get(
            "id"
        )

        text = message.get(
            "text",
            ""
        ).strip()

        # =================================================
        # START
        # =================================================

        if text == "/start":

            send_message(
                chat_id,

                "Assalomu alaykum! 👋\n\n"

                "Menga OLX.uz e'lon havolasini "
                "yuboring.\n\n"

                "Men sizga:\n"

                "🖼 E'lon rasmlarini\n"

                "📝 E'lon ma'lumotlarini\n"

                "📱 E'lon egasining telefon raqamini\n"

                "📞 Aloqa raqamini\n"

                "ajratib beraman."
            )

        # =================================================
        # OLX
        # =================================================

        elif "olx.uz" in text.lower():

            send_message(
                chat_id,

                "🔎 E'lon ma'lumotlari va rasmlar "
                "qidirilmoqda...\n\n"

                "Biroz kuting."
            )

            page_html = get_page(
                text
            )

            if not page_html:

                send_message(
                    chat_id,

                    "❌ OLX e'lonini ochib bo'lmadi."
                )

                return "OK", 200

            # -------------------------------------------------
            # RASMLAR
            # -------------------------------------------------

            images = get_olx_images_from_html(
                page_html
            )

            # -------------------------------------------------
            # E'LON MA'LUMOTLARI
            # -------------------------------------------------

            data = get_listing_data(
                page_html
            )

            # -------------------------------------------------
            # TELEFONLAR
            # -------------------------------------------------

            phones = get_phone_numbers(
                page_html
            )

            # -------------------------------------------------
            # MATN
            # -------------------------------------------------

            listing_text = make_listing_text(
                data
            )

            # -------------------------------------------------
            # RASMLAR + CAPTION
            # -------------------------------------------------

            if images:

                sent_count = send_media_group(
                    chat_id,
                    images,
                    listing_text
                )

                # -------------------------------------------------
                # E'LON EGASINING RAQAMI ALOHIDA
                # -------------------------------------------------

                phone_text = make_owner_phone_text(
                    phones
                )

                send_message(
                    chat_id,
                    phone_text
                )

                # -------------------------------------------------
                # NECHTA RASM YUBORILGANINI
                # -------------------------------------------------

                send_message(
                    chat_id,

                    f"🖼 {sent_count} ta rasm yuborildi."
                )

            # -------------------------------------------------
            # RASM TOPILMASA
            # -------------------------------------------------

            else:

                send_message(
                    chat_id,
                    listing_text
                )

                phone_text = make_owner_phone_text(
                    phones
                )

                send_message(
                    chat_id,
                    phone_text
                )

                send_message(
                    chat_id,
                    "⚠️ E'londa rasmlar topilmadi."
                )

        # =================================================
        # BOSHQA XABAR
        # =================================================

        else:

            send_message(
                chat_id,

                "Iltimos, OLX.uz e'lon havolasini "
                "yuboring."
            )

        return "OK", 200

    except Exception:

        return "OK", 200

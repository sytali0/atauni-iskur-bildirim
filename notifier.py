#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Atatürk Üniversitesi İŞKUR Gençlik Programı / Kura Sonuçları Takip ve WhatsApp Bildirim Sistemi.
Bilgisayar kapalıyken GitHub Actions üzerinde ücretsiz ve 7/24 çalışacak şekilde tasarlanmıştır.
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

# 콘솔 karakter kodlamasını UTF-8 olarak ayarla
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SEEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen_items.json")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)

# Türkçe karakter duyarlı küçük harfe çevirme
def tr_lower(text: str) -> str:
    if not text:
        return ""
    return (
        text.replace("İ", "i")
        .replace("I", "ı")
        .replace("Ğ", "ğ")
        .replace("Ü", "ü")
        .replace("Ş", "ş")
        .replace("Ö", "ö")
        .replace("Ç", "ç")
        .lower()
    )


def strip_html(raw_html: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", raw_html or "")
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()


def fetch_url(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def is_iskur_kura_related(title: str, content: str = "", strict_kura: bool = False) -> bool:
    """
    Metnin İŞKUR Gençlik Programı veya Kura Sonuçları ile ilgili olup olmadığını kontrol eder.
    atauni.edu.tr üzerindeki her yeni İŞKUR duyurusu kritik olduğu için varsayılan olarak
    'işkur' veya 'gençlik programı' geçen tüm yeni üniversite duyurularını yakalar.
    Google Haberler gibi genel kaynaklarda ise strict_kura=True ile kura/sonuç kelimesi şartı aranır.
    """
    combined = tr_lower(f"{title} {content}")
    iskur_keywords = ["işkur", "iskur", "gençlik programı", "genclik programi", "iup", "işgücü uyum"]
    kura_keywords = [
        "kura",
        "sonuç",
        "sonuc",
        "asil",
        "yedek",
        "isim listesi",
        "aday listesi",
        "hak kazanan",
        "açıklandı",
        "aciklandi",
        "evrak teslim",
        "belge teslim",
    ]

    has_iskur = any(k in combined for k in iskur_keywords)
    if not has_iskur:
        return False

    if strict_kura:
        return any(k in combined for k in kura_keywords)
    return True


def check_atauni_wp_api() -> list[dict]:
    """
    1. Kaynak: Atatürk Üniversitesi Resmi WordPress REST API (Ana Sayfa & Duyurular)
    """
    results = []
    endpoints = [
        ("Ana Sayfa / Duyurular", "https://atauni.edu.tr/wp-json/wp/v2/posts?per_page=20"),
        ("SKS Daire Başkanlığı", "https://atauni.edu.tr/saglik-kultur-ve-spor-daire-baskanligi/wp-json/wp/v2/posts?per_page=10"),
        ("Öğrenci İşleri", "https://atauni.edu.tr/ogrenci-isleri-daire-baskanligi/wp-json/wp/v2/posts?per_page=10"),
    ]

    for source_name, url in endpoints:
        try:
            raw = fetch_url(url)
            posts = json.loads(raw)
            for post in posts:
                post_id = f"wp-{post.get('id')}"
                title = strip_html(post.get("title", {}).get("rendered", ""))
                raw_content = post.get("content", {}).get("rendered", "")
                content = strip_html(raw_content)
                link = post.get("link", "https://atauni.edu.tr/tum-duyurular/")
                date_str = post.get("date", "")

                if is_iskur_kura_related(title, content, strict_kura=False):
                    # Varsa duyuru içindeki PDF / Excel liste bağlantılarını da çıkar
                    doc_links = re.findall(
                        r'href=["\'](https?://[^"\']+\.(?:pdf|xlsx?|docx?))["\']',
                        raw_content,
                        re.I,
                    )
                    summary = content[:280] + ("..." if len(content) > 280 else "")
                    if doc_links:
                        unique_docs = list(dict.fromkeys(doc_links))[:3]
                        summary += "\n📎 Ek Dosyalar: " + " , ".join(unique_docs)

                    results.append(
                        {
                            "id": post_id,
                            "source": f"Atatürk Üniversitesi ({source_name})",
                            "title": title,
                            "link": link,
                            "date": date_str,
                            "summary": summary,
                        }
                    )
        except Exception as exc:
            print(f"[UYARI] {source_name} API kontrol edilirken hata oluştu: {exc}")

    return results


def check_google_news_rss() -> list[dict]:
    """
    2. Kaynak: Google Haberler RSS ("Atatürk Üniversitesi" İŞKUR kura sonuçları)
    Clickbait ("açıklandı mı?", "ne zaman?") haberlerini otomatik filtreler.
    """
    results = []
    query = urllib.parse.quote('"Atatürk Üniversitesi" İŞKUR kura')
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=tr&gl=TR&ceid=TR:tr"
    clickbait_phrases = [
        "açıklandı mı",
        "aciklandi mi",
        "belli oldu mu",
        "ne zaman",
        "nereden bakılır",
        "nasıl öğrenilir",
        "sorgulanır mı",
    ]

    try:
        xml_data = fetch_url(rss_url)
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item")[:10]:
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            guid = (item.findtext("guid") or link).strip()

            combined_lower = tr_lower(title)
            if any(cb in combined_lower for cb in clickbait_phrases):
                continue

            if "atatürk" in combined_lower or "atauni" in combined_lower:
                if is_iskur_kura_related(title, strict_kura=True):
                    results.append(
                        {
                            "id": f"gnews-{guid[:80]}",
                            "source": "Google Haberler",
                            "title": title,
                            "link": link,
                            "date": pub_date,
                            "summary": "Basında Atatürk Üniversitesi İŞKUR kura sonuçları ile ilgili yeni haber yayınlandı.",
                        }
                    )
    except Exception as exc:
        print(f"[UYARI] Google Haberler RSS kontrol edilirken hata oluştu: {exc}")

    return results


def load_seen() -> dict:
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            print(f"[UYARI] seen_items.json okunamadı: {exc}")
    return {"seen_ids": [], "last_checked": None}


def save_seen(data: dict) -> None:
    data["last_checked"] = datetime.now(timezone.utc).isoformat()
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_whatsapp_callmebot(phone: str, apikey: str, message: str) -> bool:
    """
    CallMeBot Ücretsiz WhatsApp API üzerinden mesaj gönderir.
    """
    clean_phone = re.sub(r"[^\d+]", "", phone)
    encoded_msg = urllib.parse.quote(message)
    url = f"https://api.callmebot.com/whatsapp.php?phone={clean_phone}&text={encoded_msg}&apikey={apikey}"

    try:
        resp_text = fetch_url(url, timeout=20)
        print(f"[WHATSAPP-CALLMEBOT] Yanıt: {resp_text.strip()[:200]}")
        return True
    except Exception as exc:
        print(f"[HATA] CallMeBot WhatsApp mesajı gönderilemedi: {exc}")
        return False


def send_whatsapp_greenapi(instance_id: str, api_token: str, phone: str, message: str) -> bool:
    """
    Green-API (green-api.com) Ücretsiz Developer paketi üzerinden WhatsApp mesajı gönderir.
    CallMeBot dolu olduğunda en hızlı ve ücretsiz WhatsApp alternatifidir (Kredi kartı gerekmez).
    """
    clean_digits = re.sub(r"\D", "", phone)
    if clean_digits.startswith("0"):
        clean_digits = "90" + clean_digits[1:]
    chat_id = f"{clean_digits}@c.us"

    url = f"https://api.green-api.com/waInstance{instance_id}/sendMessage/{api_token}"
    payload = json.dumps({"chatId": chat_id, "message": message}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            resp_body = resp.read().decode("utf-8", errors="ignore")
            print(f"[WHATSAPP-GREENAPI] Mesaj gönderildi! Yanıt: {resp_body[:200]}")
            return resp.status == 200
    except Exception as exc:
        print(f"[HATA] Green-API WhatsApp mesajı gönderilemedi: {exc}")
        return False


def send_whatsapp_twilio(account_sid: str, auth_token: str, from_number: str, to_phone: str, message: str) -> bool:
    """
    Twilio Ücretsiz WhatsApp Sandbox üzerinden mesaj gönderir.
    """
    import base64

    clean_to = re.sub(r"[^\d+]", "", to_phone)
    if not clean_to.startswith("+"):
        clean_to = "+" + clean_to
    clean_from = re.sub(r"[^\d+]", "", from_number or "+14155238886")
    if not clean_from.startswith("+"):
        clean_from = "+" + clean_from

    url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    data = urllib.parse.urlencode(
        {
            "From": f"whatsapp:{clean_from}",
            "To": f"whatsapp:{clean_to}",
            "Body": message,
        }
    ).encode("utf-8")
    auth_str = base64.b64encode(f"{account_sid}:{auth_token}".encode("utf-8")).decode("ascii")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Basic {auth_str}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"[WHATSAPP-TWILIO] Mesaj başarıyla gönderildi! (HTTP {resp.status})")
            return resp.status in (200, 201)
    except Exception as exc:
        print(f"[HATA] Twilio WhatsApp mesajı gönderilemedi: {exc}")
        return False


def resolve_telegram_chat_id(bot_token: str, explicit_chat_id: str = "") -> str:
    """
    TELEGRAM_CHAT_ID tanımlı değilse seen_items.json'dan veya botun getUpdates
    API'sinden bota mesaj atan kullanıcının chat_id bilgisini otomatik bulur ve kaydeder.
    """
    if explicit_chat_id:
        return explicit_chat_id

    seen_data = load_seen()
    saved_chat_id = str(seen_data.get("telegram_chat_id", "")).strip()
    if saved_chat_id:
        return saved_chat_id

    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    try:
        raw = fetch_url(url, timeout=15)
        data = json.loads(raw)
        for upd in reversed(data.get("result", [])):
            msg_obj = upd.get("message") or upd.get("my_chat_member") or {}
            chat = msg_obj.get("chat") or {}
            cid = chat.get("id")
            if cid:
                cid_str = str(cid)
                print(f"[TELEGRAM] Chat ID otomatik tespit edildi: {cid_str}")
                seen_data["telegram_chat_id"] = cid_str
                save_seen(seen_data)
                return cid_str
    except Exception as exc:
        print(f"[UYARI] Telegram getUpdates ile Chat ID alınamadı: {exc}")

    return ""


def send_telegram(bot_token: str, chat_id: str, message: str) -> bool:
    """
    Telegram Bot API üzerinden bildirim gönderir.
    """
    resolved_chat_id = resolve_telegram_chat_id(bot_token, chat_id)
    if not resolved_chat_id:
        print(
            "[UYARI] Telegram Chat ID henüz bulunamadı! "
            "Lütfen Telegram'da @canonews_bot adresine girip 'Başlat' (Start) butonuna basın veya bir mesaj gönderin."
        )
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode(
        {"chat_id": resolved_chat_id, "text": message, "disable_web_page_preview": "false"}
    ).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=payload, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"[TELEGRAM] Mesaj başarıyla gönderildi! (Chat ID: {resolved_chat_id})")
            return resp.status == 200
    except Exception as exc:
        print(f"[HATA] Telegram mesajı gönderilemedi: {exc}")
        return False


def notify_user(item: dict, is_test: bool = False) -> bool:
    prefix = "🧪 [TEST BİLDİRİMİ]\n" if is_test else "🚨 *ATATÜRK ÜNİVERSİTESİ İŞKUR DUYURUSU!* 🚨\n\n"
    msg = (
        f"{prefix}"
        f"📌 *Başlık:* {item['title']}\n"
        f"🏛️ *Kaynak:* {item['source']}\n"
        f"🕒 *Tarih:* {item.get('date', 'Yeni')}\n\n"
        f"📝 *Özet:* {item.get('summary', '')}\n\n"
        f"🔗 *Bağlantı:* {item['link']}"
    )

    phone = os.environ.get("WHATSAPP_PHONE", "").strip()
    apikey = os.environ.get("CALLMEBOT_APIKEY", "").strip()
    green_id = os.environ.get("GREENAPI_INSTANCE_ID", "").strip()
    green_token = os.environ.get("GREENAPI_API_TOKEN", "").strip()
    twilio_sid = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    twilio_token = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    twilio_from = os.environ.get("TWILIO_WHATSAPP_FROM", "+14155238886").strip()
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    sent_any = False

    # 1. Green-API ile WhatsApp (Ücretsiz, Kota Sınırı Yok)
    if green_id and green_token and phone:
        print(f"[BİLGİ] Green-API üzerinden WhatsApp ({phone}) mesajı gönderiliyor...")
        if send_whatsapp_greenapi(green_id, green_token, phone, msg):
            sent_any = True

    # 2. Twilio Sandbox ile WhatsApp
    if twilio_sid and twilio_token and phone:
        print(f"[BİLGİ] Twilio üzerinden WhatsApp ({phone}) mesajı gönderiliyor...")
        if send_whatsapp_twilio(twilio_sid, twilio_token, twilio_from, phone, msg):
            sent_any = True

    # 3. CallMeBot ile WhatsApp
    if phone and apikey:
        print(f"[BİLGİ] CallMeBot üzerinden WhatsApp ({phone}) mesajı gönderiliyor...")
        if send_whatsapp_callmebot(phone, apikey, msg):
            sent_any = True

    # 4. Telegram Bot (Chat ID yoksa getUpdates üzerinden otomatik bulur)
    if tg_token:
        print("[BİLGİ] Telegram üzerinden bildirim gönderiliyor...")
        if send_telegram(tg_token, tg_chat, msg):
            sent_any = True

    if not sent_any:
        print("[UYARI] Henüz aktif bir bildirim anahtarı veya Chat ID tanımlanmamış!")
        print("\n--- GÖNDERİLECEK MESAJ ÖNİZLEMESİ ---")
        print(msg)
        print("-------------------------------------\n")

    return sent_any


def main() -> int:
    parser = argparse.ArgumentParser(description="Atatürk Üniversitesi İŞKUR Kura Sonuçları Takipçisi")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Bildirim bağlantısını doğrulamak için hemen bir test mesajı gönderir.",
    )
    args = parser.parse_args()

    if args.test:
        test_item = {
            "id": "test-001",
            "source": "Atatürk Üniversitesi Bildirim Sistemi (Test)",
            "title": "Bildirim Sisteminiz Başarıyla Çalışıyor!",
            "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
            "summary": "Atatürk Üniversitesi İŞKUR Gençlik Programı kura sonuçları açıklandığı anda bu sohbet üzerinden anında bildirim alacaksınız.",
            "link": "https://atauni.edu.tr/tum-duyurular/",
        }
        notify_user(test_item, is_test=True)
        return 0

    seen_data = load_seen()
    seen_ids = set(seen_data.get("seen_ids", []))

    # İlk kez Telegram bağlantısı kurulduğunda otomatik hoş geldin / doğrulama mesajı gönder
    tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if tg_token and not seen_data.get("welcome_sent"):
        cid = resolve_telegram_chat_id(tg_token, tg_chat)
        if cid:
            seen_data["telegram_chat_id"] = cid
            welcome_item = {
                "id": "welcome-001",
                "source": "Atatürk Üniversitesi İŞKUR Takip Botu (@canonews_bot)",
                "title": "✅ Otomatik Takip ve Bildirim Sisteminiz Aktif Edildi!",
                "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
                "summary": "GitHub Actions üzerinde 7/24 takip başladı. Atatürk Üniversitesi İŞKUR Gençlik Programı kura sonuçları açıklandığı anda buradan mesaj alacaksınız.",
                "link": "https://atauni.edu.tr/tum-duyurular/",
            }
            if notify_user(welcome_item, is_test=True):
                seen_data["welcome_sent"] = True
                save_seen(seen_data)

    print("[BİLGİ] Atatürk Üniversitesi duyuruları ve haber kaynakları taranıyor...")
    found_items = []
    found_items.extend(check_atauni_wp_api())
    found_items.extend(check_google_news_rss())

    new_items = [item for item in found_items if item["id"] not in seen_ids]

    if not new_items:
        print(f"[BİLGİ] Yeni İŞKUR/Kura duyurusu bulunamadı. (Kontrol edilen toplam kayıt: {len(found_items)})")
        save_seen(seen_data)
        return 0

    print(f"[ MÜJDE! ] {len(new_items)} yeni duyuru/haber tespit edildi!")
    for item in new_items:
        print(f" -> Bulundu: [{item['id']}] {item['title']}")
        notify_user(item, is_test=False)
        seen_ids.add(item["id"])

    seen_data["seen_ids"] = sorted(list(seen_ids))
    save_seen(seen_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())

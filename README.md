# 🎓 Atatürk Üniversitesi İŞKUR Kura Sonuçları Takip & WhatsApp Bildirim Sistemi

Bu sistem, **Atatürk Üniversitesi İŞKUR Gençlik Programı** kura sonuçları ve duyuruları yayınlandığı anda **bilgisayarınız kapalı olsa bile** 7/24 bulut üzerinde (GitHub Actions) kontrol ederek **WhatsApp** üzerinden size anında mesaj gönderir.

## 🔍 Neleri Takip Eder?
1. **Atatürk Üniversitesi Resmi Duyuru & Haber Sistemi (`atauni.edu.tr`)**: Ana sayfa, Tüm Duyurular, SKS Daire Başkanlığı ve Öğrenci İşleri API'lerini doğrudan tarar. Duyuru içerisindeki **PDF / Excel (Asil & Yedek isim listesi)** dosyalarını otomatik algılar ve WhatsApp mesajına ekler.
2. **Google Haberler RSS Akışı**: Basına yansıyan gerçek kura sonucu haberlerini yakalar (*"açıklandı mı?", "ne zaman?"* gibi sahte/clickbait haberleri otomatik filtreler).
3. **Tekrarlı Mesaj Koruması (`seen_items.json`)**: Aynı duyuru için size yalnızca **1 kez** mesaj atar. *(2 Kasım 2026 tarihli protokol haberi `wp-29703` önceden kaydedilmiştir, yalnızca yeni gelecek duyurularda bildirim atar.)*

---

## 🚀 3 Dakikada Kurulum Rehberi

### 1. Adım: Bildirim Kanalı Seçimi (Ücretsiz & Kota Sınırı Olmayan Yöntemler)

CallMeBot'un ücretsiz sunucuları dolu (`This Bot is full`) olduğunda aşağıdaki **2 ücretsiz ve anında çalışan** yöntemden birini kullanabilirsiniz:

#### Seçenek A: Green-API ile WhatsApp Bildirimi (Tamamen Ücretsiz, Kredi Kartı İstemez)
1. [console.green-api.com](https://console.green-api.com/) adresinden ücretsiz kayıt olun.
2. **Create an instance** butonuna tıklayıp ücretsiz **Developer (Free)** paketini seçin.
3. Açılan ekranda size verilen **`idInstance`** ve **`apiTokenInstance`** değerlerini kopyalayın.
4. Aynı sayfada **Get QR** butonuna basıp, tıpkı bilgisayarda WhatsApp Web açar gibi telefonunuzun WhatsApp uygulamasından (*Bağlı Cihazlar -> Cihaz Bağla*) QR kodu okutun.
5. GitHub Secrets kısmına şu 3 değeri ekleyin:
   - `WHATSAPP_PHONE`: Telefon numaranız (Örn: `+905551234567`)
   - `GREENAPI_INSTANCE_ID`: Aldığınız `idInstance` numarası
   - `GREENAPI_API_TOKEN`: Aldığınız `apiTokenInstance` kodu

#### Seçenek B: Telegram Bot ile Bildirim (En Hızlısı - 1 Dakika Sürer, Asla Dolu Olmaz)
1. Telegram'da arama kısmına **`@BotFather`** yazıp onaylı bota girin ve `/newbot` yazın.
2. Botunuza bir isim ve sonu `bot` ile biten bir kullanıcı adı verin. Size verdiği **HTTP API Token** kodunu kopyalayın (`TELEGRAM_BOT_TOKEN`).
3. Oluşturduğunuz botun linkine tıklayıp **Başlat (Start)** butonuna basın.
4. Telegram'da **`@userinfobot`** adresine gidip Başlat'a basın; size verdiği **`Id`** numarasını kopyalayın (`TELEGRAM_CHAT_ID`).
5. GitHub Secrets kısmına `TELEGRAM_BOT_TOKEN` ve `TELEGRAM_CHAT_ID` olarak bu iki değeri ekleyin.

---

### 2. Adım: Projeyi GitHub'a Yükleme (Bilgisayar Kapalıyken 7/24 Çalışması İçin)
1. [GitHub](https://github.com/new) üzerinden yeni bir depo (repository) oluşturun (Örn: `atauni-iskur-bildirim`).
2. Bu klasördeki dosyaları (`notifier.py`, `seen_items.json`, `.github/workflows/check_iskur.yml`) deponuza yükleyin.
3. GitHub deponuzda üst menüden **Settings** -> sol menüden **Secrets and variables** -> **Actions** sayfasına girin.
4. **New repository secret** butonuna tıklayarak şu 2 bilgiyi ekleyin:
   - **`WHATSAPP_PHONE`**: Telefon numaranız (Ülke koduyla birlikte, örn: `+905551234567`)
   - **`CALLMEBOT_APIKEY`**: 1. adımda WhatsApp'tan size gelen API şifresi (örn: `1234567`)

---

### 3. Adım: Test Mesajı Gönderme
1. GitHub deponuzda üstteki **Actions** sekmesine tıklayın.
2. Soldan **"Atatürk Üniversitesi İŞKUR Kura Takip ve WhatsApp Bildirim"** iş akışını seçin.
3. Sağ taraftaki **Run workflow** butonuna tıklayıp `test_mode` seçeneğini **`true`** yapın ve yeşil **Run workflow** tuşuna basın.
4. Birkaç saniye içinde WhatsApp'ınıza test mesajı gelecektir! Bundan sonra sistem her 10 dakikada bir otomatik olarak kontrol yapacaktır.

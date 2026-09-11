# AGENTS.md: Resmi Gazete AI Takip & Denetim Sistemi

## 1. Proje Özeti
Bu proje; T.C. Resmi Gazete'yi (`resmigazete.gov.tr`) her gün belirlenen saatte otomatik tarayan, günün fihristindeki tüm mevzuatların (HTML ve PDF) **tam metinlerine/içeriklerine girip** kullanıcıların tanımladığı anahtar kelimeleri arayan, eşleşen mevzuatları Firecrawl ile kazıyıp LLM ile özetleyen, sonuçları e-posta ile ileten ve tüm denetim (audit) geçmişini PostgreSQL üzerinde tutan bir Docker mimarisidir.

Tüm servisler container ortamında çalışacak; arayüz Streamlit ile sunulacak, otomasyon ve orkestrasyon n8n üzerinden yürütülecektir.

---

## 2. Mimari Bileşenler & Sorumluluklar

| Servis | İmaj / Teknoloji | Görev ve Sorumluluk |
| :--- | :--- | :--- |
| **Database** | `postgres:15-alpine` | Kullanıcı tercihleri, crawl geçmişi ve gönderilen bildirim loglarının saklanması. |
| **Workflow Engine** | `docker.n8n.io/n8nio/n8n:latest` | Zamanlanmış tetikleyici (Cron), Firecrawl API çağrıları, tam metin arama mantığı, LLM özetleme ve mail gönderimi. |
| **Scraper** | Firecrawl API (veya Self-Hosted) | Günlük Resmi Gazete fihristini ve bağlantılı mevzuatın gövde metnini/PDF içeriklerini LLM dostu Markdown formatına dönüştürme. |
| **Kullanıcı Paneli** | Python / Streamlit | Anahtar kelime/e-posta ayarlarının yönetimi ve "nereye bakıldı, hangi metin içinde ne bulundu, kime gönderildi" audit loglarının izlenmesi. |

---

## 3. Veritabanı Şeması (`init.sql`)

PostgreSQL ilk ayağa kalktığında aşağıdaki şema otomatik olarak oluşturulmalıdır:

```sql
-- 1. Kullanıcı Ayarları Tablosu
CREATE TABLE IF NOT EXISTS user_settings (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    keywords TEXT[] NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Crawl & Tarama Denetim Logları
CREATE TABLE IF NOT EXISTS crawl_logs (
    id SERIAL PRIMARY KEY,
    crawl_date DATE DEFAULT CURRENT_DATE,
    target_url TEXT NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'SUCCESS', 'NO_MATCH', 'FAILED'
    items_scraped_count INT DEFAULT 0,
    matched_count INT DEFAULT 0,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bildirim & Özet Arşiv Tablosu
CREATE TABLE IF NOT EXISTS notifications_log (
    id SERIAL PRIMARY KEY,
    crawl_log_id INT REFERENCES crawl_logs(id) ON DELETE SET NULL,
    recipient_email VARCHAR(255) NOT NULL,
    matched_keyword VARCHAR(100) NOT NULL,
    legislation_title TEXT NOT NULL,
    legislation_url TEXT NOT NULL,
    match_location VARCHAR(50) NOT NULL, -- 'TITLE', 'BODY_TEXT', 'PDF_CONTENT'
    ai_summary TEXT NOT NULL,
    email_status VARCHAR(50) NOT NULL, -- 'SENT', 'FAILED'
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

```

---

## 4. Dosya ve Dizin Yapısı

Agent, depoda tam olarak aşağıdaki dosya hiyerarşisini oluşturmalıdır:

```text
.
├── docker-compose.yml
├── .env.example
├── init.sql
├── README.md
├── n8n/
│   └── workflows/
│       └── gazette_tracker_workflow.json
└── ui/
    ├── Dockerfile
    ├── requirements.txt
    └── app.py

```

---

## 5. Uygulama Detayları ve Kod Spesifikasyonları

### 5.1. `docker-compose.yml`

* Ortak bir bridge network (`gazette_net`) tanımlanmalıdır.
* `postgres`: 5432 portunu açmalı, `init.sql` dosyasını `/docker-entrypoint-initdb.d/` altına bağlamalı ve veriyi volume ile kalıcı kılmalıdır.
* `n8n`: `postgres` servisine bağımlı olmalı (`depends_on`), `N8N_HOST=localhost`, `N8N_PORT=5678`, `GENERIC_TIMEZONE=Europe/Istanbul` ortam değişkenlerini almalıdır.
* `ui`: `./ui` klasöründen build edilmeli, 8501 portunu açmalı ve veritabanı bağlantı değişkenlerini environment üzerinden almalıdır.

### 5.2. `ui/app.py` (Streamlit Paneli)

* **Sekme 1: Ayarlar:**
* E-posta ve virgülle ayrılmış anahtar kelimeleri girdi olarak alır.
* Form gönderildiğinde `user_settings` tablosuna `UPSERT` mantığıyla (`ON CONFLICT (email) DO UPDATE`) kayıt atar.
* Alt kısımda mevcut aktif kullanıcı aboneliklerini tablo olarak listeler.


* **Sekme 2: Denetim (Audit) & Arşiv:**
* Yan yana iki kolon: `crawl_logs` tablosunu (hangi gün hangi fihrist tarandı, kaç mevzuat incelendi) ve `notifications_log` tablosunu gösterir.
* Tabloda kelimenin nerede yakalandığı (`match_location`: başlık mı, metin/PDF içi mi) açıkça belirtilir.
* Seçilen bir mevzuat kaydının yapay zeka tarafından çıkarılmış tam özetini (`ai_summary`), eşleşen kelimesini ve kaynak linkini kart şeklinde gösterir.



### 5.3. n8n İş Akışı Mantığı (`gazette_tracker_workflow.json`)

İş akışında anahtar kelimeler **kesinlikle sadece başlıkta aranmamalı**, mevzuatın içine girilmelidir:

1. **Schedule Trigger:** Her sabah 07:00'de tetiklenir (CRON: `0 7 * * *`).
2. **Postgres Node (Get Users):** `SELECT * FROM user_settings WHERE is_active = TRUE;` sorgusuyla aktif kullanıcıları ve takip ettikleri anahtar kelimeleri çeker.
3. **Fihrist Scrape (Firecrawl):** Günün Resmi Gazete fihrist sayfasını (`https://www.resmigazete.gov.tr/` + günün fihristi) çekerek günün tüm mevzuat linklerini (HTML ve PDF URL'leri) listeler.
4. **Postgres Node (Crawl Start Log):** Hedef fihrist URL'si ve bulunan toplam mevzuat linki sayısı ile `crawl_logs` tablosuna başlangıç kaydı atar.
5. **Tam Metin Kazıma (Firecrawl Scrape - Loop):**
* Fihristteki her bir mevzuat bağlantısına sırayla girilir.
* Firecrawl mevzuatın tüm sayfa metnini ve ekli PDF dokümanlarını Markdown formatına dönüştürür.


6. **Full-Text Arama & Eşleştirme (Code Node):**
* Kullanıcı anahtar kelimeleri; hem **mevzuat başlığında** hem de Firecrawl'dan dönen **maddeler, gövde metni ve ek metinler** içinde büyük/küçük harf duyarsız (`case-insensitive` regex) aranır.
* Eşleşme durumu (`TITLE`, `BODY_TEXT`, `PDF_CONTENT`) belirlenir. Eşleşme yoksa o mevzuat atlanır.


7. **LLM Node (Gemini / OpenAI / Ollama):**
* Yalnızca eşleşme bulunan mevzuatlar LLM'e gönderilir.
* *System Prompt:* "Sen bir mevzuat analiz asistanısın. Kullanıcı '{matched_keyword}' kelimesini takip ediyor. Bu kelimenin mevzuat içerisindeki bağlamını, getirdiği değişiklikleri, yükümlülükleri ve yürürlük tarihini sade Türkçe ile 3-4 maddede özetle."


8. **Email Node (SMTP / Gmail):** İlgili kullanıcıya mevzuat başlığı, eşleşme konumu, kaynak linki ve LLM özetini içeren e-postayı gönderir.
9. **Postgres Node (Log Notification):** `notifications_log` tablosuna mevzuat başlığını, linkini, eşleşme konumunu (`match_location`), AI özetini, alıcı adresini ve `SENT` durumunu kaydeder.
10. **Postgres Node (Crawl Finalize):** `crawl_logs` tablosunu eşleşen toplam kayıt sayısı ve `SUCCESS` durumuyla günceller.

---

## 6. Geliştirici ve Agent Doğrulama Kriterleri

Agent implementasyonu tamamladığında aşağıdaki adımları sırasıyla doğrulamalıdır:

1. `docker compose up -d --build` komutunun hatasız çalışması ve 3 servisin de ayağa kalkması.
2. PostgreSQL `gazette_db` içinde `init.sql` tablolarının eksiksiz oluştuğunun doğrulanması.
3. Streamlit panelinde (`http://localhost:8501`) bir test kullanıcısı ve anahtar kelimesi kaydedildiğinde `user_settings` tablosuna başarıyla yazılması.
4. n8n workflow testinde bir mevzuat linkinin gövdesinde anahtar kelime geçtiğinde, başlıkta kelime yer almasa dahi sistemin bunu yakalayıp özet üretmesi, mail göndermesi ve Postgres'e `match_location = 'BODY_TEXT'` olarak kaydetmesi.
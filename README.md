#  YouTube Shorts Viral Video Transformation Bot - MVP

##  MVP TAMAMLANDI (Faz 1)

YouTube Shorts için viral video transformation bot'unun ilk aşaması başarıyla tamamlandı.

###  Yapılanlar

#### 1. Klasör Yapısı 
```
youtube-shorts-bot/
├── downloads/          # İndirilecek videolar
├── scripts/
│   ├── drafts/        # AI taslak scriptler
│   └── finals/        # Düzenlenmiş final scriptler
├── audio/             # TTS veya manuel kayıtlar
├── ready/             # Onay bekleyen videolar
├── approved/          # Onaylanmış videolar
├── uploaded/          # Upload edilmiş videolar
├── rejected/          # Reddedilen videolar
├── modules/           # Python modülleri
│   ├── viral_scraper.py     MVP (dummy data)
│   └── __init__.py
├── modules_old/       # Eski modüller (yedek)
└── config/
    └── config.yaml    # Yeni config template
```

#### 2. Yeni Dosyalar 
- `.env.example` - API key template'i
- `config/config.yaml` - Yeni config yapısı (transformation bot için)
- `requirements.txt` - Güncel paketler (Selenium, yt-dlp, opencv, vs.)
- `modules/viral_scraper.py` - Instagram scraper (dummy data ile test)
- `main.py` - Yeni orchestrator (MVP)

#### 3. Modül: viral_scraper.py 

**Fonksiyonlar:**
- `__init__(config)` - Config yükleme
- `_parse_view_count(text)` - "1.2M views" → 1200000
- `scrape_instagram()` - Instagram scraping (şu an dummy 5 video)
- `scrape_tiktok()` - Placeholder (sonraki versiyon)
- `scrape_facebook()` - Placeholder (sonraki versiyon)
- `display_videos(videos)` - Terminal'de formatlanmış liste
- `user_select(videos)` - Kullanıcı seçimi (validation ile)

**Dummy Data Örnekleri:**
- 5 örnek Instagram Reels videosu
- Views: 1.8M - 5.1M arası
- Duration: 38-58 saniye
- Kategoriler: ASMR, gold panning, woodworking, food challenge, nature

###  Nasıl Çalıştırılır?

```bash
# 1. Paketleri kur
pip install -r requirements.txt

# 2. .env dosyası oluştur (varsa atla)
cp .env.example .env
# API key'leri .env'ye ekle

# 3. MVP'yi çalıştır
python main.py
```

### Beklenen Çıktı

```
================================================================================
 YOUTUBE SHORTS VİRAL VİDEO TRANSFORMATION BOT
 MVP Version: Video Scraping & Selection
================================================================================

[1/5] Checking FFmpeg...
 FFmpeg is installed

[2/5] Loading config...
 Config loaded successfully

[3/5] Initializing viral scraper...
ViralScraper initialized

[4/5] Scraping Instagram videos...
Found 5 Instagram videos (dummy data)

================================================================================
  VİRAL VIDEOLAR (1M+ görüntülenme)
================================================================================

[1] INSTAGRAM - 2.300.000 görüntülenme (45s)
     Amazing soap cutting ASMR - Satisfying sounds
     https://www.instagram.com/reel/C1a2b3c4d5/

[2] INSTAGRAM - 5.100.000 görüntülenme (52s)
     Gold panning discovery - Found real gold!
     https://www.instagram.com/reel/D6e7f8g9h0/

...

 Hangi videoları işlemek istersiniz?
   Örnek: 1,3,5  veya  1-3  veya  all

Seçim: 1,2,3

================================================================================
  MVP TAMAMLANDI - 3 video seçildi
================================================================================
```

##  Sonraki Adımlar (Faz 2)

### 1. video_downloader.py
**Görev:** Seçilen videoları indir, orijinal sesi ayır

**Fonksiyonlar:**
- `download_video(url, output_path)` - yt-dlp ile video indirme
- `extract_audio(video_path)` - FFmpeg ile ses ayırma
- `remove_audio_track(video_path)` - Silent video oluşturma

**Tools:** yt-dlp, FFmpeg

**Output:** `downloads/{video_id}_silent.mp4`

---

### 2. ai_script_writer.py
**Görev:** Video analiz et, Türkçe draft script yaz

**Fonksiyonlar:**
- `analyze_video(video_path)` - Groq Vision API ile video analiz
- `generate_draft(description, duration)` - Structured script (Hook/Story/Climax/CTA)

**AI Model:** Groq Llama 3.3 70B

**Output:** `scripts/drafts/{video_id}_draft.json`

---

### 3. script_editor.py
**Görev:** Interactive editing interface

**Fonksiyonlar:**
- `load_draft(script_path)` - Draft'ı yükle
- `interactive_edit()` - Terminal UI ile düzenleme
- `save_final(script_path)` - Final script'i kaydet

**Output:** `scripts/finals/{video_id}_final.json`

---

### 4. audio_manager.py
**Görev:** AI TTS veya manuel ses kaydı

**Fonksiyonlar:**
- `tts_generate(text, voice_id)` - ElevenLabs TTS
- `manual_record(script_text)` - Microphone recording
- `user_choice()` - AI/Manuel seçim

**Output:** `audio/{video_id}_narration.mp3`

---

### 5. video_composer.py
**Görev:** Final montaj (video + ses + MrBeast subtitle)

**Fonksiyonlar:**
- `add_voiceover(silent_video, audio)` - Ses ekleme
- `generate_subtitles_mrbeast(script)` - Subtitle PNG'leri oluştur
- `apply_subtitles(video, subtitles)` - Overlay
- `export_final(video, output_path)` - 1080x1920, <60s

**MrBeast Style:**
- Font: Impact, 72px
- Color: White + Yellow outline (5px)
- Word-by-word animation

**Output:** `ready/{video_id}.mp4`

---

### 6. approval_interface.py
**Görev:** Manuel onay sistemi

**Interface:**
```
=== READY FOR APPROVAL ===
1. soap_cutting_001.mp4 (52s)

[p] Play  [a] Approve  [r] Reject  [q] Quit
```

**Output:** `approved/{video_id}.mp4` veya `rejected/{video_id}.mp4`

---

### 7. Gerçek Selenium Scraping
**Görev:** Dummy data yerine gerçek Instagram/TikTok/FB scraping

**Challenges:**
- Anti-bot sistemleri
- Rate limiting
- View count parsing
- Face/logo detection

---

##  Notlar

### FFmpeg Kontrolü
 MVP'de implement edildi. `check_ffmpeg()` fonksiyonu var.

### ChromeDriver
`webdriver-manager` paketi requirements.txt'te (otomatik yönetim).

### Face/Logo Detection
Şimdilik manuel kontrol. Sonra OpenCV Haar Cascades veya OCR eklenebilir.

### Config
`.cursorrules`'teki config template kullanıldı. Tüm değerler config.yaml'da.

---

##  Test Edilenler

-  Klasör yapısı oluşturma
-  Mevcut modülleri yedekleme (modules_old/)
-  Config yükleme (YAML + env substitution)
-  FFmpeg kontrolü
-  ViralScraper başlatma
-  Dummy video listesi gösterme
-  View count parsing ("1.2M" → 1200000)
-  Formatlanmış terminal output
-  User selection (interactive mode'da çalışır, background'da EOF)

---

##  MVP Başarı Kriterleri

Tüm klasörler oluşturuldu  
.gitkeep dosyaları eklendi  
 Eski modüller yedeklendi  
Yeni config yapısı hazır  
requirements.txt güncellendi  
viral_scraper.py minimal çalışır halde  
main.py test CLI çalışıyor  
FFmpeg kontrolü yapılıyor  
Terminal output güzel formatlanmış  

---

**MVP Tamamlandı! Sonraki modül için hazırız.**
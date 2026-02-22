#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viral Scraper Module
Instagram, TikTok, Facebook'tan 1M+ goruntulenen videolari scrape eder.

This version uses multiple Instagram scraping strategies.
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOTENV_PATH = PROJECT_ROOT / ".env"


def _load_env() -> None:
    """Load .env from project root deterministically."""
    if DOTENV_PATH.exists():
        load_dotenv(dotenv_path=DOTENV_PATH, override=True)
    else:
        logger.warning(".env not found at %s", DOTENV_PATH)

    missing = []
    if not os.getenv("INSTAGRAM_USERNAME"):
        missing.append("INSTAGRAM_USERNAME")
    if not os.getenv("INSTAGRAM_PASSWORD"):
        missing.append("INSTAGRAM_PASSWORD")

    if missing:
        logger.warning("Missing Instagram env vars: %s", ", ".join(missing))
    else:
        user = os.getenv("INSTAGRAM_USERNAME", "")
        logger.info("Instagram credentials loaded: %s***", user[:3])


_load_env()

CATEGORIES = {
    "1": {
        "name": "ASMR & Satisfying",
        "hashtags": ["asmr", "satisfying", "oddlysatisfying", "relaxing", "asmrsounds"],
    },
    "2": {
        "name": "Maden & Altın Arama",
        "hashtags": ["goldmining", "treasurehunting", "goldrush", "goldpanning", "metaldetecting"],
    },
    "3": {
        "name": "Doğal Taş & Mineraller",
        "hashtags": ["gemstones", "crystals", "minerals", "gems", "stones"],
    },
    "4": {
        "name": "Değerli Taşlar",
        "hashtags": ["emerald", "jade", "ruby", "sapphire", "diamond"],
    },
    "5": {
        "name": "DIY & El İşleri",
        "hashtags": ["diy", "crafts", "handmade", "woodworking", "restoration"],
    },
    "6": {
        "name": "Doğa & Manzara",
        "hashtags": ["nature", "naturephotography", "landscape", "wilderness", "earthpix"],
    },
    "7": {
        "name": "Yemek (Hands Only)",
        "hashtags": ["cooking", "recipe", "foodasmr", "cookingvideo", "foodprep"],
    },
    "8": {
        "name": "Tümü (Karışık)",
        "hashtags": ["viral", "satisfying", "trending", "asmr", "nature"],
    },
}


class ViralScraper:
    """
    Instagram, TikTok, Facebook'tan viral videolari scrape eden sinif.

    Attributes:
        config (dict): Config.yaml'dan yuklenen ayarlar
        min_views (int): Minimum goruntulenme sayisi
        max_videos (int): Platform basina maksimum video sayisi
        rate_limit (int): Istekler arasi bekleme suresi (saniye)
    """

    def __init__(self, config: dict):
        """
        Args:
            config: Config dictionary (yaml'dan yuklenen)
        """
        self.config = config
        self.min_views = config.get('scraping', {}).get('min_views', 1_000_000)
        self.max_videos = config.get('scraping', {}).get('max_videos_per_platform', 10)
        self.rate_limit = config.get('scraping', {}).get('rate_limit_seconds', 2)
        self.user_agents = config.get('scraping', {}).get('user_agents', [])

        scraper_cfg = config.get('scraper', {})
        self.max_scrolls = int(scraper_cfg.get('max_scrolls', 5))
        self.timeout = int(scraper_cfg.get('timeout', 10))
        self.scraper_min_views = int(scraper_cfg.get('min_views', self.min_views))

        logger.info("ViralScraper initialized")
        logger.debug(
            "Min views: %s, Max videos/platform: %s, Max scrolls: %s",
            self.min_views,
            self.max_videos,
            self.max_scrolls,
        )

    def _dummy_data(self) -> List[Dict]:
        """Return dummy data (fallback)."""
        return [
            {
                "id": "insta_001",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/C1a2b3c4d5/",
                "views": 2_300_000,
                "description": "Amazing soap cutting ASMR - Satisfying sounds",
                "duration": 45,
            },
            {
                "id": "insta_002",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/D6e7f8g9h0/",
                "views": 5_100_000,
                "description": "Gold panning discovery - Found real gold!",
                "duration": 52,
            },
            {
                "id": "insta_003",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/E1i2j3k4l5/",
                "views": 1_800_000,
                "description": "Oddly satisfying woodworking",
                "duration": 38,
            },
            {
                "id": "insta_004",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/F6m7n8o9p0/",
                "views": 3_400_000,
                "description": "Extreme food challenge - 100 layers!",
                "duration": 58,
            },
            {
                "id": "insta_005",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/G1q2r3s4t5/",
                "views": 4_200_000,
                "description": "Nature restoration time-lapse",
                "duration": 41,
            },
        ]

    def _setup_driver(self):
        """
        Setup Chrome with basic options.
        """
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        import random

        options = Options()

        # FIXED: User agent rotation from config
        user_agents = self.config.get('scraping', {}).get('user_agents', [])
        if user_agents:
            selected_ua = random.choice(user_agents)
            options.add_argument(f'--user-agent={selected_ua}')
            logger.info(f"Using UA: {selected_ua[:60]}...")
        else:
            # Fallback to default
            options.add_argument(
                '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            logger.warning("No user agents in config, using default UA")

        # Persistent profile (user-data-dir)
        user_data_dir = self.config.get('scraper', {}).get('chrome_profile')
        if not user_data_dir:
            user_data_dir = str(PROJECT_ROOT / ".chrome_profile")
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)
        options.add_argument(f'--user-data-dir={user_data_dir}')

        # Headless (optional)
        if self.config.get('scraper', {}).get('headless', False):
            options.add_argument('--headless=new')

        # Anti-detection
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        driver = webdriver.Chrome(options=options)
        try:
            driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception:
            pass
        return driver

    def _safe_quit(self, driver) -> None:
        """Quit driver safely without raising."""
        if driver is None:
            return
        try:
            driver.quit()
        except Exception:
            pass

    def _wait_page_ready(self, driver) -> bool:
        """Wait for document.readyState == complete."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException, WebDriverException

        try:
            WebDriverWait(driver, self.timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return True
        except (TimeoutException, WebDriverException) as exc:
            logger.warning("Page readyState timeout: %s", exc)
            return False

    def _wait_for_post_links(self, driver) -> bool:
        """Wait until reel/p links appear."""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException

        try:
            WebDriverWait(driver, self.timeout).until(
                lambda d: len(self._collect_post_links(d)) > 0
            )
            return True
        except TimeoutException:
            return False

    def _return_to_listing(self, driver, listing_url: str) -> bool:
        """Return to listing page safely (no back)."""
        from selenium.common.exceptions import WebDriverException

        for _ in range(2):
            try:
                driver.get(listing_url)
                self._wait_page_ready(driver)
            except WebDriverException:
                continue

            current_url = (driver.current_url or "").lower()
            if "/p/" in current_url or "/reel/" in current_url:
                continue
            return True

        return False

    def _has_login_form(self, driver) -> bool:
        """Return True if username field is visible (login form present)."""
        from selenium.webdriver.common.by import By

        selectors = [
            (By.NAME, "username"),
            (By.CSS_SELECTOR, "input[name='username']"),
            (By.XPATH, "//input[@aria-label='Phone number, username, or email']"),
        ]

        try:
            for by, selector in selectors:
                elements = driver.find_elements(by, selector)
                for el in elements:
                    if el.is_displayed():
                        return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Login form check failed: %s", exc)
            return True
        return False

    def _is_logged_in(self, driver) -> bool:
        """Strict login check (no false positives)."""
        try:
            current_url = (driver.current_url or "").lower()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read current_url: %s", exc)
            return False

        blocked_tokens = ["accounts/login", "/challenge/", "/checkpoint/"]
        if any(token in current_url for token in blocked_tokens):
            return False

        if self._has_login_form(driver):
            return False

        return True

    def _manual_login(self, driver) -> bool:
        """Manual login helper (user-driven)."""
        print("\n" + "=" * 80)
        print(" INSTAGRAM GİRİŞ GEREKLİ")
        print("=" * 80)
        print("\n1. Açılan Chrome penceresinde Instagram'a giriş yapın")
        print("2. Ana sayfaya geldiğinizde bu terminal'e geri dönün")
        print("3. Enter tuşuna basın\n")
        input("Giriş yaptıktan sonra Enter'a basın: ")

        # BUG FIX: Removed driver.get() to preserve user's manual login session
        # The driver.get() call was overwriting the user's authentication
        # Now we just wait and verify the current page status

        time.sleep(1)  # Brief pause for user navigation to complete

        if self._is_logged_in(driver):
            logger.info("Manual login başarılı")
            return True

        current_url = (driver.current_url or "").lower()
        if any(token in current_url for token in ["/challenge/", "/checkpoint/"]):
            logger.error("Login challenge/checkpoint detected: %s", current_url)
        else:
            logger.error("Giris dogrulanamadi")
        return False

    def _login(self, driver) -> bool:
        """Auto login if possible; fallback to manual login with verification."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")

        if not username or not password:
            logger.warning("Auto-login skipped (missing credentials)")
            return self._manual_login(driver)

        logger.info("Auto-login starting for %s***", username[:3])

        try:
            driver.get("https://www.instagram.com/accounts/login/")
            self._wait_page_ready(driver)

            username_field = WebDriverWait(driver, self.timeout).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            username_field.clear()
            username_field.send_keys(username)

            password_field = driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(password)

            login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            login_btn.click()

            # FIXED: Wait for redirect instead of fixed sleep
            import random
            time.sleep(random.uniform(2.5, 4.0))  # Human-like delay
            self._wait_page_ready(driver)

            # Wait for either redirect to home or challenge page
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.common.exceptions import TimeoutException

            try:
                # Wait for URL to change away from login page
                WebDriverWait(driver, 10).until(
                    lambda d: "/accounts/login" not in (d.current_url or "").lower()
                )
            except TimeoutException:
                logger.warning("Login redirect timeout")

            if self._is_logged_in(driver):
                logger.info("Auto-login successful")
                return True

            current_url = (driver.current_url or "").lower()
            if any(token in current_url for token in ["/challenge/", "/checkpoint/"]):
                logger.error("Login challenge/checkpoint detected: %s", current_url)
                return False

            logger.warning("Auto-login incomplete, switching to manual login")
            return self._manual_login(driver)

        except Exception as exc:  # noqa: BLE001
            logger.error("Auto-login failed: %s", exc)
            return self._manual_login(driver)

    def _check_login(self, driver) -> bool:
        """
        Login check:
        - If login page / challenge / checkpoint detected -> login required
        - If username field visible -> login required
        """
        from selenium.common.exceptions import WebDriverException

        try:
            driver.get("https://www.instagram.com/")
            self._wait_page_ready(driver)
        except WebDriverException as exc:
            logger.error("Failed to open Instagram: %s", exc)
            return False

        if self._is_logged_in(driver):
            logger.info("Login verified")
            return True

        logger.info("Login required, starting login flow")
        return self._login(driver)

    def _select_category(self) -> List[str]:
        """User selects content category."""
        print("\n" + "=" * 80)
        print(" İÇERİK KATEGORİSİ SEÇİN (Telif-Safe)")
        print("=" * 80)

        for key, cat in CATEGORIES.items():
            hashtags_preview = ", ".join(cat['hashtags'][:3])
            print(f"[{key}] {cat['name']:<25} ({hashtags_preview}...)")

        print("=" * 80)

        while True:
            choice = input("\nSeçim (1-8): ").strip()
            if choice in CATEGORIES:
                selected = CATEGORIES[choice]
                print(f"\nSeçildi: {selected['name']}")
                print(f"Hashtag'ler: {', '.join(selected['hashtags'])}\n")
                return selected['hashtags']
            print("Geçersiz seçim! 1-8 arası bir sayı girin.")

    def _parse_view_text(self, text: str) -> int:
        """
        Parse view count string into integer.
        """
        text = text.lower().replace(',', '').replace(' ', '')
        match = re.search(r'([\d.]+)([km])?', text)
        if not match:
            return 0
        number = float(match.group(1))
        unit = match.group(2)
        if unit == 'k':
            return int(number * 1_000)
        if unit == 'm':
            return int(number * 1_000_000)
        return int(number)

    def _parse_view_count(self, driver) -> int:
        """Parse view count from meta and DOM (locale-safe, stale-safe)."""
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import StaleElementReferenceException

        def _to_int(num_str: str, unit: str | None) -> int | None:
            if not num_str:
                return None
            s = num_str.strip().lower()
            if s in {".", ",", ""}:
                return None

            unit = (unit or "").lower()
            if unit in {"mn"}:
                unit = "m"

            if unit in {"k", "m"}:
                s = s.replace(",", ".")
                if s.count(".") > 1:
                    parts = s.split(".")
                    s = parts[0] + "." + "".join(parts[1:])
                try:
                    val = float(s)
                except ValueError:
                    return None
                if unit == "k":
                    return int(val * 1_000)
                return int(val * 1_000_000)

            digits = re.sub(r"[^0-9]", "", s)
            if not digits:
                return None
            try:
                return int(digits)
            except ValueError:
                return None

        def _parse_from_text(text: str) -> int | None:
            if not text:
                return None
            t = text.lower()
            for match in re.finditer(r"([\d.,]+)\s*(mn|m|k)\b", t):
                val = _to_int(match.group(1), match.group(2))
                if val is not None:
                    return val
            for match in re.finditer(r"([\d.,]+)\s*views?", t):
                val = _to_int(match.group(1), None)
                if val is not None:
                    return val
            for match in re.finditer(r"[\d][\d.,]+", t):
                val = _to_int(match.group(0), None)
                if val is not None:
                    return val
            return None

        try:
            meta_elems = driver.find_elements(
                By.XPATH,
                "//meta[@property='og:description'] | //meta[@name='description']",
            )
            for elem in meta_elems:
                try:
                    content = elem.get_attribute("content") or ""
                except StaleElementReferenceException:
                    continue
                val = _parse_from_text(content)
                if val is not None:
                    return val
        except Exception:
            pass

        try:
            view_elements = driver.find_elements(
                By.XPATH,
                "//*[contains(text(), 'view') or contains(text(), 'M') or contains(text(), 'K')]",
            )
            for elem in view_elements:
                try:
                    text = (elem.text or "").strip()
                except StaleElementReferenceException:
                    continue
                val = _parse_from_text(text)
                if val is not None:
                    return val
        except Exception as exc:  # noqa: BLE001
            logger.error("Error parsing view count: %s", exc)

        return 0

    def _parse_description(self, driver) -> str:
        """Parse video description/caption."""
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import NoSuchElementException

        selectors = [
            "//span[contains(@class, '_ap3a')]",
            "//h1[contains(@class, 'x1lliihq')]",
        ]
        for selector in selectors:
            try:
                elem = driver.find_element(By.XPATH, selector)
                return elem.text.strip()[:100]
            except NoSuchElementException:
                continue
            except Exception:  # noqa: BLE001
                continue
        return "No description"

    def _parse_duration(self, driver) -> int:
        """Parse video duration in seconds."""
        from selenium.webdriver.common.by import By

        try:
            video = driver.find_element(By.TAG_NAME, 'video')
            duration = driver.execute_script("return arguments[0].duration;", video)
            return int(duration) if duration else 45
        except Exception as exc:  # noqa: BLE001
            logger.error("Error parsing duration: %s", exc)
            return 45

    def _normalize_instagram_url(self, url: str) -> str:
        """Ensure Instagram URLs are absolute."""
        if url.startswith("/"):
            url = f"https://www.instagram.com{url}"
        # Strip query/fragment
        url = url.split("?", 1)[0].split("#", 1)[0]
        return url

    def _collect_post_links(self, driver) -> List[str]:
        """Collect reel/post links using multiple fallback strategies."""
        from selenium.webdriver.common.by import By

        urls: List[str] = []

        # Detect if we're on a search page
        current_url = driver.current_url or ""
        is_search_page = "/explore/search/" in current_url

        # STRATEGY 1: Modern CSS with role attribute (Instagram 2025+)
        try:
            elements = driver.find_elements(
                By.CSS_SELECTOR, "a[href*='/reel/'][role='link'], a[href*='/p/'][role='link']"
            )
            if elements:
                logger.debug(f"Strategy 1 (modern CSS): {len(elements)} elements")
                for el in elements:
                    href = el.get_attribute("href")
                    if href:
                        urls.append(self._normalize_instagram_url(href))
        except Exception as exc:
            logger.debug(f"Strategy 1 failed: {exc}")

        # STRATEGY 2: Search page specific selectors
        if not urls and is_search_page:
            try:
                # Instagram search sayfası farklı class'lar kullanıyor
                # article, div elements içinde linkler olabilir
                search_selectors = [
                    "article a",
                    "div[role='button'] a",
                    "a.x1i10hfl",  # Instagram dynamic class
                    "main a",
                ]

                for selector in search_selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        logger.debug(f"Strategy 2 (search page {selector}): {len(elements)} elements")
                        for el in elements:
                            href = el.get_attribute("href")
                            if href and ("/reel/" in href or "/p/" in href):
                                urls.append(self._normalize_instagram_url(href))

                        if urls:
                            break

            except Exception as exc:
                logger.debug(f"Strategy 2 (search page) failed: {exc}")

        # STRATEGY 3: Classic CSS selector (backward compatibility)
        if not urls:
            try:
                elements = driver.find_elements(
                    By.CSS_SELECTOR, "a[href*='/reel/'], a[href*='/p/']"
                )
                if elements:
                    logger.debug(f"Strategy 3 (classic CSS): {len(elements)} elements")
                    for el in elements:
                        href = el.get_attribute("href")
                        if href:
                            urls.append(self._normalize_instagram_url(href))
            except Exception as exc:
                logger.debug(f"Strategy 3 failed: {exc}")

        # STRATEGY 4: XPath fallback
        if not urls:
            try:
                elements = driver.find_elements(
                    By.XPATH, "//a[contains(@href, '/reel/') or contains(@href, '/p/')]"
                )
                if elements:
                    logger.debug(f"Strategy 3 (XPath): {len(elements)} elements")
                    for el in elements:
                        href = el.get_attribute("href")
                        if href:
                            urls.append(self._normalize_instagram_url(href))
            except Exception as exc:
                logger.debug(f"Strategy 3 failed: {exc}")

        # STRATEGY 4: JavaScript injection (most reliable)
        if not urls:
            try:
                script = """
                return Array.from(document.querySelectorAll('a'))
                    .filter(a => a.href && (a.href.includes('/reel/') || a.href.includes('/p/')))
                    .map(a => a.href);
                """
                js_urls = driver.execute_script(script)
                if js_urls:
                    logger.debug(f"Strategy 4 (JavaScript): {len(js_urls)} links")
                    urls.extend([self._normalize_instagram_url(u) for u in js_urls])
            except Exception as exc:
                logger.debug(f"Strategy 4 failed: {exc}")

        # STRATEGY 5: Regex fallback from page source
        if not urls:
            try:
                html = driver.page_source or ""
                paths = re.findall(r'href="(/(?:reel|p)/[^"/]+/)"', html)
                if paths:
                    logger.debug(f"Strategy 5 (regex): {len(paths)} matches")
                    for path in paths:
                        urls.append(f"https://www.instagram.com{path}")
            except Exception as exc:
                logger.debug(f"Strategy 5 failed: {exc}")

        # SEARCH SAYFASI VİDEO ÖN-FİLTRESİ
        # Search sayfasında /p/ URL'leri hem fotoğraf hem video içerebilir.
        # Thumbnail grid DOM'undan video indicator'larına bakarak açmadan filtrele.
        # Bu sayede yüzlerce fotoğraf URL'i için 17s/adet harcamaktan kaçınılır.
        if is_search_page and urls:
            try:
                video_hrefs = driver.execute_script("""
                    var results = [];
                    var seen = {};
                    var links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
                    for (var i = 0; i < links.length; i++) {
                        var a = links[i];
                        var href = a.getAttribute('href');
                        if (!href || seen[href]) continue;
                        seen[href] = true;

                        // Thumbnail container'ı bul (yukarıya doğru 5 adım)
                        var container = a;
                        for (var j = 0; j < 5; j++) {
                            if (!container.parentElement) break;
                            container = container.parentElement;
                            if (container.tagName === 'LI' || container.tagName === 'ARTICLE') break;
                            if (container.children.length > 4) break;
                        }

                        var html = container.innerHTML || '';
                        var text = container.textContent || '';

                        // Video indicator'ları:
                        // 1. Duration overlay (ör: "0:32", "1:05") — video/reel için gösterilir
                        var hasDuration = /\\b\\d{1,2}:\\d{2}\\b/.test(text);
                        // 2. Instagram'ın play/video/reel SVG icon'ları
                        var hasSvg = html.indexOf('<svg') !== -1 && (
                            html.indexOf('M10.813') !== -1 ||
                            html.toLowerCase().indexOf('videocamera') !== -1 ||
                            html.toLowerCase().indexOf('playcircle') !== -1
                        );
                        // 3. aria-label "Video" veya "Reel" içeriyor
                        var lowerHtml = html.toLowerCase();
                        var hasAriaVideo = lowerHtml.indexOf('aria-label="video') !== -1 ||
                                           lowerHtml.indexOf("aria-label='video") !== -1 ||
                                           lowerHtml.indexOf('aria-label="reel') !== -1 ||
                                           lowerHtml.indexOf("aria-label='reel") !== -1;
                        // 4. /reel/ URL — kesinlikle video
                        var isReel = href.indexOf('/reel/') !== -1;

                        if (hasDuration || hasSvg || hasAriaVideo || isReel) {
                            results.push(href);
                        }
                    }
                    return results;
                """)

                if video_hrefs and len(video_hrefs) > 0:
                    total_before = len(urls)
                    filtered_urls = set(self._normalize_instagram_url(h) for h in video_hrefs)
                    # /reel/ URL'lerini de koru (zaten isReel ile yakalanıyor ama güvenlik için)
                    reel_urls = {u for u in urls if '/reel/' in u}
                    urls = list(filtered_urls | reel_urls)
                    logger.info(
                        "Search page video pre-filter: %d video links (from %d total /p/ links)",
                        len(urls),
                        total_before,
                    )
                else:
                    logger.warning(
                        "Search page video pre-filter: 0 video indicators found in DOM "
                        "— falling back to all %d links (will be slow, mostly photos)",
                        len(urls),
                    )
                    # urls değişmeden kalır — mevcut davranışa fallback
            except Exception as exc:
                logger.warning(
                    "Search page video pre-filter failed (%s) — using all %d links",
                    exc,
                    len(urls),
                )
                # urls değişmeden kalır — güvenli fallback

        # Deduplicate
        seen = set()
        unique_urls: List[str] = []
        for u in urls:
            u = self._normalize_instagram_url(u)
            if u in seen:
                continue
            seen.add(u)
            unique_urls.append(u)

        return unique_urls

    def _collect_post_links_split(self, driver) -> tuple[List[str], List[str]]:
        """Return (reel_links, post_links) in priority order."""
        links = self._collect_post_links(driver)
        reels = [u for u in links if "/reel/" in u]
        posts = [u for u in links if "/p/" in u]
        return reels, posts

    def _collect_tag_links(self, driver) -> List[str]:
        """Collect related hashtag links (DOM + regex fallback)."""
        from selenium.webdriver.common.by import By

        urls: List[str] = []
        elements = driver.find_elements(
            By.CSS_SELECTOR,
            "a[href^='/explore/tags/'], a[href^='https://www.instagram.com/explore/tags/']",
        )
        if not elements:
            elements = driver.find_elements(
                By.XPATH, "//a[contains(@href,'/explore/tags/')]"
            )

        for el in elements:
            href = el.get_attribute("href")
            if not href:
                continue
            urls.append(self._normalize_instagram_url(href))

        if not urls:
            html = driver.page_source or ""
            tags = re.findall(r'/explore/tags/([^/]+)/', html)
            for tag in tags:
                urls.append(f"https://www.instagram.com/explore/tags/{tag}/")

        seen = set()
        unique_urls: List[str] = []
        for u in urls:
            u = self._normalize_instagram_url(u)
            if u in seen:
                continue
            seen.add(u)
            unique_urls.append(u)

        return unique_urls

    def _extract_tag_from_url(self, url: str) -> str | None:
        """Extract tag name from /explore/tags/<tag>/ URL."""
        if "/explore/tags/" not in url:
            return None
        clean = self._normalize_instagram_url(url)
        tag_part = clean.split("/explore/tags/")[-1]
        tag = tag_part.split("/")[0].strip()
        return tag or None

    def _log_link_debug(self, driver, context: str) -> None:
        """Log debug info when no links are found."""
        from selenium.webdriver.common.by import By

        current_url = ""
        try:
            current_url = driver.current_url
        except Exception:
            current_url = ""

        total_links = len(driver.find_elements(By.TAG_NAME, "a"))
        css_count = len(
            driver.find_elements(By.CSS_SELECTOR, "a[href*='/reel/'], a[href*='/p/']")
        )
        xpath_count = len(
            driver.find_elements(
                By.XPATH, "//a[contains(@href,'/reel/') or contains(@href,'/p/')]"
            )
        )
        tag_count = len(
            driver.find_elements(
                By.CSS_SELECTOR,
                "a[href^='/explore/tags/'], a[href*='/explore/tags/']",
            )
        )

        html = driver.page_source or ""
        regex_reel = len(re.findall(r'href="/reel/([^"/]+)/"', html))
        regex_post = len(re.findall(r'href="/p/([^"/]+)/"', html))
        regex_tag = len(re.findall(r'/explore/tags/([^/]+)/', html))

        logger.warning("%s: no post links found. current_url=%s", context, current_url)
        logger.warning("%s: total <a>=%d", context, total_links)
        logger.warning(
            "%s: link counts css=%d xpath=%d tag=%d",
            context,
            css_count,
            xpath_count,
            tag_count,
        )
        logger.warning(
            "%s: regex counts reel=%d post=%d tag=%d",
            context,
            regex_reel,
            regex_post,
            regex_tag,
        )
        snippet = html[:300]
        logger.debug("%s: page_source head: %s", context, snippet)

    def _extract_video_url(self, driver) -> str | None:
        """Try multiple strategies to locate a video URL."""
        from selenium.webdriver.common.by import By

        meta_props = ["og:video:secure_url", "og:video"]
        for prop in meta_props:
            try:
                elems = driver.find_elements(By.XPATH, f"//meta[@property='{prop}']")
                if elems:
                    content = elems[0].get_attribute("content")
                    if content:
                        return content
            except Exception:
                continue

        try:
            video = driver.find_element(By.TAG_NAME, "video")
            src = video.get_attribute("src")
            if src:
                return src
        except Exception:
            pass

        try:
            html = driver.page_source or ""
            match = re.search(r'property="og:video(:secure_url)?" content="([^"]+)"', html)
            if match:
                return match.group(2)
        except Exception:
            pass

        return None

    def _parse_reel_quick(self, driver, url: str, listing_url: str | None = None) -> Dict | None:
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException, InvalidSessionIdException, WebDriverException

        result: Dict | None = None
        try:
            driver.get(url)
            self._wait_page_ready(driver)

            try:
                WebDriverWait(driver, self.timeout).until(
                    lambda d: self._extract_video_url(d) is not None
                )
            except TimeoutException:
                pass

            video_url = self._extract_video_url(driver)
            if not video_url:
                if "/reel/" in url:
                    logger.warning("No video media found for %s", url)
                else:
                    logger.info("No video media found (post): %s", url)
            else:
                if '/reel/' in url:
                    shortcode = url.split('/reel/')[-1].rstrip('/').split('/')[0]
                elif '/p/' in url:
                    shortcode = url.split('/p/')[-1].rstrip('/').split('/')[0]
                else:
                    shortcode = url.rstrip('/').split('/')[-1]

                views = self._parse_view_count(driver)
                description = self._parse_description(driver)
                duration = self._parse_duration(driver)

                result = {
                    "id": f"insta_{shortcode}",
                    "platform": "instagram",
                    "url": url,
                    "views": views,
                    "description": description,
                    "duration": duration,
                }

        except (InvalidSessionIdException, WebDriverException) as exc:
            logger.error("WebDriver session error while parsing %s: %s", url, exc)
            result = None

        except Exception as exc:
            logger.error("Failed to parse %s: %s", url, exc)
            result = None

        finally:
            if listing_url:
                if not self._return_to_listing(driver, listing_url):
                    logger.warning(
                        "Listing page return failed, skipping post: %s (listing=%s)",
                        url,
                        listing_url,
                    )
                    result = None

        return result

    def _click_reels_tab_if_available(self, driver):
        """Try to click Reels tab on search/explore pages."""
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import NoSuchElementException, TimeoutException

        try:
            # Instagram search sayfasında "Reels" tab'i ara
            reels_tab_selectors = [
                "//a[contains(text(), 'Reels')]",
                "//a[contains(text(), 'reels')]",
                "//span[contains(text(), 'Reels')]",
                "//div[contains(text(), 'Reels')]",
                "//button[contains(text(), 'Reels')]",
            ]

            for selector in reels_tab_selectors:
                try:
                    tab = driver.find_element(By.XPATH, selector)
                    if tab.is_displayed():
                        tab.click()
                        logger.info("Clicked Reels tab")
                        return True
                except NoSuchElementException:
                    continue

            logger.debug("No Reels tab found (may be normal for some pages)")
            return False

        except Exception as exc:
            logger.debug(f"Tab click failed: {exc}")
            return False

    def scrape_popular_accounts(self, driver, category: str) -> List[Dict]:
        """Scrape from popular accounts (viral content guaranteed)."""
        popular_accounts = {
            "asmr": ["asmr", "satisfying", "oddlysatisfying"],
            "gaming": ["gaming", "playstation", "xbox"],
            "food": ["food", "tasty", "buzzfeedfood"],
            "fitness": ["fitness", "gymshark"],
            "comedy": ["funny", "9gag", "memezar"],
            "all": ["reels", "instagram", "creators"],
        }

        key = (category or "all").lower()
        accounts = popular_accounts.get(key, popular_accounts["all"])
        videos: List[Dict] = []
        unknown_views = 0

        for account in accounts:
            logger.info("Scraping @%s...", account)
            driver.get(f"https://www.instagram.com/{account}/")
            self._wait_page_ready(driver)
            try:
                current_url = driver.current_url or ""
            except Exception:
                current_url = ""
            if "/p/" in current_url or "/reel/" in current_url:
                driver.get(f"https://www.instagram.com/{account}/")
                self._wait_page_ready(driver)
                try:
                    current_url = driver.current_url or ""
                except Exception:
                    current_url = ""
                if "/p/" in current_url or "/reel/" in current_url:
                    logger.warning(
                        "Account %s post sayfasina saplandi, skip ediliyor: %s",
                        account,
                        current_url,
                    )
                    continue
            listing_url = driver.current_url or f"https://www.instagram.com/{account}/"
            self._wait_for_post_links(driver)

            # FIXED: Progressive scrolling for popular accounts
            logger.info(f"Progressive scrolling (max {self.max_scrolls} scrolls)...")
            all_links_raw_account = self._progressive_scroll(driver, self.max_scrolls)
            logger.info(f"@{account}: {len(all_links_raw_account)} total links after scrolling")

            # Split reels and posts
            reel_links = [u for u in all_links_raw_account if "/reel/" in u]
            post_links = [u for u in all_links_raw_account if "/p/" in u]

            if self.config.get("scraper", {}).get("only_reels", False):
                post_links = []

            all_links = reel_links + post_links
            logger.info(
                "@%s: %d reel / %d post link bulundu",
                account,
                len(reel_links),
                len(post_links),
            )
            if not all_links:
                self._log_link_debug(driver, f"account @{account}")

            for url in all_links[:30]:
                video_data = self._parse_reel_quick(driver, url, listing_url)
                if video_data is None:
                    logger.info("Skip (parse failed): %s", url)
                    continue
                if video_data['views'] == 0:
                    if "/reel/" in url or "/p/" in url:
                        unknown_views += 1
                        logger.info("Views parse 0 (unknown) kabul: %s", url)
                        videos.append(video_data)
                        continue
                    logger.info("Skip (views 0): %s", url)
                    continue
                if video_data['views'] >= self.scraper_min_views:
                    videos.append(video_data)
                else:
                    logger.info("Skip (views dusuk %s): %s", video_data['views'], url)
                if len(videos) >= 15:
                    break

            if len(videos) >= 15:
                break

        if unknown_views:
            logger.info("Popular accounts: unknown views accepted: %d", unknown_views)
        return videos

    def _progressive_scroll(self, driver, max_scrolls: int) -> List[str]:
        """Progressive scroll to load more content, return all collected links."""
        import random
        all_links = set()

        for scroll_iteration in range(max_scrolls):
            previous_count = len(all_links)

            # Scroll to bottom
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # Wait for new content with random delay (human-like)
            time.sleep(random.uniform(1.5, 3.0))

            # Collect current links
            current_links = self._collect_post_links(driver)
            all_links.update(current_links)

            new_count = len(all_links)

            # If no new links loaded, stop scrolling
            if new_count == previous_count:
                logger.info(f"No new posts after scroll {scroll_iteration + 1}/{max_scrolls}, stopping")
                break

            logger.debug(f"Scroll {scroll_iteration + 1}/{max_scrolls}: {new_count} total links (+{new_count - previous_count} new)")

        return list(all_links)

    def scrape_hashtags(self, driver, hashtags: List[str]) -> List[Dict]:
        """Scrape reels by hashtag (slow but works)."""
        videos: List[Dict] = []
        unknown_views = 0
        only_reels = bool(self.config.get("scraper", {}).get("only_reels", False))

        base_tags: List[str] = []
        seen_tags = set()
        for t in hashtags:
            if t not in seen_tags:
                base_tags.append(t)
                seen_tags.add(t)

        related_tags: List[str] = []
        related_seen = set()

        for tag in base_tags:
            logger.info("Scraping #%s...", tag)
            target_url = f"https://www.instagram.com/explore/tags/{tag}/"
            driver.get(target_url)
            self._wait_page_ready(driver)

            # DETECT REDIRECT (Instagram may redirect to search page)
            current_url = driver.current_url or ""

            # Flag: search sayfasında reels, /p/ URL'siyle listelenir (not /reel/)
            is_search_page = "/explore/search/" in current_url

            if "/explore/search/keyword/" in current_url or "/explore/search/" in current_url:
                logger.warning(f"#{tag} redirected to search page: {current_url}")
                logger.info("Adapting to search page DOM structure...")
                logger.info("NOTE: Search page lists reels as /p/ URLs — only_reels filter will be bypassed.")

                # Try clicking Reels tab if available
                self._click_reels_tab_if_available(driver)
                import random
                time.sleep(random.uniform(1.5, 2.5))

            elif "/explore/tags/" not in current_url:
                logger.error(f"#{tag} unexpected redirect: {current_url}")
                continue

            if not self._wait_for_post_links(driver):
                logger.warning("Hashtag #%s: post linkleri bulunamadi (timeout)", tag)

            # FIXED: Progressive scrolling using max_scrolls config
            logger.info(f"Progressive scrolling (max {self.max_scrolls} scrolls)...")
            all_links_raw = self._progressive_scroll(driver, self.max_scrolls)
            logger.info(f"Hashtag #{tag}: {len(all_links_raw)} total links after scrolling")

            listing_url = driver.current_url or f"https://www.instagram.com/explore/tags/{tag}/"

            # Related tags (max 5 per tag)
            tag_links = self._collect_tag_links(driver)
            collected = []
            for tag_url in tag_links:
                tag_name = self._extract_tag_from_url(tag_url)
                if not tag_name:
                    continue
                if tag_name in seen_tags or tag_name in related_seen:
                    continue
                collected.append(tag_name)
                related_seen.add(tag_name)
                if len(collected) >= 5:
                    break

            if collected:
                logger.info("Related tags for #%s: %s", tag, ", ".join(collected))
                related_tags.extend(collected)

            # Split reels and posts from collected links
            reel_links = [u for u in all_links_raw if "/reel/" in u]
            post_links = [u for u in all_links_raw if "/p/" in u]

            # Search sayfasında reels /p/ URL'siyle gösterilir — bypass only_reels
            if only_reels and not is_search_page:
                post_links = []

            all_links = reel_links + post_links
            logger.info(
                "Hashtag #%s: %d reel / %d post link bulundu (is_search_page=%s)",
                tag,
                len(reel_links),
                len(post_links),
                is_search_page,
            )
            if not all_links:
                self._log_link_debug(driver, f"hashtag #{tag}")

            for url in all_links[:30]:
                video_data = self._parse_reel_quick(driver, url, listing_url)
                if video_data is None:
                    logger.info("Skip (parse failed): %s", url)
                    continue
                if video_data['views'] == 0:
                    if "/reel/" in url or "/p/" in url:
                        unknown_views += 1
                        logger.info("Views parse 0 (unknown) kabul: %s", url)
                        videos.append(video_data)
                        continue
                    logger.info("Skip (views 0): %s", url)
                    continue
                if video_data['views'] >= self.scraper_min_views:
                    videos.append(video_data)
                    logger.info(
                        "Found: %s - %s views",
                        video_data['id'],
                        f"{video_data['views']:,}",
                    )
                else:
                    logger.info("Skip (views dusuk %s): %s", video_data['views'], url)
                if len(videos) >= 15:
                    break

            if len(videos) >= 15:
                break

        if len(videos) >= 15:
            if unknown_views:
                logger.info("Hashtags: unknown views accepted: %d", unknown_views)
            return videos

        for tag in related_tags:
            if len(videos) >= 15:
                break
            logger.info("Scraping related #%s...", tag)
            target_url = f"https://www.instagram.com/explore/tags/{tag}/"
            driver.get(target_url)
            self._wait_page_ready(driver)

            # DETECT REDIRECT for related tags too
            current_url = driver.current_url or ""

            # Flag: search sayfasında reels, /p/ URL'siyle listelenir (not /reel/)
            is_related_search_page = "/explore/search/" in current_url

            if "/explore/search/keyword/" in current_url or "/explore/search/" in current_url:
                logger.warning(f"Related #{tag} redirected to search page: {current_url}")
                self._click_reels_tab_if_available(driver)
                import random
                time.sleep(random.uniform(1.5, 2.5))

            elif "/explore/tags/" not in current_url:
                logger.error(f"Related #{tag} unexpected redirect: {current_url}")
                continue

            if not self._wait_for_post_links(driver):
                logger.warning("Hashtag #%s: post linkleri bulunamadi (timeout)", tag)

            # FIXED: Progressive scrolling for related tags too
            logger.info(f"Progressive scrolling (max {self.max_scrolls} scrolls)...")
            all_links_raw_related = self._progressive_scroll(driver, self.max_scrolls)
            logger.info(f"Related #{tag}: {len(all_links_raw_related)} total links after scrolling")

            listing_url = driver.current_url or f"https://www.instagram.com/explore/tags/{tag}/"

            # Split reels and posts
            reel_links = [u for u in all_links_raw_related if "/reel/" in u]
            post_links = [u for u in all_links_raw_related if "/p/" in u]

            # Search sayfasında reels /p/ URL'siyle gösterilir — bypass only_reels
            if only_reels and not is_related_search_page:
                post_links = []

            all_links = reel_links + post_links
            logger.info(
                "Related #%s: %d reel / %d post link bulundu (is_search_page=%s)",
                tag,
                len(reel_links),
                len(post_links),
                is_related_search_page,
            )
            if not all_links:
                self._log_link_debug(driver, f"hashtag #{tag}")

            for url in all_links[:30]:
                video_data = self._parse_reel_quick(driver, url, listing_url)
                if video_data is None:
                    logger.info("Skip (parse failed): %s", url)
                    continue
                if video_data['views'] == 0:
                    if "/reel/" in url or "/p/" in url:
                        unknown_views += 1
                        logger.info("Views parse 0 (unknown) kabul: %s", url)
                        videos.append(video_data)
                        continue
                    logger.info("Skip (views 0): %s", url)
                    continue
                if video_data['views'] >= self.scraper_min_views:
                    videos.append(video_data)
                    logger.info(
                        "Found: %s - %s views",
                        video_data['id'],
                        f"{video_data['views']:,}",
                    )
                else:
                    logger.info("Skip (views dusuk %s): %s", video_data['views'], url)
                if len(videos) >= 15:
                    break

        if unknown_views:
            logger.info("Hashtags: unknown views accepted: %d", unknown_views)
        return videos

    def scrape_with_instaloader(self, hashtags: List[str]) -> List[Dict]:
        """Use Instaloader library (faster, direct API)."""
        try:
            import instaloader
        except Exception as exc:  # noqa: BLE001
            logger.warning("Instaloader not available: %s", exc)
            return []

        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")
        if not username or not password:
            logger.warning("Instaloader login skipped (missing credentials)")
            return []

        L = instaloader.Instaloader()

        try:
            L.login(username, password)
        except Exception as exc:  # noqa: BLE001
            logger.error("Instaloader login failed: %s", exc)
            return []

        videos: List[Dict] = []

        for tag in hashtags:
            logger.info("Instaloader: #%s", tag)
            try:
                for post in instaloader.Hashtag.from_name(L.context, tag).get_posts():
                    if post.is_video and post.video_view_count >= self.scraper_min_views:
                        videos.append(
                            {
                                "id": f"insta_{post.shortcode}",
                                "platform": "instagram",
                                "url": f"https://www.instagram.com/reel/{post.shortcode}/",
                                "views": post.video_view_count,
                                "description": (post.caption[:100] if post.caption else ""),
                                "duration": getattr(post, 'video_duration', 45),
                            }
                        )
                        logger.info("Found: %s - %s views", post.shortcode, f"{post.video_view_count:,}")

                    if len(videos) >= 15:
                        break
            except Exception:  # noqa: BLE001
                continue

            if len(videos) >= 15:
                break

        return videos

    def scrape_instagram(self) -> List[Dict]:
        """Scrape viral reels from selected category."""
        # 1. Kategori sec
        hashtags = self._select_category()
        videos: List[Dict] = []

        use_instaloader = bool(self.config.get('scraper', {}).get('use_instaloader', False))
        if use_instaloader:
            try:
                logger.info("Trying Instaloader...")
                videos = self.scrape_with_instaloader(hashtags)
                if len(videos) >= 10:
                    logger.info("Instaloader success: %d videos", len(videos))
                    return videos[:15]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Instaloader failed: %s", exc)
        else:
            logger.info("Instaloader disabled, using Selenium")

        # 2. Selenium fallback (with driver retry)
        from selenium.common.exceptions import InvalidSessionIdException, WebDriverException

        for attempt in range(2):
            driver = None
            try:
                driver = self._setup_driver()
                if not self._check_login(driver):
                    logger.error("Login failed. Aborting scraping.")
                    return []

                logger.info("Trying hashtag scraping...")
                videos = self.scrape_hashtags(driver, hashtags)
                if len(videos) >= 10:
                    return videos[:15]

                logger.info("Trying popular accounts...")
                category_key = hashtags[0] if hashtags else "all"
                videos = self.scrape_popular_accounts(driver, category_key)
                return videos[:15]

            except (InvalidSessionIdException, WebDriverException) as exc:
                logger.error("WebDriver error: %s", exc)
                if attempt == 0:
                    logger.info("Recreating WebDriver and retrying once...")
                    continue
                return []
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected scraping error: %s", exc)
                return []
            finally:
                self._safe_quit(driver)

        return []

    def scrape_tiktok(self) -> List[Dict]:
        """TikTok scraping placeholder."""
        logger.warning("TikTok scraping not implemented yet (next version)")
        return []

    def scrape_facebook(self) -> List[Dict]:
        """Facebook scraping placeholder."""
        logger.warning("Facebook scraping not implemented yet (next version)")
        return []

    def scrape_all(self) -> List[Dict]:
        """Scrape all platforms and combine."""
        all_videos = []

        if 'instagram' in self.config.get('scraping', {}).get('platforms', []):
            all_videos.extend(self.scrape_instagram())

        if 'tiktok' in self.config.get('scraping', {}).get('platforms', []):
            all_videos.extend(self.scrape_tiktok())

        if 'facebook' in self.config.get('scraping', {}).get('platforms', []):
            all_videos.extend(self.scrape_facebook())

        logger.info("Total videos scraped: %d", len(all_videos))
        return all_videos

    def display_videos(self, videos: List[Dict]) -> None:
        """Display videos in terminal."""
        if not videos:
            print("\nNo videos found!")
            return

        print("\n" + "=" * 80)
        print(" VIRAL VIDEOS (1M+ views)")
        print("=" * 80)

        for idx, video in enumerate(videos, start=1):
            views_formatted = f"{video['views']:,}".replace(',', '.')
            duration = video['duration']
            platform = video['platform'].upper()

            print(f"\n[{idx}] {platform} - {views_formatted} views ({duration}s)")
            print(f"    {video['description']}")
            print(f"    {video['url']}")

        print("\n" + "=" * 80)

    def user_select(self, videos: List[Dict]) -> List[Dict]:
        """Ask user to select videos by index."""
        if not videos:
            logger.error("No videos to select from")
            return []

        print("\nWhich videos do you want to process?")
        print("Example: 1,3,5  or  1-3  or  all")

        while True:
            try:
                user_input = input("\nSelection: ").strip().lower()

                if user_input == "all":
                    logger.info("User selected all videos")
                    return videos

                if '-' in user_input:
                    start, end = map(int, user_input.split('-'))
                    indices = list(range(start, end + 1))
                else:
                    indices = [int(x.strip()) for x in user_input.split(',')]

                if any(i < 1 or i > len(videos) for i in indices):
                    print(f"Invalid number! (1-{len(videos)} only)")
                    continue

                selected = [videos[i - 1] for i in indices]
                logger.info("User selected %d videos: %s", len(selected), indices)
                return selected

            except ValueError:
                print("Invalid format! Example: 1,3,5")
            except KeyboardInterrupt:
                print("\n\nOperation cancelled")
                return []


if __name__ == "__main__":
    import yaml

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # .env test
    _load_env()
    print("=== .env TEST ===")
    user = os.getenv("INSTAGRAM_USERNAME")
    pwd = os.getenv("INSTAGRAM_PASSWORD")

    if user and pwd:
        print(f"Username: {user}")
        print(f"Password: {'*' * len(pwd)}")
    else:
        print(".env'de credentials yok!")
        print("\n.env dosyasi olustur:")
        print("INSTAGRAM_USERNAME=your_username")
        print("INSTAGRAM_PASSWORD=your_password")

    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    scraper = ViralScraper(config)

    print("\nTesting view count parser:")
    test_cases = ["1.2M views", "500K views", "3,200,000 views", "15.5M"]
    for test in test_cases:
        parsed = scraper._parse_view_text(test)
        print(f"  {test} -> {parsed:,}")

    videos = scraper.scrape_instagram()
    scraper.display_videos(videos)

    selected = scraper.user_select(videos)

    if selected:
        print(f"\nSelected videos ({len(selected)}):")
        for video in selected:
            print(f"   - {video['id']}: {video['description']}")

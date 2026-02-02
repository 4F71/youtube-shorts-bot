#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Viral Scraper Module
Instagram, TikTok, Facebook'tan 1M+ görüntülenen videoları scrape eder.

Bu versiyon: Dummy data ile çalışır (test amaçlı)
Sonraki versiyon: Gerçek Selenium scraping eklenecek
"""

import re
import logging
import random
from typing import List, Dict, Optional
from pathlib import Path

# Selenium (sonraki versiyonda aktif edilecek)
# from selenium import webdriver
# from selenium.webdriver.chrome.options import Options
# from webdriver_manager.chrome import ChromeDriverManager

logger = logging.getLogger(__name__)


class ViralScraper:
    """
    Instagram, TikTok, Facebook'tan viral videoları scrape eden sınıf.
    
    Attributes:
        config (dict): Config.yaml'dan yüklenen ayarlar
        min_views (int): Minimum görüntüleme sayısı
        max_videos (int): Platform başına maksimum video sayısı
        rate_limit (int): İstekler arası bekleme süresi (saniye)
    """
    
    def __init__(self, config: dict):
        """
        Args:
            config: Config dictionary (yaml'dan yüklenen)
        """
        self.config = config
        self.min_views = config['scraping']['min_views']
        self.max_videos = config['scraping']['max_videos_per_platform']
        self.rate_limit = config['scraping']['rate_limit_seconds']
        self.user_agents = config['scraping']['user_agents']
        
        logger.info("ViralScraper initialized")
        logger.debug(f"Min views: {self.min_views}, Max videos/platform: {self.max_videos}")
    
    def _init_driver(self) -> None:
        """
        Selenium WebDriver'ı başlatır (headless + random user-agent).
        
        NOT: Şimdilik disabled, gerçek scraping için aktif edilecek.
        """
        # TODO: Gerçek Selenium driver setup
        # options = Options()
        # options.add_argument("--headless")
        # options.add_argument("--no-sandbox")
        # options.add_argument("--disable-dev-shm-usage")
        # options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        # self.driver = webdriver.Chrome(
        #     service=Service(ChromeDriverManager().install()),
        #     options=options
        # )
        pass
    
    def _parse_view_count(self, text: str) -> int:
        """
        View count string'ini integer'a çevirir.
        
        Örnekler:
            "1.2M views" -> 1200000
            "500K views" -> 500000
            "3,200,000 views" -> 3200000
        
        Args:
            text: View count metni
        
        Returns:
            Integer view count
        """
        text = text.lower().replace(',', '').replace(' ', '')
        
        # Regex pattern: sayı + (opsiyonel K/M)
        match = re.search(r'([\d.]+)([km])?', text)
        
        if not match:
            logger.warning(f"Could not parse view count: {text}")
            return 0
        
        number = float(match.group(1))
        multiplier = match.group(2)
        
        if multiplier == 'k':
            return int(number * 1_000)
        elif multiplier == 'm':
            return int(number * 1_000_000)
        else:
            return int(number)
    
    def scrape_instagram(self) -> List[Dict]:
        """
        Instagram Reels'ten viral videoları scrape eder.
        
        Şu an: Dummy data döndürür
        Gelecek: Gerçek Selenium scraping
        
        Returns:
            List of video dicts:
            {
                "id": "insta_001",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/ABC123/",
                "views": 2_300_000,
                "description": "Amazing soap cutting ASMR",
                "duration": 45
            }
        """
        logger.info("Scraping Instagram Reels...")
        
        # DUMMY DATA (Test için)
        dummy_videos = [
            {
                "id": "insta_001",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/C1a2b3c4d5/",
                "views": 2_300_000,
                "description": "Amazing soap cutting ASMR - Satisfying sounds",
                "duration": 45
            },
            {
                "id": "insta_002",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/D6e7f8g9h0/",
                "views": 5_100_000,
                "description": "Gold panning discovery - Found real gold!",
                "duration": 52
            },
            {
                "id": "insta_003",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/E1i2j3k4l5/",
                "views": 1_800_000,
                "description": "Oddly satisfying woodworking",
                "duration": 38
            },
            {
                "id": "insta_004",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/F6m7n8o9p0/",
                "views": 3_400_000,
                "description": "Extreme food challenge - 100 layers!",
                "duration": 58
            },
            {
                "id": "insta_005",
                "platform": "instagram",
                "url": "https://www.instagram.com/reel/G1q2r3s4t5/",
                "views": 4_200_000,
                "description": "Nature restoration time-lapse",
                "duration": 41
            },
        ]
        
        logger.info(f"Found {len(dummy_videos)} Instagram videos (dummy data)")
        return dummy_videos
    
    def scrape_tiktok(self) -> List[Dict]:
        """
        TikTok'tan trending videoları scrape eder.
        
        Şu an: NotImplemented (sonraki versiyon)
        """
        logger.warning("TikTok scraping not implemented yet (next version)")
        return []
    
    def scrape_facebook(self) -> List[Dict]:
        """
        Facebook Watch'tan viral videoları scrape eder.
        
        Şu an: NotImplemented (sonraki versiyon)
        """
        logger.warning("Facebook scraping not implemented yet (next version)")
        return []
    
    def scrape_all(self) -> List[Dict]:
        """
        Tüm platformlardan videoları scrape edip birleştirir.
        
        Returns:
            Combined list of all videos
        """
        all_videos = []
        
        # Instagram
        if 'instagram' in self.config['scraping']['platforms']:
            all_videos.extend(self.scrape_instagram())
        
        # TikTok (disabled for now)
        if 'tiktok' in self.config['scraping']['platforms']:
            all_videos.extend(self.scrape_tiktok())
        
        # Facebook (disabled for now)
        if 'facebook' in self.config['scraping']['platforms']:
            all_videos.extend(self.scrape_facebook())
        
        logger.info(f"Total videos scraped: {len(all_videos)}")
        return all_videos
    
    def display_videos(self, videos: List[Dict]) -> None:
        """
        Videoları terminal'de güzel formatlı listeler.
        
        Args:
            videos: Video dictionary listesi
        """
        if not videos:
            print("\n❌ No videos found!")
            return
        
        print("\n" + "="*80)
        print(" 🎥 VİRAL VIDEOLAR (1M+ görüntülenme)")
        print("="*80)
        
        for idx, video in enumerate(videos, start=1):
            views_formatted = f"{video['views']:,}".replace(',', '.')
            duration = video['duration']
            platform = video['platform'].upper()
            
            print(f"\n[{idx}] {platform} - {views_formatted} görüntülenme ({duration}s)")
            print(f"    📝 {video['description']}")
            print(f"    🔗 {video['url']}")
        
        print("\n" + "="*80)
    
    def user_select(self, videos: List[Dict]) -> List[Dict]:
        """
        Kullanıcıdan video seçimi alır.
        
        Args:
            videos: Tüm videoların listesi
        
        Returns:
            Seçilen videoların listesi
        """
        if not videos:
            logger.error("No videos to select from")
            return []
        
        print("\n📌 Hangi videoları işlemek istersiniz?")
        print("   Örnek: 1,3,5  veya  1-3  veya  all")
        
        while True:
            try:
                user_input = input("\nSeçim: ").strip().lower()
                
                # "all" seçeneği
                if user_input == "all":
                    logger.info("User selected all videos")
                    return videos
                
                # Range seçimi (örn: 1-3)
                if '-' in user_input:
                    start, end = map(int, user_input.split('-'))
                    indices = list(range(start, end + 1))
                else:
                    # Comma-separated seçim (örn: 1,3,5)
                    indices = [int(x.strip()) for x in user_input.split(',')]
                
                # Validation
                if any(i < 1 or i > len(videos) for i in indices):
                    print(f"❌ Geçersiz numara! (1-{len(videos)} arası olmalı)")
                    continue
                
                # Seçilen videoları döndür
                selected = [videos[i-1] for i in indices]
                logger.info(f"User selected {len(selected)} videos: {indices}")
                
                return selected
                
            except ValueError:
                print("❌ Geçersiz format! Örnek: 1,3,5")
            except KeyboardInterrupt:
                print("\n\n❌ İşlem iptal edildi")
                return []


# ═══════════════════════════════════════════════════════════
# STANDALONE TEST
# ═══════════════════════════════════════════════════════════
if __name__ == "__main__":
    import yaml
    from pathlib import Path
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    
    # Config yükle
    config_path = Path(__file__).parent.parent / "config" / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Test scraper
    scraper = ViralScraper(config)
    
    # Test view count parser
    print("\n🧪 Testing view count parser:")
    test_cases = ["1.2M views", "500K views", "3,200,000 views", "15.5M"]
    for test in test_cases:
        parsed = scraper._parse_view_count(test)
        print(f"  {test} -> {parsed:,}")
    
    # Test Instagram scraping
    videos = scraper.scrape_instagram()
    scraper.display_videos(videos)
    
    # Test user selection
    selected = scraper.user_select(videos)
    
    if selected:
        print(f"\n✅ Seçilen videolar ({len(selected)}):")
        for video in selected:
            print(f"   - {video['id']}: {video['description']}")

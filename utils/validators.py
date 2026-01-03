import re
from typing import Optional, Tuple
from models import Platform

class Validator:
    @staticmethod
    def validate_usdt_wallet(wallet: str) -> bool:
        """Validate USDT ERC20 wallet address"""
        return bool(re.match(r'^0x[a-fA-F0-9]{40}$', wallet))
    
    @staticmethod
    def validate_profile_url(platform: str, url: str) -> Tuple[bool, Optional[str]]:
        """Validate social media profile URL"""
        url = url.lower().strip()
        
        if platform == Platform.INSTAGRAM.value:
            if 'instagram.com' not in url:
                return False, "Invalid Instagram URL"
        elif platform == Platform.TIKTOK.value:
            if 'tiktok.com' not in url:
                return False, "Invalid TikTok URL"
        elif platform == Platform.YOUTUBE.value:
            if not ('youtube.com' in url or 'youtu.be' in url):
                return False, "Invalid YouTube URL"
        else:
            return False, "Invalid platform"
            
        return True, None
    
    @staticmethod
    def validate_video_url(platform: str, url: str) -> Tuple[bool, Optional[str]]:
        """Validate video URL"""
        url = url.lower().strip()
        
        if platform == Platform.INSTAGRAM.value:
            if not ('instagram.com/reel/' in url or 'instagram.com/p/' in url):
                return False, "Invalid Instagram video URL"
        elif platform == Platform.TIKTOK.value:
            if not ('tiktok.com/@' in url and '/video/' in url):
                return False, "Invalid TikTok video URL"
        elif platform == Platform.YOUTUBE.value:
            if not ('youtube.com/watch?v=' in url or 'youtu.be/' in url):
                return False, "Invalid YouTube video URL"
        else:
            return False, "Invalid platform"
            
        return True, None

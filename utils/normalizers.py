import re
from typing import Optional
from models import Platform

class Normalizer:
    @staticmethod
    def normalize_profile_id(platform: str, url: str) -> Optional[str]:
        """Normalize social media profile URL to unique ID"""
        url = url.lower().strip()
        
        if platform == Platform.INSTAGRAM.value:
            match = re.search(r'instagram\.com/([^/?]+)', url)
            return f"ig:{match.group(1)}" if match else None
        elif platform == Platform.TIKTOK.value:
            match = re.search(r'tiktok\.com/@([^/?]+)', url)
            return f"tt:{match.group(1)}" if match else None
        elif platform == Platform.YOUTUBE.value:
            match = re.search(r'(?:youtube\.com/(?:c/|channel/|@)|youtu\.be/)([^/?]+)', url)
            return f"yt:{match.group(1)}" if match else None
        
        return None
    
    @staticmethod
    def normalize_video_id(platform: str, url: str) -> Optional[str]:
        """Normalize video URL to unique ID"""
        url = url.lower().strip()
        
        if platform == Platform.INSTAGRAM.value:
            match = re.search(r'instagram\.com/(?:reel|p)/([^/?]+)', url)
            return f"ig_video:{match.group(1)}" if match else None
        elif platform == Platform.TIKTOK.value:
            match = re.search(r'tiktok\.com/@[^/]+/video/(\d+)', url)
            return f"tt_video:{match.group(1)}" if match else None
        elif platform == Platform.YOUTUBE.value:
            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([^&?]+)', url)
            return f"yt_video:{match.group(1)}" if match else None
        
        return None

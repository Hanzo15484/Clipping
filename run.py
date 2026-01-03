#!/usr/bin/env python3
"""
Clipping Bot - Content Clipping & Promotion Discord Bot
Entry point script
"""

import asyncio
from main import main

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════╗
    ║     Clipping Bot - Content Clipping System         ║
    ║           Starting up...                     ║
    ╚══════════════════════════════════════════════╝
    """)
    
    asyncio.run(main())

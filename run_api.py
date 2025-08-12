#!/usr/bin/env python3
"""
Script para executar a Instagram Collection API
"""

import sys
import os


# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if hasattr(sys, '__stdout__'):
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__

from app.api.main import app
from app.config import Settings
import uvicorn

if __name__ == "__main__":
    settings = Settings()

    print("🚀 Instagram Collection API")
    print("=" * 50)
    print(f"🌐 Host: {settings.api_host}")
    print(f"🔌 Port: {settings.api_port}")
    print(f"📁 Sessions: {settings.session_dir}")
    print(f"📊 Max accounts: {settings.max_accounts}")
    print("=" * 50)

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        reload=False,  # ✅ Corrige o erro de logging
        log_level="info"
    )

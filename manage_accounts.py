#!/usr/bin/env python3
"""
Script para gerenciar contas do pool
"""

import sys
import os

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scripts.account_manager import AccountManager
import asyncio

if __name__ == "__main__":
    manager = AccountManager()
    asyncio.run(manager.run())
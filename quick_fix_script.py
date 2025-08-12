#!/usr/bin/env python3
"""
Script de correção rápida para copiar arquivos em falta
"""

import os
import shutil
from pathlib import Path

def copy_missing_files():
    """Copia arquivos em falta para estrutura correta"""
    
    project_root = Path.cwd()
    
    # Mapeamento de arquivos
    file_mappings = [
        ("config.py", "app/config.py"),
        ("models.py", "app/models.py"),
        ("account_pool.py", "app/core/account_pool.py"),
        ("logging_config.py", "app/utils/logging_config.py"),
        ("media_collector.py", "app/core/media_collector.py"),
        ("collection_service.py", "app/core/collection_service.py"),
    ]
    
    print("🔧 Verificando e copiando arquivos...")
    
    for source, target in file_mappings:
        source_path = project_root / source
        target_path = project_root / target
        
        # Criar diretório pai se não existir
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        if source_path.exists() and not target_path.exists():
            shutil.copy2(source_path, target_path)
            print(f"✅ Copiado: {source} → {target}")
        elif target_path.exists():
            print(f"✅ Já existe: {target}")
        else:
            print(f"⚠️ Não encontrado: {source}")
    
    # Criar __init__.py em pacotes
    init_dirs = ["app", "app/core", "app/utils", "app/api", "scripts"]
    
    for dir_name in init_dirs:
        init_path = project_root / dir_name / "__init__.py"
        init_path.parent.mkdir(parents=True, exist_ok=True)
        if not init_path.exists():
            init_path.write_text("# -*- coding: utf-8 -*-\n")
            print(f"✅ Criado: {dir_name}/__init__.py")

if __name__ == "__main__":
    copy_missing_files()
    print("\n🎯 Correção concluída! Agora tente:")
    print("cd scripts")
    print("python account_manager.py")
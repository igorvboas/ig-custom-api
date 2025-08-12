#!/usr/bin/env python3
# scripts/reset_accounts.py
"""
Script para resetar cooldown das contas
"""

import json
from pathlib import Path

def reset_accounts():
    """Reset das contas para remover cooldown"""
    
    project_root = Path(__file__).parent.parent
    pool_file = project_root / "data" / "account_pool.json"
    
    if not pool_file.exists():
        print("❌ Arquivo account_pool.json não encontrado!")
        return
    
    # Ler arquivo
    with open(pool_file, 'r') as f:
        data = json.load(f)
    
    print(f"📊 Encontradas {len(data)} contas")
    
    # Reset das contas
    for acc in data:
        old_status = acc.get('status', 'unknown')
        old_ops = acc.get('operations_today', 0)
        
        acc['operations_today'] = 0
        acc['last_used'] = None
        acc['status'] = 'active'
        
        print(f"✅ {acc['username']}: {old_status} -> active, ops: {old_ops} -> 0")
    
    # Salvar
    with open(pool_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("🎉 Todas as contas foram resetadas!")
    print("🚀 Agora teste a API!")

if __name__ == "__main__":
    reset_accounts()
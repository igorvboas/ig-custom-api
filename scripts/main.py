# main.py (para testar o pool)
"""
Script principal para testar o AccountPool
"""
import asyncio
import time
from config import Settings
from logging_config import setup_logging
from account_pool import AccountPool

async def test_pool():
    """
    Função de teste do AccountPool
    """
    # Carregar configurações
    settings = Settings()
    setup_logging(settings)
    
    # Criar pool
    pool = AccountPool(settings)
    
    # Exibir status inicial
    print("📊 Status inicial do pool:")
    print(pool.get_pool_status())
    
    # Adicionar contas de teste (substitua pelas suas)
    test_accounts = [
        ("conta1", "senha1", None),
        ("conta2", "senha2", None),
        # Adicione suas contas aqui
    ]
    
    print("\n🔧 Adicionando contas de teste...")
    for username, password, proxy in test_accounts:
        result = pool.add_account(username, password, proxy)
        print(f"Conta {username}: {'✅' if result else '❌'}")
    
    # Testar obtenção de conta
    print("\n🎯 Testando obtenção de conta...")
    account = pool.get_available_account()
    if account:
        print(f"✅ Conta obtida: {account.username}")
        
        # Testar cliente
        client = pool.get_client(account)
        if client:
            print("✅ Cliente obtido com sucesso")
            
            # Marcar como usada
            pool.mark_account_used(account, success=True)
            print("✅ Conta marcada como usada")
        else:
            print("❌ Erro ao obter cliente")
    else:
        print("❌ Nenhuma conta disponível")
    
    # Health check
    print("\n🏥 Executando health check...")
    pool.health_check()
    
    # Status final
    print("\n📊 Status final do pool:")
    print(pool.get_pool_status())

if __name__ == "__main__":
    asyncio.run(test_pool())
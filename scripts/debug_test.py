#!/usr/bin/env python3
# scripts/debug_test.py
"""
Teste com debug detalhado
"""

import asyncio
import sys
from pathlib import Path

# Path absoluto
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print("🧪 DEBUG TEST - INÍCIO")
print("="*50)
print(f"📁 Project root: {project_root}")
print(f"📍 Current dir: {Path.cwd()}")

def test_imports():
    """Testa todos os imports"""
    try:
        print("\n1️⃣ Testando imports...")
        
        from app.config import Settings
        print("✅ Settings importado")
        
        settings = Settings()
        print("✅ Settings instanciado")
        print(f"📊 Session dir: {settings.session_dir}")
        print(f"📊 Downloads dir: {settings.downloads_dir}")
        
        from app.utils.logging_config import setup_logging
        print("✅ logging_config importado")
        
        # Configurar logging sem output verbose
        import logging
        logging.getLogger('instagrapi').setLevel(logging.CRITICAL)
        setup_logging(settings)
        print("✅ Logging configurado")
        
        from app.core.account_pool import AccountPool
        print("✅ AccountPool importado")
        
        pool = AccountPool(settings)
        print("✅ AccountPool instanciado")
        
        status = pool.get_pool_status()
        print(f"📊 Pool status: {status}")
        
        if status['total_accounts'] == 0:
            print("❌ PROBLEMA: Nenhuma conta no pool!")
            print("💡 Execute primeiro: python manage_accounts.py")
            return False
        
        from app.core.media_collector import MediaCollector
        print("✅ MediaCollector importado")
        
        collector = MediaCollector(pool, settings)
        print(f"✅ MediaCollector instanciado - temp_dir: {collector.temp_dir}")
        
        from app.core.collection_service import CollectionService
        print("✅ CollectionService importado")
        
        service = CollectionService(settings)
        print("✅ CollectionService instanciado")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no import: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_collection():
    """Teste de coleta"""
    print("\n2️⃣ Testando coleta...")
    
    try:
        from app.core.collection_service import CollectionService
        from app.config import Settings
        
        settings = Settings()
        service = CollectionService(settings)
        
        # Status do pool
        status = service.get_pool_status()
        print(f"📊 Contas disponíveis: {status['available_accounts']}")
        
        if status['available_accounts'] == 0:
            print("❌ Nenhuma conta disponível!")
            return
        
        # Input sem timeout
        print("\n👤 Digite um username para testar:")
        username = input("Username (sem @): ").strip()
        
        if not username:
            print("❌ Username vazio!")
            return
        
        print(f"\n🔄 Iniciando coleta para @{username}...")
        
        # Fazer coleta
        result = await service.collect_user_content(
            username=username,
            include_stories=True,
            include_feed=True,
            max_feed_posts=2
        )
        
        print(f"\n📊 RESULTADO DETALHADO:")
        print(f"✅ Sucesso: {result['success']}")
        print(f"📅 Timestamp: {result['timestamp']}")
        print(f"🏦 Conta usada: {result.get('account_used', 'N/A')}")
        
        if result['success']:
            print(f"\n📈 ESTATÍSTICAS:")
            stats = result.get('statistics', {})
            print(f"   📁 Total files: {stats.get('total_files', 0)}")
            print(f"   📊 Total size: {stats.get('total_size_mb', 0)}MB")
            print(f"   📱 Stories: {stats.get('stories_count', 0)}")
            print(f"   📋 Posts: {stats.get('feed_posts_count', 0)}")
            
            # Detalhes dos arquivos
            stories = result.get('data', {}).get('stories', [])
            posts = result.get('data', {}).get('feed_posts', [])
            
            if stories:
                print(f"\n📱 STORIES ENCONTRADOS:")
                for i, story in enumerate(stories, 1):
                    print(f"   {i}. {story.get('filename', 'N/A')} ({story.get('size_bytes', 0)} bytes)")
            
            if posts:
                print(f"\n📋 POSTS ENCONTRADOS:")
                for i, post in enumerate(posts, 1):
                    print(f"   {i}. {post.get('filename', 'N/A')} ({post.get('size_bytes', 0)} bytes)")
        
        else:
            print(f"❌ Erro na coleta: {result.get('error', 'Erro desconhecido')}")
        
        service.cleanup()
        
    except Exception as e:
        print(f"❌ Erro na coleta: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Função principal"""
    print("🚀 Iniciando teste completo...")
    
    # Teste de imports
    if not test_imports():
        print("\n❌ Falha nos imports - não prosseguindo")
        return
    
    print("\n✅ Todos os imports OK!")
    
    # Teste de coleta
    await test_collection()
    
    print("\n🏁 Teste concluído!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Teste interrompido")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
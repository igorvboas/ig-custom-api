#!/usr/bin/env python3
# scripts/test_collector.py
"""
Script de teste para o MediaCollector
"""

import asyncio
import sys
import os
from pathlib import Path

# Adicionar raiz do projeto ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import Settings
from app.utils.logging_config import setup_logging
from app.core.collection_service import CollectionService


async def test_collection():
    """
    Testa o sistema de coleta
    """
    print("🧪 TESTE DO MEDIACOLLECTOR")
    print("="*50)
    
    # Configurar
    settings = Settings()
    setup_logging(settings)
    
    service = CollectionService(settings)
    
    # Verificar pool
    pool_status = service.get_pool_status()
    print(f"📊 Pool status: {pool_status['available_accounts']} contas disponíveis de {pool_status['total_accounts']} total")
    
    if pool_status['available_accounts'] == 0:
        print("❌ Nenhuma conta disponível! Adicione contas primeiro:")
        print("   python manage_accounts.py")
        return
    
    # Testar coleta
    username = input("\n👤 Digite o username para testar (sem @): ").strip()
    if not username:
        print("❌ Username é obrigatório!")
        return
    
    print(f"\n🔄 Testando coleta para @{username}...")
    print("💡 Coletando poucos itens para teste rápido")
    
    try:
        result = await service.collect_user_content(
            username=username,
            include_stories=True,
            include_feed=True,
            max_feed_posts=3  # Poucos posts para teste
        )
        
        print(f"\n📊 RESULTADO:")
        print("="*40)
        print(f"✅ Sucesso: {result['success']}")
        
        if result['success']:
            stats = result['statistics']
            print(f"📁 Total de arquivos: {stats['total_files']}")
            print(f"📊 Tamanho total: {stats['total_size_mb']}MB")
            print(f"📱 Stories: {stats['stories_count']}")
            print(f"📋 Feed posts: {stats['feed_posts_count']}")
            print(f"🏦 Conta usada: {result['account_used']}")
            
            # Mostrar detalhes dos arquivos
            if result['data']['stories']:
                print(f"\n📱 DETALHES DOS STORIES:")
                for i, story in enumerate(result['data']['stories'][:5], 1):  # Mostrar só 5
                    print(f"   {i}. {story['filename']} ({story['size_bytes']} bytes)")
                    print(f"      Tipo: {story['type']} | ID: {story['id']}")
                    if len(result['data']['stories']) > 5:
                        print(f"   ... e mais {len(result['data']['stories']) - 5} stories")
                        break
            
            if result['data']['feed_posts']:
                print(f"\n📋 DETALHES DOS POSTS:")
                for i, post in enumerate(result['data']['feed_posts'][:5], 1):  # Mostrar só 5
                    print(f"   {i}. {post['filename']} ({post['size_bytes']} bytes)")
                    print(f"      Tipo: {post['type']} | ID: {post['id']}")
                    # Mostrar metadados interessantes
                    metadata = post.get('metadata', {})
                    if metadata.get('like_count'):
                        print(f"      Likes: {metadata['like_count']} | Comments: {metadata.get('comment_count', 0)}")
                    if len(result['data']['feed_posts']) > 5:
                        print(f"   ... e mais {len(result['data']['feed_posts']) - 5} posts")
                        break
            
            # Teste de formato dos dados binários
            if result['data']['stories'] or result['data']['feed_posts']:
                print(f"\n🔍 TESTE DE DADOS BINÁRIOS:")
                
                # Testar primeiro arquivo encontrado
                test_file = None
                if result['data']['stories']:
                    test_file = result['data']['stories'][0]
                elif result['data']['feed_posts']:
                    test_file = result['data']['feed_posts'][0]
                
                if test_file:
                    binary_data = test_file['binary_data']
                    print(f"   Arquivo: {test_file['filename']}")
                    print(f"   Tipo de dados: {type(binary_data)}")
                    print(f"   Tamanho: {len(binary_data)} bytes")
                    print(f"   Primeiros 10 bytes: {binary_data[:10]}")
                    
                    # Verificar se é realmente binário
                    if isinstance(binary_data, bytes):
                        print("   ✅ Dados binários válidos!")
                    else:
                        print("   ❌ Dados não são binários!")
        
        else:
            print(f"❌ Erro: {result.get('error', 'Erro desconhecido')}")
            
            # Sugestões baseadas no tipo de erro
            error_msg = result.get('error', '').lower()
            if 'privado' in error_msg:
                print("💡 Sugestão: Tente um perfil público")
            elif 'não encontrado' in error_msg:
                print("💡 Sugestão: Verifique se o username está correto")
            elif 'rate limit' in error_msg:
                print("💡 Sugestão: Aguarde alguns minutos e tente novamente")
            elif 'nenhuma conta' in error_msg:
                print("💡 Sugestão: Adicione mais contas ou aguarde cooldown")
    
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        print("💡 Verifique os logs para mais detalhes")
    
    finally:
        # Limpeza
        service.cleanup()
        print(f"\n🧹 Limpeza concluída")


async def test_multiple_users():
    """
    Testa coleta de múltiplos usuários
    """
    print("🧪 TESTE MÚLTIPLOS USUÁRIOS")
    print("="*50)
    
    settings = Settings()
    setup_logging(settings)
    service = CollectionService(settings)
    
    # Lista de usuários para teste
    test_users = []
    print("Digite usuários para testar (um por linha, 'fim' para terminar):")
    
    while True:
        user = input("Username: ").strip()
        if user.lower() == 'fim' or not user:
            break
        test_users.append(user)
    
    if not test_users:
        print("❌ Nenhum usuário para testar")
        return
    
    print(f"\n🔄 Testando {len(test_users)} usuários...")
    
    results = []
    for i, username in enumerate(test_users, 1):
        print(f"\n[{i}/{len(test_users)}] Processando @{username}...")
        
        try:
            result = await service.collect_user_content(
                username=username,
                include_stories=True,
                include_feed=True,
                max_feed_posts=2  # Poucos para teste rápido
            )
            
            results.append({
                'username': username,
                'success': result['success'],
                'files': result.get('statistics', {}).get('total_files', 0),
                'size_mb': result.get('statistics', {}).get('total_size_mb', 0),
                'error': result.get('error')
            })
            
            if result['success']:
                stats = result['statistics']
                print(f"   ✅ {stats['total_files']} arquivos ({stats['total_size_mb']}MB)")
            else:
                print(f"   ❌ {result.get('error', 'Erro')}")
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            results.append({
                'username': username,
                'success': False,
                'files': 0,
                'size_mb': 0,
                'error': str(e)
            })
        
        # Delay entre usuários
        if i < len(test_users):
            print("   ⏱️ Aguardando 3 segundos...")
            await asyncio.sleep(3)
    
    # Resumo final
    print(f"\n📊 RESUMO FINAL:")
    print("="*50)
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    print(f"✅ Sucessos: {len(successful)}")
    print(f"❌ Falhas: {len(failed)}")
    
    if successful:
        total_files = sum(r['files'] for r in successful)
        total_size = sum(r['size_mb'] for r in successful)
        print(f"📁 Total de arquivos coletados: {total_files}")
        print(f"📊 Total de dados: {total_size:.2f}MB")
    
    if failed:
        print(f"\n❌ Usuários com falha:")
        for r in failed:
            print(f"   @{r['username']}: {r['error']}")
    
    service.cleanup()


def show_menu():
    """Mostra menu de opções de teste"""
    print("\n🧪 MENU DE TESTES DO MEDIACOLLECTOR")
    print("="*50)
    print("1. 🎯 Teste único usuário")
    print("2. 👥 Teste múltiplos usuários") 
    print("3. 📊 Status do pool")
    print("4. 🚪 Sair")
    print("="*50)


async def main():
    """Função principal"""
    print("🚀 TESTADOR DO MEDIACOLLECTOR")
    print("Sistema de teste para coleta de mídias Instagram")
    
    while True:
        try:
            show_menu()
            choice = input("\n👉 Escolha uma opção: ").strip()
            
            if choice == '1':
                await test_collection()
            elif choice == '2':
                await test_multiple_users()
            elif choice == '3':
                # Mostrar status do pool
                settings = Settings()
                setup_logging(settings)
                service = CollectionService(settings)
                status = service.get_pool_status()
                
                print(f"\n📊 STATUS DO POOL:")
                print(f"Total de contas: {status['total_accounts']}")
                print(f"Contas disponíveis: {status['available_accounts']}")
                print(f"Score médio: {status['average_health_score']}")
                print(f"Operações hoje: {status['total_operations_today']}")
                
            elif choice == '4':
                print("\n👋 Saindo...")
                break
            else:
                print("❌ Opção inválida!")
            
            if choice != '4':
                input("\n⏸️ Pressione Enter para continuar...")
                
        except KeyboardInterrupt:
            print("\n\n👋 Saindo...")
            break
        except Exception as e:
            print(f"\n❌ Erro inesperado: {e}")
            input("⏸️ Pressione Enter para continuar...")


if __name__ == "__main__":
    asyncio.run(main())
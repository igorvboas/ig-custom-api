from instagrapi import Client

USERNAME = ""
PASSWORD = ""
TARGET_USERNAME = ""  # Usuário de teste

cl = Client()
cl.login(USERNAME, PASSWORD)

# Buscar o ID do usuário alvo
user_id = cl.user_id_from_username(TARGET_USERNAME)

# Buscar 1 post do feed
posts = cl.user_medias(user_id, amount=1)
print(f"Encontrados {len(posts)} posts!")

if posts:
    post = posts[0]
    print("ID:", post.pk)
    print("Data de criação:", post.taken_at)
    print("Legenda:", getattr(post, "caption_text", ""))
    print("Tipo de mídia:", post.media_type)
    print("URL da mídia:", post.thumbnail_url)
else:
    print("Nenhum post encontrado.")

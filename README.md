# Instagram Collection API

API profissional para coleta de stories e posts do Instagram com sistema de pool de contas e rotação inteligente.

## 🚀 Features

- ✅ **Pool de Contas** com rotação inteligente
- ✅ **Coleta de Stories** e posts do feed
- ✅ **Download de mídias** em formato binário
- ✅ **Rate limiting** automático
- ✅ **Health monitoring** das contas
- ✅ **API REST** compatível com N8N
- ✅ **Logs detalhados** e monitoramento

## 📁 Estrutura do Projeto

```
apogeu_insta_api/
├── app/                          # Core da aplicação
│   ├── main.py                   # FastAPI app
│   ├── config.py                 # Configurações
│   ├── models.py                 # Data models
│   ├── core/                     # Business logic
│   ├── api/                      # API endpoints
│   └── utils/                    # Utilities
├── scripts/                      # Scripts utilitários
├── data/                         # Dados persistentes
└── tests/                        # Testes
```

## 🔧 Instalação

1. **Clone o repositório**
```bash
git clone <repository>
cd apogeu_insta_api
```

2. **Instale dependências**
```bash
pip install -r requirements.txt
```

3. **Configure ambiente**
```bash
cp .env.example .env
# Edite .env com suas configurações
```

4. **Adicione contas Instagram**
```bash
python manage_accounts.py
```

## 🚀 Uso

### Executar API
```bash
python run_api.py
```

### Gerenciar Contas
```bash
python manage_accounts.py
```

### Testar Coleta
```bash
python scripts/test_collector.py
```

## 📡 API Endpoints

### Coletar Conteúdo
```http
POST /collect/{username}
```

**Parâmetros:**
- `username`: Nome de usuário Instagram (sem @)
- `include_stories`: Incluir stories (default: true)
- `include_feed`: Incluir posts (default: true)  
- `max_feed_posts`: Máximo de posts (default: 10)

**Response:**
```json
{
  "success": true,
  "username": "usuario",
  "data": {
    "stories": [...],
    "feed_posts": [...]
  },
  "statistics": {
    "total_files": 15,
    "total_size_mb": 12.5
  }
}
```

### Health Check
```http
GET /health
```

### Status do Pool
```http
GET /pool-status
```

## ⚙️ Configuração

Configure no arquivo `.env`:

```env
# API
API_HOST=0.0.0.0
API_PORT=8000

# Pool
MAX_ACCOUNTS=30
ACCOUNT_COOLDOWN_MINUTES=120

# Delays
REQUEST_DELAY_MIN=1.0
REQUEST_DELAY_MAX=3.0

# Logging
LOG_LEVEL=INFO
```

## 🔒 Segurança

- Senhas das contas são armazenadas localmente
- Sessões Instagram são persistidas
- Logs detalhados para auditoria
- Rate limiting automático

## 📊 Monitoramento

- Health check das contas
- Logs rotativos
- Métricas de uso
- Status do pool em tempo real

## 🤝 Integração N8N

A API foi otimizada para uso com N8N:

1. **CRON** no N8N chama `/collect/{username}`
2. **API** retorna mídias em formato binário
3. **N8N** processa com IA e armazena

## 📄 Licença

Este projeto é para uso interno e educacional.

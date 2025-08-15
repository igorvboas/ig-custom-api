# app/api/onboarding.py
"""
Onboarding web para adicionar conta Instagram com suporte a Challenge/2FA,
LOGS visíveis na interface e sem prompt no terminal.

Fluxo:
1) GET  /adicionar-insta           -> formulário (username/password/proxy).
2) POST /adicionar-insta/iniciar   -> tenta login.
   - Se logar: adiciona ao pool e finaliza.
   - Se ChallengeRequired/TwoFactorRequired: mostra formulário de código + console de logs.
3) POST /adicionar-insta/confirmar -> recebe código e tenta concluir login (CHALLENGE/2FA).
4) POST /adicionar-insta/cancelar  -> cancela a sessão de onboarding.
"""

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any, List
from uuid import uuid4
from pathlib import Path
import json
import time

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired, TwoFactorRequired, LoginRequired

from app.config import Settings
from app.utils.logging_config import get_app_logger
from app.api.routes import get_collection_service

router = APIRouter(tags=["Onboarding UI"])
logger = get_app_logger(__name__)

# -----------------------------
# Persistência simples da sessão
# -----------------------------
_settings = Settings()
_ONB_DIR = Path(_settings.session_dir) / "onboarding"
_ONB_DIR.mkdir(parents=True, exist_ok=True)


def _onb_path(onb_id: str) -> Path:
    return _ONB_DIR / f"{onb_id}.json"


def _new_onb(username: str, password: str, proxy: Optional[str]) -> str:
    onb_id = str(uuid4())
    data = {
        "id": onb_id,
        "username": username.strip(),
        "password": password,
        "proxy": proxy.strip() if proxy else None,
        "status": "INIT",        # INIT | NEED_CODE | DONE | CANCELED
        "flow": None,            # "CHALLENGE" | "TWO_FACTOR"
        "logs": [],              # lista de strings
        "created_at": int(time.time()),
    }
    _save_onb(onb_id, data)
    return onb_id


def _save_onb(onb_id: str, data: Dict[str, Any]) -> None:
    _onb_path(onb_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_onb(onb_id: str) -> Optional[Dict[str, Any]]:
    p = _onb_path(onb_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _delete_onb(onb_id: str) -> None:
    _onb_path(onb_id).unlink(missing_ok=True)


def _append_log(onb_id: str, msg: str) -> None:
    data = _load_onb(onb_id)
    if not data:
        return
    ts = time.strftime("%H:%M:%S")
    data.setdefault("logs", []).append(f"[{ts}] {msg}")
    _save_onb(onb_id, data)


# -----------------------------
# HTML base + componentes
# -----------------------------
def _html_base(body: str, title: str = "Adicionar conta Instagram") -> HTMLResponse:
    html = f"""<!doctype html>
<html lang="pt-br"><head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{title}</title>
<style>
  body {{ font-family: system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; margin:24px; color:#111; }}
  .container {{ max-width: 760px; margin:0 auto; }}
  .card {{ padding: 24px; border:1px solid #e5e7eb; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,.05); }}
  h1 {{ font-size: 22px; margin: 0 0 16px; }}
  label {{ display:block; font-size: 14px; margin: 12px 0 6px; color:#374151; }}
  input {{ width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius: 10px; font-size: 14px; }}
  button {{ margin-top:16px; padding:12px 16px; border:0; border-radius:10px; background:#111827; color:#fff; font-weight:600; cursor:pointer; }}
  a.btn, form.inline {{ display:inline-block; margin-top:12px; margin-right:10px; }}
  .btn-secondary {{ background:#334155; color:#fff; padding:10px 14px; border-radius:10px; text-decoration:none; }}
  .muted {{ color:#6b7280; font-size:12px; margin-top:8px; }}
  .ok {{ background:#065f46; color:#fff; padding:10px 12px; border-radius:8px; }}
  .err {{ background:#7f1d1d; color:#fff; padding:10px 12px; border-radius:8px; }}
  .info {{ background:#1f2937; color:#fff; padding:10px 12px; border-radius:8px; }}
  .console {{ margin-top:16px; background:#0b1020; color:#c9d1ff; padding:12px; border-radius:10px; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas,"Liberation Mono","Courier New", monospace; font-size:12px; white-space:pre-wrap; max-height:260px; overflow:auto; }}
  .row {{ display:flex; gap:12px; align-items:center; flex-wrap:wrap; }}
</style>
</head><body><div class="container"><div class="card">
{body}
</div></div></body></html>"""
    return HTMLResponse(html)


def _console(logs: List[str]) -> str:
    if not logs:
        return '<div class="console">[console] aguardando eventos…</div>'
    return '<div class="console">' + "\n".join(logs[-200:]) + "</div>"


# -----------------------------
# UI: formulário inicial
# -----------------------------
@router.get("/adicionar-insta", response_class=HTMLResponse, summary="[UI] Formulário para adicionar conta")
async def ui_add_account(request: Request):
    body = f"""
<h1>Adicionar conta do Instagram</h1>
<form method="POST" action="/adicionar-insta/iniciar">
  <label>Username (sem @)</label>
  <input name="username" required placeholder="ex: usuario.teste" />
  <label>Senha</label>
  <input name="password" type="password" required />
  <label>Proxy (opcional)</label>
  <input name="proxy" placeholder="http://user:pass@host:port" />
  <button type="submit">Conectar conta</button>
  <div class="muted">Se a conta exigir verificação (código por e-mail/SMS/2FA), pediremos o código no próximo passo.</div>
</form>
"""
    return _html_base(body, title="Adicionar conta do Instagram")


# -----------------------------
# Iniciar login (NÃO pedir código no terminal)
# -----------------------------
@router.post("/adicionar-insta/iniciar", response_class=HTMLResponse, summary="[UI] Iniciar login (pode pedir código)")
async def ui_start_add_account(
    username: str = Form(...),
    password: str = Form(...),
    proxy: Optional[str] = Form(None),
):
    onb_id = _new_onb(username, password, proxy)
    _append_log(onb_id, f"Iniciando login para @{username}")
    if proxy:
        _append_log(onb_id, f"Proxy informado: {proxy}")

    cl = Client()
    if proxy:
        try:
            cl.set_proxy(proxy)
            _append_log(onb_id, "Proxy configurado com sucesso")
        except Exception as e:
            _append_log(onb_id, f"[WARN] Proxy inválido: {e}")

    # Handler de pré-login: impede prompt no terminal e devolve o fluxo à UI
    try:
        from instagrapi.mixins.challenge import ChallengeChoice
    except Exception:
        ChallengeChoice = object  # fallback tipagem

    def _prelogin_handler(_u: str, choice: "ChallengeChoice"):
        try:
            chosen = getattr(choice, "value", str(choice))
        except Exception:
            chosen = str(choice)
        _append_log(onb_id, f"Challenge detectado (método: {chosen}). Aguardando código na interface…")
        # Interrompe aqui para NÃO pedir no terminal:
        raise ChallengeRequired("awaiting_code_from_ui")

    cl.challenge_code_handler = _prelogin_handler

    try:
        _append_log(onb_id, "Tentando login direto…")
        ok = cl.login(username, password)
        if ok:
            _append_log(onb_id, "Login concluído com sucesso")
            pool = get_collection_service().account_pool
            added = pool.add_account(username, password, proxy)
            _append_log(onb_id, "Conta adicionada ao pool" if added else "Conta já no pool ou não pôde ser adicionada novamente")
            _delete_onb(onb_id)
            body = f"""
<h1>Conta adicionada</h1>
<p class="ok">✅ @{username} pronta para uso.</p>
<div class="row">
  <a class="btn-secondary" href="/pool-status">Ver status do pool</a>
  <a class="btn-secondary" href="/docs">Abrir Swagger</a>
  <a class="btn-secondary" href="/adicionar-insta">Adicionar outra conta</a>
</div>
"""
            return _html_base(body, title="Conta adicionada")

        # Se não retornou ok, força fluxo de verificação
        raise LoginRequired("Falha no login (sem desafio)")

    except TwoFactorRequired:
        data = _load_onb(onb_id) or {}
        data["status"] = "NEED_CODE"
        data["flow"] = "TWO_FACTOR"
        _save_onb(onb_id, data)
        _append_log(onb_id, "⚠️ 2FA requerido (use o código do app autenticador/SMS)")
        logs = (_load_onb(onb_id) or {}).get("logs", [])
        body = f"""
<h1>Verificação em duas etapas (2FA)</h1>
<p class="info">Informe o código 2FA para concluir o login de @{username}.</p>
<form method="POST" action="/adicionar-insta/confirmar">
  <input type="hidden" name="onboarding_id" value="{onb_id}" />
  <label>Código 2FA</label>
  <input name="code" required placeholder="6 dígitos" />
  <button type="submit">Confirmar</button>
</form>
<form class="inline" method="POST" action="/adicionar-insta/cancelar">
  <input type="hidden" name="onboarding_id" value="{onb_id}" />
  <button type="submit">Cancelar</button>
</form>
{_console(logs)}
"""
        return _html_base(body, title="Confirmar 2FA")

    except ChallengeRequired:
        data = _load_onb(onb_id) or {}
        data["status"] = "NEED_CODE"
        data["flow"] = "CHALLENGE"
        _save_onb(onb_id, data)
        _append_log(onb_id, "⚠️ Challenge requerido — Instagram enviará um código (email/SMS)")
        _append_log(onb_id, "Dica: verifique também a pasta de SPAM / promoções do e-mail.")
        logs = (_load_onb(onb_id) or {}).get("logs", [])
        body = f"""
<h1>Verificação necessária (Challenge)</h1>
<p class="info">Enviamos/solicitamos um código via e-mail ou SMS. Insira abaixo para concluir.</p>
<form method="POST" action="/adicionar-insta/confirmar">
  <input type="hidden" name="onboarding_id" value="{onb_id}" />
  <label>Código recebido</label>
  <input name="code" required placeholder="6 dígitos" />
  <button type="submit">Confirmar</button>
</form>
<form class="inline" method="POST" action="/adicionar-insta/cancelar">
  <input type="hidden" name="onboarding_id" value="{onb_id}" />
  <button type="submit">Cancelar</button>
</form>
{_console(logs)}
"""
        return _html_base(body, title="Verificar código")

    except Exception as e:
        _append_log(onb_id, f"[ERRO] Falha ao iniciar o login: {e}")
        logs = (_load_onb(onb_id) or {}).get("logs", [])
        body = f"""
<h1>Adicionar conta do Instagram</h1>
<p class="err">Falha ao iniciar o login: {str(e)}</p>
<a class="btn-secondary" href="/adicionar-insta">Tentar novamente</a>
{_console(logs)}
"""
        return _html_base(body, title="Erro")


# -----------------------------
# Confirmar código (CHALLENGE/2FA)
# -----------------------------
@router.post("/adicionar-insta/confirmar", response_class=HTMLResponse, summary="[UI] Confirmar código e concluir")
async def ui_confirm_code(
    onboarding_id: str = Form(...),
    code: str = Form(...),
):
    data = _load_onb(onboarding_id)
    if not data:
        body = """
<h1>Verificação</h1>
<p class="err">Sessão de onboarding não encontrada ou expirada.</p>
<a class="btn-secondary" href="/adicionar-insta">Voltar</a>
"""
        return _html_base(body, title="Sessão expirada")

    username = data["username"]
    password = data["password"]
    proxy = data.get("proxy")
    flow = data.get("flow", "CHALLENGE")  # default CHALLENGE

    _append_log(onboarding_id, f"Recebido código para @{username}. Tentando concluir {flow}…")

    cl = Client()
    if proxy:
        try:
            cl.set_proxy(proxy)
            _append_log(onboarding_id, "Proxy configurado novamente para concluir verificação")
        except Exception as e:
            _append_log(onboarding_id, f"[WARN] Proxy inválido ao confirmar: {e}")

    try:
        if flow == "TWO_FACTOR":
            # Dispara estado 2FA, se necessário
            try:
                cl.login(username, password)
            except TwoFactorRequired:
                pass

            ok = False
            try:
                ok = bool(cl.two_factor_login(code))
            except Exception as e:
                _append_log(onboarding_id, f"[WARN] two_factor_login falhou: {e}")
                ok = False

            if not ok:
                raise LoginRequired("2FA não aceito")

            _append_log(onboarding_id, "2FA validado com sucesso")

        else:
            # CHALLENGE: usar handler que retorna o código informado e fallback explicitamente
            try:
                from instagrapi.mixins.challenge import ChallengeChoice
            except Exception:
                ChallengeChoice = object

            def _handler(_u: str, choice: "ChallengeChoice"):
                try:
                    chosen = getattr(choice, "value", str(choice))
                except Exception:
                    chosen = str(choice)
                _append_log(onboarding_id, f"Instagram solicitou código via método: {chosen}")
                return code

            cl.challenge_code_handler = _handler

            ok = False
            try:
                ok = bool(cl.login(username, password))
            except ChallengeRequired:
                ok = False
            except Exception as e:
                _append_log(onboarding_id, f"[WARN] login com handler falhou: {e}")
                ok = False

            # Fallback para versões que exigem resolver explicitamente
            if not ok:
                try:
                    # Algumas versões usam challenge_resolve(code) ou challenge_resolve(code=...)
                    try:
                        resolved = cl.challenge_resolve(code)
                    except TypeError:
                        resolved = cl.challenge_resolve(code=code)
                    ok = bool(resolved)
                except Exception as e:
                    _append_log(onboarding_id, f"[WARN] challenge_resolve falhou: {e}")
                    ok = False

            if not ok:
                raise LoginRequired("Challenge não aceito")

            _append_log(onboarding_id, "Challenge validado com sucesso")

        # Registrar no pool
        pool = get_collection_service().account_pool
        added = pool.add_account(username, password, proxy)
        _append_log(
            onboarding_id,
            "Conta adicionada ao pool" if added else "Conta já estava no pool ou não pôde ser registrada novamente"
        )
        _delete_onb(onboarding_id)

        body = f"""
<h1>Tudo certo!</h1>
<p class="ok">✅ @{username} pronta para uso.</p>
<div class="row">
  <a class="btn-secondary" href="/pool-status">Ver status do pool</a>
  <a class="btn-secondary" href="/docs">Abrir Swagger</a>
  <a class="btn-secondary" href="/adicionar-insta">Adicionar outra conta</a>
</div>
"""
        return _html_base(body, title="Concluído")

    except Exception as e:
        _append_log(onboarding_id, f"[ERRO] Falha na confirmação do código: {e}")
        logs = (_load_onb(onboarding_id) or {}).get("logs", [])
        body = f"""
<h1>Verificação</h1>
<p class="err">Não foi possível validar o código: {str(e)}</p>
<form method="POST" action="/adicionar-insta/confirmar">
  <input type="hidden" name="onboarding_id" value="{onboarding_id}" />
  <label>Tentar novamente</label>
  <input name="code" required placeholder="6 dígitos" />
  <button type="submit">Confirmar</button>
</form>
<form class="inline" method="POST" action="/adicionar-insta/cancelar">
  <input type="hidden" name="onboarding_id" value="{onboarding_id}" />
  <button type="submit">Cancelar</button>
</form>
{_console(logs)}
"""
        return _html_base(body, title="Erro na verificação")


# -----------------------------
# Cancelar sessão
# -----------------------------
@router.post("/adicionar-insta/cancelar", response_class=HTMLResponse, summary="[UI] Cancelar sessão de onboarding")
async def ui_cancel(onboarding_id: str = Form(...)):
    data = _load_onb(onboarding_id)
    if data:
        _append_log(onboarding_id, "Sessão cancelada pelo usuário")
        _delete_onb(onboarding_id)
    body = """
<h1>Onboarding cancelado</h1>
<p class="info">A sessão foi encerrada.</p>
<a class="btn-secondary" href="/adicionar-insta">Voltar ao início</a>
"""
    return _html_base(body, title="Cancelado")

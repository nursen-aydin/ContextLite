import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import json
from src.main import app
from src.services.db import get_connection

client = TestClient(app)


def sse_payloads(response):
    payloads = []
    for line in response.iter_lines():
        if line.startswith("data: ") and line != "data: [DONE]":
            payloads.append(json.loads(line[6:]))
    return payloads


@pytest.fixture(scope="function", autouse=True)
def setup_and_login():
    client.cookies.clear()
    client.headers.clear()

    setup_res = client.post("/api/auth/setup", json={
        "name": "Admin",
        "email": "admin@example.com",
        "password": "Password123!"
    })
    
    login_res = client.post("/api/auth/login", json={
        "email": "admin@example.com",
        "password": "Password123!"
    })
    
    client.cookies.update(login_res.cookies)
    client.headers.update({"X-CSRF-Token": login_res.cookies.get("csrf_token")})
    yield

def test_setup_only_once():
    res = client.post("/api/auth/setup", json={
        "name": "Hacker",
        "email": "hacker@example.com",
        "password": "Password123!"
    })
    assert res.status_code == 403
    assert "zaten yapılmış" in res.json()["detail"]

def test_password_validation():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()
    
    res = client.post("/api/auth/setup", json={
        "name": "Admin",
        "email": "admin@example.com",
        "password": "weak"
    })
    assert res.status_code == 400
    assert "8" in res.json()["detail"]

def test_login_invalid_credentials_does_not_leak_existence():
    unauth_client = TestClient(app)
    res = unauth_client.post("/api/auth/login", json={
        "email": "notexist@example.com",
        "password": "Password123!"
    })
    assert res.status_code == 401
    assert "E-posta veya parola hatalı" in res.json()["detail"]

def test_csrf_protection_for_post():
    client.headers = {}
    res = client.post("/api/budget", json={"daily_limit": 10.0, "monthly_limit": 100.0})
    assert res.status_code == 403
    assert "CSRF" in res.json()["detail"]

def test_unauthorized_access():
    unauth_client = TestClient(app)
    res = unauth_client.get("/api/providers")
    assert res.status_code == 401

def test_logout_invalidates_session():
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    
    res2 = client.get("/api/providers")
    assert res2.status_code == 401

def test_data_isolation():
    # Create second user directly via DB since setup is disabled
    from src.services.db import create_user, set_budget_settings
    user2_id = create_user("User2", "user2@example.com", "hash", "user")
    
    set_budget_settings(user2_id, 99.0, 99.0)
    
    res = client.get("/api/budget")
    assert res.json()["daily_limit"] is None

@patch("src.providers.local_foundry.LocalQwenProvider.generate_chat_stream")
def test_conversation_history(mock_local):
    mock_local.return_value = [{"content": "Yanit"}, {"is_metadata": True, "provider": "Foundry Local", "model": "qwen3-4b"}]
    
    res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hi"}], "mode": "Sadece Yerel"})
    list(res.iter_lines())  # Exhaust generator to release DB locks
    
    res_convs = client.get("/api/conversations")
    convs = res_convs.json()
    assert len(convs) > 0
    conv_id = convs[0]["id"]
    
    res_msgs = client.get(f"/api/conversations/{conv_id}")
    msgs = res_msgs.json()
    assert len(msgs) >= 2

def test_health_check():
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_login_page_contains_required_verification_controls():
    res = client.get("/login")
    assert res.status_code == 200
    assert 'id="login-resend-btn"' in res.text
    assert 'id="unverified-block"' in res.text


def test_chat_does_not_show_general_chat_label():
    res = client.get("/app")
    assert res.status_code == 200
    assert "Genel sohbet" not in res.text
    assert 'id="chat-project-select" class="form-select hidden"' in res.text


def test_sidebar_history_divider_is_resizable():
    page = client.get("/app")
    script = client.get("/static/app.js")
    assert page.status_code == 200
    assert script.status_code == 200
    assert 'id="sidebar-resize-handle"' in page.text
    assert "pointerdown" in script.text
    assert "contextlite_sidebar_history_height" in script.text


def test_chat_token_saver_uses_compact_toggle():
    page = client.get("/app")
    styles = client.get("/static/style.css")
    assert page.status_code == 200
    assert styles.status_code == 200
    assert 'class="token-saver-toggle tooltip-wrapper"' in page.text
    assert 'class="token-saver-track"' in page.text
    assert ".token-saver-toggle > input:checked ~ .token-saver-track" in styles.text


@patch("src.api.routes.local_provider.generate_chat_stream")
def test_token_saver_reports_real_history_reduction(mock_generate):
    from src.services.db import add_message, create_conversation, get_conversation_info

    conversation_id = "token-saver-conversation"
    create_conversation(conversation_id, 1, "Uzun sohbet", "Sadece Yerel")
    for index in range(8):
        add_message(
            f"history-{index}",
            conversation_id,
            "user" if index % 2 == 0 else "assistant",
            f"Bu geçmiş mesaj {index} ayrıntılı bağlam bilgisi içeriyor ve birkaç kelimeden oluşuyor.",
        )
    mock_generate.return_value = [{"content": "Kısa yanıt"}]

    response = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "messages": [{"role": "user", "content": "Sonuç nedir?"}],
        "provider": "foundry",
        "token_saver_enabled": True,
    })
    metadata = next(item for item in sse_payloads(response) if item.get("is_metadata"))

    assert metadata["token_saver_enabled"] is True
    assert metadata["prevented_tokens"] > 0
    assert metadata["savings_percent"] > 0
    assert get_conversation_info(conversation_id, 1)["token_saver_enabled"] == 1


@patch("src.api.routes.local_provider.generate_chat_stream")
def test_token_saver_reports_savings_on_first_response(mock_generate):
    mock_generate.return_value = [{"content": "Kısa yanıt"}]

    response = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "Merhaba"}],
        "provider": "foundry",
        "token_saver_enabled": True,
    })
    payloads = sse_payloads(response)
    metadata = next(item for item in payloads if item.get("is_metadata"))
    prompt_preview = next(item for item in payloads if item.get("is_prompt_preview"))

    assert metadata["prevented_tokens"] > 0
    assert metadata["savings_percent"] > 0
    assert "[SYSTEM]" in prompt_preview["sent_prompt"]
    assert "[USER]\nMerhaba" in prompt_preview["sent_prompt"]
    assert prompt_preview["normal_prompt_tokens"] > prompt_preview["sent_prompt_tokens"]


@patch("src.api.routes.local_provider.generate_chat_stream")
@patch("src.api.routes.local_provider.generate_chat")
@patch("src.api.routes.local_provider.count_tokens")
@patch("src.api.routes.local_provider.list_models")
def test_token_saver_optimizes_long_user_prompt_before_answer(mock_models, mock_count, mock_optimize, mock_stream):
    original_prompt = (
        "Antibiotics are medicines used to treat bacterial infections. They either kill "
        "bacteria or prevent them from reproducing. They do not work against viruses and "
        "incorrect use can cause antibiotic resistance. Please explain all of the information "
        "above clearly in exactly one sentence without adding unrelated details."
    )
    optimized_prompt = "Explain antibiotics, their bacterial use and resistance risk in exactly one sentence."
    mock_models.return_value = [
        {"id": "qwen2.5-1.5b", "name": "qwen2.5-1.5b", "isLoaded": True, "isCached": True},
        {"id": "phi-4-mini", "name": "phi-4-mini", "isLoaded": False, "isCached": True},
    ]
    mock_count.side_effect = lambda text, model: 55 if text == original_prompt else 14
    mock_optimize.side_effect = [
        optimized_prompt,
        '{"same_task":true,"runnable_prompt":true,"constraints_preserved":true,"answer_generated":false}',
    ]
    mock_stream.return_value = [{"content": "Kısa yanıt"}]

    response = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": original_prompt}],
        "provider": "foundry",
        "token_saver_enabled": True,
        "save_history": False,
    })
    payloads = sse_payloads(response)
    preview = next(item for item in payloads if item.get("is_prompt_preview"))

    assert preview["optimization_applied"] is True
    assert preview["optimized_user_tokens"] < preview["original_user_tokens"]
    assert preview["optimizer_model"] == "phi-4-mini"
    assert preview["original_user_prompt"] == original_prompt
    assert preview["optimized_user_prompt"] == optimized_prompt
    assert f"[USER]\n{optimized_prompt}" in preview["sent_prompt"]
    assert original_prompt not in preview["sent_prompt"]
    sent_messages = mock_stream.call_args.kwargs["messages"]
    assert sent_messages[-1]["content"] == optimized_prompt
    assert mock_optimize.call_args_list[0].kwargs["model"] == "phi-4-mini"


@patch("src.api.routes.local_provider.generate_chat_stream")
def test_existing_conversation_does_not_duplicate_browser_history(mock_generate):
    from src.services.db import add_message, create_conversation

    conversation_id = "no-duplicate-history"
    create_conversation(conversation_id, 1, "Tekrarsız sohbet", "Sadece Yerel")
    add_message("old-user", conversation_id, "user", "Önceki soru")
    add_message("old-assistant", conversation_id, "assistant", "Önceki yanıt")
    mock_generate.return_value = [{"content": "Yeni yanıt"}]

    response = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "messages": [
            {"role": "user", "content": "Önceki soru"},
            {"role": "assistant", "content": "Önceki yanıt"},
            {"role": "user", "content": "Yeni soru"},
        ],
        "provider": "foundry",
    })
    list(response.iter_lines())
    sent_messages = mock_generate.call_args.kwargs["messages"]

    assert [message["content"] for message in sent_messages].count("Önceki soru") == 1
    assert [message["content"] for message in sent_messages].count("Önceki yanıt") == 1
    assert [message["content"] for message in sent_messages].count("Yeni soru") == 1


def test_sidebar_theme_picker_has_icons_and_menu():
    page = client.get("/app")
    script = client.get("/static/app.js")
    assert page.status_code == 200
    assert script.status_code == 200
    assert 'id="theme-menu-button"' in page.text
    assert 'data-theme="system"' in page.text
    assert 'data-theme="light"' in page.text
    assert 'data-theme="dark"' in page.text
    assert "renderThemePicker" in script.text


def test_local_email_verification_code_flow(monkeypatch):
    """A fresh account can be verified locally when SMTP is unavailable."""
    from src.config import settings

    monkeypatch.setattr(settings, "smtp_host", "")
    signup_client = TestClient(app)
    signup_res = signup_client.post("/api/auth/signup", json={
        "name": "Yerel Kullanıcı",
        "email": "local-verify@example.com",
        "password": "LocalPassword123!",
    })
    assert signup_res.status_code == 200
    assert signup_res.json()["verification_delivery"] == "local"

    csrf = signup_client.cookies.get("csrf_token")
    headers = {"X-CSRF-Token": csrf}
    status_before = signup_client.get("/api/auth/verify-status")
    assert status_before.status_code == 200
    assert status_before.json()["verified"] is False

    request_res = signup_client.post("/api/auth/request-verification", headers=headers)
    assert request_res.status_code == 200
    code = request_res.json()["local_code"]
    assert len(code) == 6 and code.isdigit()

    verify_res = signup_client.post(
        "/api/auth/verify-code",
        json={"code": code},
        headers=headers,
    )
    assert verify_res.status_code == 200
    assert signup_client.get("/api/auth/verify-status").json()["verified"] is True


def test_email_link_verification_flow(monkeypatch):
    """SMTP mode creates a token that the public verification link can consume."""
    from src.config import settings

    monkeypatch.setattr(settings, "smtp_host", "smtp.example.test")
    signup_client = TestClient(app)
    with patch("src.api.auth.send_verification_email", return_value=True) as send_mock:
        signup_res = signup_client.post("/api/auth/signup", json={
            "name": "E-posta Kullanıcısı",
            "email": "mail-verify@example.com",
            "password": "MailPassword123!",
        })

    assert signup_res.status_code == 200
    assert signup_res.json()["verification_delivery"] == "email"
    assert signup_res.json()["email_sent"] is True
    raw_token = send_mock.call_args.args[1]

    verify_res = signup_client.post("/api/auth/verify-email", json={"token": raw_token})
    assert verify_res.status_code == 200
    assert signup_client.get("/api/auth/verify-status").json()["verified"] is True


def test_verify_page_has_local_and_email_controls():
    res = client.get("/account/verify")
    assert res.status_code == 200
    assert '/static/style.css' in res.text
    assert 'id="request-btn"' in res.text
    assert 'id="verification-code"' in res.text

def test_crypto_round_trip():
    from src.services.crypto import encrypt_key, decrypt_key
    msg = "sk-secret-key-12345"
    enc = encrypt_key(msg)
    assert enc != msg
    dec = decrypt_key(enc)
    assert dec == msg

def test_provider_listing_no_leak():
    res = client.get("/api/providers")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    for p in data:
        assert "api_key" not in p
        assert "encrypted_key" not in p


def test_cloud_provider_settings_are_available():
    page = client.get("/app")
    script = client.get("/static/app.js")
    assert page.status_code == 200
    assert script.status_code == 200
    assert 'id="cloud-providers-section"' in page.text
    assert 'id="providers-container"' in page.text
    assert "['openai', 'gemini']" in script.text
    assert "testLocalProvider" in script.text


def test_cloud_provider_status_and_allowlist():
    save_res = client.post("/api/providers/gemini", json={"api_key": "test-gemini-key"})
    assert save_res.status_code == 200

    providers = client.get("/api/providers").json()
    gemini = next(item for item in providers if item["id"] == "gemini")
    assert gemini["has_key"] is True
    assert gemini["status_code"] == "untested"

    unsupported = client.post("/api/providers/anthropic", json={"api_key": "secret"})
    assert unsupported.status_code == 400

def test_save_and_delete_key():
    res1 = client.post("/api/providers/openai", json={"api_key": "sk-123"})
    assert res1.status_code == 200
    
    res2 = client.get("/api/providers")
    p = next((x for x in res2.json() if x["id"] == "openai"), None)
    assert p["has_key"] is True
    
    res3 = client.delete("/api/providers/openai")
    assert res3.status_code == 200
    
    res4 = client.get("/api/providers")
    p = next((x for x in res4.json() if x["id"] == "openai"), None)
    assert p["has_key"] is False

def test_test_connection_invalid_key():
    res = client.post("/api/providers/openai/test", json={"api_key": "bad_key"})
    assert res.status_code == 400

@patch("src.providers.local_foundry.LocalQwenProvider.generate_chat_stream")
def test_local_model_routing_smoke_test(mock_generate):
    mock_generate.return_value = [{"content": "Foundry Local"}, {"is_metadata": True, "provider": "Foundry Local", "model": "qwen3-4b"}]
    
    res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "selam"}], "mode": "Sadece Yerel"})
    list(res.iter_lines())  # Exhaust generator to release DB locks
    
    found = False
    for line in res.iter_lines():
        if line.startswith("data: ") and line != "data: [DONE]":
            data = json.loads(line[6:])
            if data.get("content") == "Foundry Local":
                found = True
    assert found
    mock_generate.assert_called_once()

@patch("src.providers.openai_provider.OpenAIProvider.generate_chat_stream")
def test_explicit_cloud_provider(mock_external):
    from src.services.db import get_user_by_email, save_provider_key
    from src.services.crypto import encrypt_key

    user = get_user_by_email("admin@example.com")
    save_provider_key(user["id"], "openai", encrypt_key("sk-test"))
    mock_external.return_value = [
        {"content": "Bulut yanıtı"},
        {"is_metadata": True, "provider": "OpenAI", "model": "gpt-4o-mini"},
    ]

    res = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "selam"}],
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mode": "Modeli kendim seçerim",
    })
    assert res.status_code == 200
    assert any(item.get("content") == "Bulut yanıtı" for item in sse_payloads(res))
    mock_external.assert_called_once()


@patch("src.providers.local_foundry.LocalQwenProvider.generate_chat_stream")
def test_foundry_error_is_visible_and_does_not_silently_use_cloud(mock_local):
    mock_local.side_effect = RuntimeError("Foundry modeli yüklenemedi")
    res = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "selam"}],
        "provider": "foundry",
        "mode": "Sadece Yerel",
    })
    assert res.status_code == 200
    assert any("Foundry modeli yüklenemedi" in item.get("error", "") for item in sse_payloads(res))



def test_usage_summary_endpoint():
    res = client.get("/api/usage/summary")
    assert res.status_code == 200
    data = res.json()
    assert "today_requests" in data
    assert "total_cost" in data


@patch("src.api.routes._model_install_executor.submit")
@patch("src.api.routes.local_provider.list_models")
def test_model_install_is_started_in_background(mock_list_models, mock_submit):
    from src.api import routes

    routes._model_install_jobs.clear()
    mock_list_models.return_value = [{
        "id": "test-model",
        "name": "Test Model",
        "isCached": False,
        "isLoaded": False,
    }]

    res = client.post("/api/models/install", json={"model_id": "test-model"})
    assert res.status_code == 202
    assert res.json()["status"] == "queued"
    mock_submit.assert_called_once_with(routes._run_model_install, "test-model")

    jobs = client.get("/api/models/installations")
    assert jobs.status_code == 200
    assert jobs.json()[0]["model_id"] == "test-model"
    routes._model_install_jobs.clear()


@patch("src.api.routes._model_install_executor.submit")
@patch("src.api.routes.local_provider.list_models")
def test_multiple_model_installs_are_queued_instead_of_rejected(mock_list_models, mock_submit):
    from src.api import routes

    routes._model_install_jobs.clear()
    mock_list_models.return_value = [
        {"id": "model-a", "isCached": False, "isLoaded": False},
        {"id": "model-b", "isCached": False, "isLoaded": False},
    ]

    first = client.post("/api/models/install", json={"model_id": "model-a"})
    second = client.post("/api/models/install", json={"model_id": "model-b"})

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["status"] == "queued"
    assert second.json()["status"] == "queued"
    assert mock_submit.call_count == 2
    routes._model_install_jobs.clear()
    routes._model_install_cancel_events.clear()


@patch("src.api.routes._model_install_executor.submit")
@patch("src.api.routes.local_provider.list_models")
def test_model_install_can_be_cancelled(mock_list_models, mock_submit):
    from src.api import routes

    routes._model_install_jobs.clear()
    routes._model_install_cancel_events.clear()
    mock_list_models.return_value = [
        {"id": "cancel-model", "isCached": False, "isLoaded": False},
    ]

    queued = client.post("/api/models/install", json={"model_id": "cancel-model"})
    cancelled = client.delete("/api/models/install/cancel-model")

    assert queued.status_code == 202
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelling"
    assert routes._model_install_cancel_events["cancel-model"].is_set()
    routes._run_model_install("cancel-model")
    assert routes._model_install_jobs["cancel-model"]["status"] == "cancelled"
    routes._model_install_jobs.clear()
    routes._model_install_cancel_events.clear()


@patch("src.api.routes.local_provider.remove_model")
@patch("src.api.routes.local_provider.list_models")
def test_cached_model_can_be_removed(mock_list_models, mock_remove):
    from src.api import routes

    routes._model_install_jobs.clear()
    routes._model_install_cancel_events.clear()
    mock_list_models.return_value = [
        {"id": "cached-model", "isCached": True, "isLoaded": False},
    ]
    mock_remove.return_value = {"id": "cached-model", "status": "removed"}

    response = client.delete("/api/models/cached-model")

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    mock_remove.assert_called_once_with("cached-model")


@patch("src.api.routes.local_provider.remove_model")
@patch("src.api.routes.local_provider.list_models")
def test_non_cached_model_cannot_be_removed(mock_list_models, mock_remove):
    mock_list_models.return_value = [
        {"id": "downloadable-model", "isCached": False, "isLoaded": False},
    ]

    response = client.delete("/api/models/downloadable-model")

    assert response.status_code == 409
    mock_remove.assert_not_called()


@patch("src.api.routes.local_provider.install_model")
def test_model_install_network_error_is_safe_and_actionable(mock_install):
    from src.api import routes

    routes._model_install_jobs.clear()
    mock_install.side_effect = RuntimeError(
        "Microsoft.Neutron.Downloader.RegionFallbackException: "
        "SocketException (10013) polandcentral.api.azureml.ms:443\nvery long stack trace"
    )

    routes._run_model_install("blocked-model")
    job = routes._model_install_jobs["blocked-model"]

    assert job["status"] == "failed"
    assert job["retryable"] is True
    assert "HTTPS (443)" in job["error"]
    assert "very long stack trace" not in job["error"]
    routes._model_install_jobs.clear()
    routes._model_install_cancel_events.clear()


@patch("src.api.routes.select_prompt_optimizer_model", return_value="qwen2.5-1.5b")
@patch("src.api.routes.FoundryProvider.count_tokens")
@patch("src.api.routes.FoundryProvider.generate_chat")
def test_prompt_optimizer_ignores_serialized_model_object(mock_generate, mock_count, _mock_select):
    mock_generate.side_effect = [
        "Teknik istemi önemli koşulları koruyarak kısalt.",
        '{"same_task":true,"runnable_prompt":true,"constraints_preserved":true,"answer_generated":false}',
    ]
    mock_count.side_effect = [18, 9]
    res = client.post("/api/optimize-prompt", json={
        "prompt": "Bu uzun teknik istemi bütün önemli koşulları koruyarak mümkün olduğu kadar kısa ve açık bir metne dönüştür.",
        "provider": "foundry",
        "model": "[object Object]",
    })

    assert res.status_code == 200
    assert res.json()["optimized_prompt"] == "Teknik istemi önemli koşulları koruyarak kısalt."
    assert res.json()["is_approximate"] is False
    assert mock_generate.call_args_list[0].kwargs["model"] == "qwen2.5-1.5b"


def test_prompt_validator_rejects_direct_qa_answer():
    from src.api.routes import structural_prompt_issues

    original = (
        'Answer the question from the context. Respond "Unsure about answer" if unsure.\n'
        'Context: OKT3 was originally sourced from mice.\n'
        'Question: What was OKT3 originally sourced from?\n'
        'Answer:'
    )
    issues = structural_prompt_issues(original, "OKT3 was originally sourced from mice.")

    assert "question_missing_or_answer_only" in issues
    assert "context_structure_missing" in issues
    assert "quoted_constraint_missing" in issues


def test_extractive_qa_optimizer_keeps_task_not_answer():
    from src.api.routes import build_extractive_qa_prompt, structural_prompt_issues

    original = (
        'Answer from context and keep it short. Respond "Unsure about answer" if unsure.\n'
        'Context: Teplizumab traces its roots to a New Jersey company. Scientists generated '
        'an early antibody dubbed OKT3. Originally sourced from mice, the molecule bound to '
        'T cells. In 1986 it was approved to prevent kidney transplant rejection.\n'
        'Question: What was OKT3 originally sourced from?\n'
        'Answer:'
    )

    optimized = build_extractive_qa_prompt(original)

    assert optimized is not None
    assert "Context:" in optimized
    assert "dubbed OKT3" in optimized
    assert "sourced from mice" in optimized
    assert "Question: What was OKT3 originally sourced from?" in optimized
    assert optimized.endswith("Answer:")
    assert "1986" not in optimized
    assert structural_prompt_issues(original, optimized) == []


def test_extractive_qa_uses_deterministic_fallback_when_validator_format_is_bad():
    from src.api.routes import build_extractive_qa_prompt, validate_optimizer_candidate

    original = (
        'Answer from context and keep it short. Respond "Unsure about answer" if unsure.\n'
        'Context: Teplizumab has a long development history. Scientists generated an early '
        'antibody dubbed OKT3. Originally sourced from mice, it bound to T cells. In 1986 it '
        'was approved to prevent kidney transplant rejection.\n'
        'Question: What was OKT3 originally sourced from?\n'
        'Answer:'
    )
    candidate = build_extractive_qa_prompt(original)

    class BadlyFormattedValidator:
        def generate_chat(self, *args, **kwargs):
            return "The candidate appears valid, but here is extra commentary."

    result = validate_optimizer_candidate(
        original,
        candidate,
        BadlyFormattedValidator(),
        "qwen2.5-1.5b",
        "extractive_qa",
    )

    assert result["valid"] is True
    assert result["runnable_prompt"] is True
    assert result["answer_generated"] is False
    assert result["verification"] == "deterministic_extractive_qa"


@patch("src.api.routes.FoundryProvider.count_tokens", side_effect=[61, 9])
@patch("src.api.routes.FoundryProvider.generate_chat")
@patch("src.api.routes.build_extractive_qa_prompt", return_value=None)
def test_prompt_optimizer_endpoint_rejects_answer_leak(_mock_extractive, mock_generate, _mock_count):
    mock_generate.return_value = "OKT3 was originally sourced from mice."
    original = (
        'Answer briefly. Respond "Unsure about answer" if unsure.\n'
        'Context: OKT3 was originally sourced from mice.\n'
        'Question: What was OKT3 originally sourced from?\n'
        'Answer:'
    )

    res = client.post("/api/optimize-prompt", json={
        "prompt": original,
        "provider": "foundry",
        "model": "qwen2.5-1.5b",
    })

    assert res.status_code == 422
    assert "geçerli bir prompt olmadığı" in res.json()["detail"]
    assert mock_generate.call_count == 1


@patch("src.api.routes.FoundryProvider.count_tokens", side_effect=[61, 29])
@patch("src.api.routes.FoundryProvider.generate_chat")
def test_prompt_optimizer_preserves_qa_task_and_uses_same_tokenizer(mock_generate, mock_count):
    original = (
        'Answer briefly. Respond "Unsure about answer" if unsure.\n'
        'Context: OKT3 was originally sourced from mice.\n'
        'Question: What was OKT3 originally sourced from?\n'
        'Answer:'
    )
    optimized = (
        'Answer the question using only the context. Return only a brief answer; do not explain. '
        'If uncertain, respond exactly "Unsure about answer".\n'
        'Context: OKT3 was originally sourced from mice.\n'
        'Question: What was OKT3 originally sourced from?\n'
        'Answer:'
    )
    mock_generate.return_value = (
        '{"same_task":true,"runnable_prompt":true,'
        '"constraints_preserved":true,"answer_generated":false}'
    )

    res = client.post("/api/optimize-prompt", json={
        "prompt": original,
        "provider": "foundry",
        "model": "qwen2.5-1.5b",
    })

    assert res.status_code == 200
    assert res.json()["optimized_prompt"] == optimized
    assert res.json()["validation"]["valid"] is True
    assert res.json()["tokenizer_name"] == "qwen2.5-1.5b tokenizer"
    assert [call.args[1] for call in mock_count.call_args_list] == [
        "qwen2.5-1.5b",
        "qwen2.5-1.5b",
    ]

def test_login_rate_limit():
    unauth = TestClient(app)
    for _ in range(5):
        unauth.post("/api/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    
    res = unauth.post("/api/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert res.status_code == 429
    assert "Çok fazla" in res.json()["detail"]
    
    from src.api.auth import login_attempts
    login_attempts.clear()

def test_secure_cookies():
    res = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Password123!"})
    cookies = res.headers.get_list("set-cookie")
    session_cookie = next(c for c in cookies if "session_id" in c)
    assert "HttpOnly" in session_cookie
    assert "samesite=lax" in session_cookie.lower()

@patch("src.providers.local_foundry.LocalQwenProvider.generate_chat_stream")
def test_save_history_off(mock_generate):
    mock_generate.return_value = [{"content": "Yanit"}]
    res = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hi"}], "mode": "Sadece Yerel", "save_history": False})
    list(res.iter_lines())  # Exhaust generator to release DB locks
    assert res.status_code == 200
    found_conv = False
    for line in res.iter_lines():
        if "conversation_id" in line:
            found_conv = True
    assert not found_conv

@patch("src.providers.local_foundry.LocalQwenProvider.generate_chat_stream")
def test_idempotency_request_id(mock_generate):
    mock_generate.return_value = [{"content": "Yanit"}]
    req_id = "test_req_123"
    res1 = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hi"}], "mode": "Sadece Yerel", "request_id": req_id})
    list(res1.iter_lines())  # Exhaust generator to release DB locks
    res2 = client.post("/api/chat/stream", json={"messages": [{"role": "user", "content": "hi"}], "mode": "Sadece Yerel", "request_id": req_id})
    list(res2.iter_lines())  # Exhaust generator to release DB locks 
    found_error = False
    for line in res2.iter_lines():
        if line.startswith("data: ") and line != "data: [DONE]":
            import json
            try:
                data = json.loads(line[6:])
                if data.get("error") == "Bu istek zaten işlendi.":
                    found_error = True
            except:
                pass
    assert found_error

@patch("src.providers.local_foundry.LocalQwenProvider.generate_chat_stream")
@patch("litellm.completion")
def test_local_request_has_zero_cost_and_never_calls_cloud(mock_litellm_completion, mock_generate):
    mock_generate.return_value = [{"content": "Yerel Yanit"}]
    from src.services.db import get_user_by_email, set_budget_settings
    u = get_user_by_email("admin@example.com")
    
    set_budget_settings(u["id"], daily=0.0)
    res = client.post("/api/chat/stream", json={
        "messages": [{"role": "user", "content": "hi"}],
        "provider": "foundry",
        "mode": "Sadece Yerel",
    })
    assert res.status_code == 200
    assert "Yerel Yanit" in res.text
    assert mock_litellm_completion.call_count == 0

def test_old_data_adopted_by_first_owner():
    from src.services.db import get_connection, create_user
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO usage_logs (provider, model, user_id) VALUES ('Test', 'test', NULL)")
    conn.commit()
    conn.close()
    
    uid = create_user("Owner2", "owner2@example.com", "hash", "owner")
    
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT user_id FROM usage_logs WHERE provider='Test'")
    adopted_uid = c.fetchone()[0]
    conn.close()
    
    assert adopted_uid == uid

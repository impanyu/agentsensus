import json
import os

from society.run import _build_llm_and_embed, _llm_config_snapshot
from society.llm import LLMClient


def test_embed_provider_split_from_config(tmp_path):
    """embed_api_key/embed_base_url in config.json point the EmbeddingClient
    at a different provider than the chat LLMClient."""
    cfg = {
        "api_key": "sk-deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "chat_model": "deepseek-v4-pro",
        "embed_api_key": "sk-openai-embed",
        "embed_base_url": "https://api.openai.com/v1",
        "embed_model": "text-embedding-3-small",
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    llm, embed_fn = _build_llm_and_embed(str(config_path))

    assert isinstance(llm, LLMClient)
    assert llm.base_url == "https://api.deepseek.com/v1"
    assert llm.api_key == "sk-deepseek-chat"
    assert llm.chat_model == "deepseek-v4-pro"

    embed_client = embed_fn.__self__
    assert embed_client.base_url == "https://api.openai.com/v1"
    assert embed_client.api_key == "sk-openai-embed"
    assert embed_client.embed_model == "text-embedding-3-small"


def test_embed_falls_back_to_chat_provider(tmp_path):
    """Without embed_* keys, embeddings fall back to the chat provider
    (backward compatible with the pre-split single-provider config)."""
    cfg = {
        "api_key": "sk-shared-key",
        "base_url": "https://api.openai.com/v1",
        "chat_model": "gpt-4o",
        "embed_model": "text-embedding-3-small",
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    llm, embed_fn = _build_llm_and_embed(str(config_path))

    embed_client = embed_fn.__self__
    assert embed_client.base_url == "https://api.openai.com/v1"
    assert embed_client.api_key == "sk-shared-key"
    assert llm.base_url == embed_client.base_url
    assert llm.api_key == embed_client.api_key


def test_embed_api_key_env_fallback(tmp_path, monkeypatch):
    """embed_api_key falls back to the EMBED_API_KEY env var (before the
    chat api_key) when config.json omits embed_api_key."""
    cfg = {
        "api_key": "sk-deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "chat_model": "deepseek-v4-pro",
        "embed_base_url": "https://api.openai.com/v1",
        "embed_model": "text-embedding-3-small",
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")
    monkeypatch.setenv("EMBED_API_KEY", "sk-env-embed-key")

    _llm, embed_fn = _build_llm_and_embed(str(config_path))
    embed_client = embed_fn.__self__
    assert embed_client.api_key == "sk-env-embed-key"


def test_embed_api_key_never_in_snapshot(tmp_path):
    """_llm_config_snapshot must never leak embed_api_key (or any api key)
    into config_snapshot.yaml."""
    cfg = {
        "api_key": "sk-deepseek-chat-SECRET",
        "base_url": "https://api.deepseek.com/v1",
        "chat_model": "deepseek-v4-pro",
        "embed_api_key": "sk-openai-embed-SECRET",
        "embed_base_url": "https://api.openai.com/v1",
        "embed_model": "text-embedding-3-small",
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(cfg), encoding="utf-8")

    llm, embed_fn = _build_llm_and_embed(str(config_path))
    snapshot = _llm_config_snapshot(llm, embed_fn)

    assert "embed_api_key" not in snapshot
    assert "api_key" not in snapshot
    snapshot_str = json.dumps(snapshot)
    assert "sk-deepseek-chat-SECRET" not in snapshot_str
    assert "sk-openai-embed-SECRET" not in snapshot_str
    # Sanity: the non-secret metadata we DO expect is still there.
    assert snapshot["chat_model"] == "deepseek-v4-pro"
    assert snapshot["embed_model"] == "text-embedding-3-small"

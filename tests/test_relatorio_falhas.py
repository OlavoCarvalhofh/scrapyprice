"""
Testa crawler/relatorio_falhas.py -- grava/remove logs/urls_quebradas/<site>.json
isolado num diretório temporário (não deve tocar o logs/ real do projeto).
"""
import json

from crawler import relatorio_falhas


def test_salvar_grava_arquivo_com_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(relatorio_falhas, "_DIR", str(tmp_path))
    falhas = [{"url": "http://a.com/1", "motivo": "sem_preco"}]

    relatorio_falhas.salvar("siteteste", falhas)

    caminho = tmp_path / "siteteste.json"
    assert caminho.exists()
    payload = json.loads(caminho.read_text(encoding="utf-8"))
    assert payload["site"] == "siteteste"
    assert payload["total"] == 1
    assert payload["urls"] == falhas
    assert "gerado_em" in payload


def test_salvar_sem_falhas_remove_arquivo_existente(tmp_path, monkeypatch):
    monkeypatch.setattr(relatorio_falhas, "_DIR", str(tmp_path))
    caminho = tmp_path / "siteteste.json"
    caminho.write_text("{}", encoding="utf-8")

    relatorio_falhas.salvar("siteteste", [])

    assert not caminho.exists()


def test_salvar_sem_falhas_e_sem_arquivo_previo_nao_quebra(tmp_path, monkeypatch):
    monkeypatch.setattr(relatorio_falhas, "_DIR", str(tmp_path))
    relatorio_falhas.salvar("siteteste", [])
    assert list(tmp_path.iterdir()) == []

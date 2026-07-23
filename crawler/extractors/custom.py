"""
Fallback por seletor CSS, para os poucos sites que não expõem dado
estruturado -- ou para completar campos que o structured não trouxe
(ex: preço "de" riscado, parcelamento).

Os seletores ficam em config/selectors.yaml, casados por domínio.
Assim você adiciona um site novo editando YAML, sem tocar em código.
"""
import os

import yaml
from parsel import Selector

from .structured import _norm_availability, _to_float

_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "selectors.yaml"
)


def _load_config():
    if not os.path.exists(_CONFIG_PATH):
        return {}
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_custom(html, domain):
    cfg = _load_config().get(domain)
    if not cfg:
        return {}

    sel = Selector(text=html)
    out = {}
    for field, css in cfg.items():
        value = sel.css(css).get()
        if value is None:
            continue
        value = value.strip()
        if field in ("preco", "preco_de", "preco_a_vista", "parcela_valor"):
            value = _to_float(value)
        elif field == "disponibilidade":
            value = _norm_availability(value)
        out[field] = value

    if out:
        out["fonte_extracao"] = "css"
    return {k: v for k, v in out.items() if v is not None}

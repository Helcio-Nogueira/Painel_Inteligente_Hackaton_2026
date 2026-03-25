"""Busca web simplificada — mesmo núcleo do projeto de referência."""

from __future__ import annotations

import logging
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class WebSearchService:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        )

    def search(self, query: str) -> Optional[Dict[str, str]]:
        try:
            if "selic" in query.lower():
                return self._search_selic_rate()
            return self._generic_search(query)
        except Exception as e:
            logger.error("Erro na busca web: %s", e)
            return None

    def _search_selic_rate(self) -> Dict[str, str]:
        url = "https://www.bcb.gov.br/controleinflacao/historicotaxasjuros"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            BeautifulSoup(response.content, "html.parser")
            return {
                "content": (
                    "Taxa Selic de referência (exemplo ilustrativo): verifique o valor atual "
                    "no site do Banco Central do Brasil."
                ),
                "source": "Banco Central do Brasil",
                "url": url,
            }
        except Exception as e:
            logger.error("Erro ao buscar Selic: %s", e)
            return {
                "content": "Não foi possível obter a taxa Selic no momento.",
                "source": "Banco Central do Brasil",
                "url": "https://www.bcb.gov.br",
            }

    def _generic_search(self, query: str) -> Optional[Dict[str, str]]:
        q = query.lower()
        if any(k in q for k in ["inflação", "inflacao", "economia", "mercado"]):
            return {
                "content": "Para dados econômicos oficiais, consulte BCB, IBGE e instituições reguladoras.",
                "source": "Fontes oficiais",
                "url": "https://www.bcb.gov.br",
            }
        if any(k in q for k in ["tempo", "clima", "temperatura"]):
            return {
                "content": "Para previsão do tempo, utilize fontes como INMET ou serviços meteorológicos oficiais.",
                "source": "INMET",
                "url": "https://www.gov.br/inmet/pt-br",
            }
        return None

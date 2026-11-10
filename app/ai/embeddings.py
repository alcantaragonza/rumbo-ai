import hashlib
import math
import re
from typing import Protocol


class EmbeddingClient(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]:
        ...


class HashEmbeddingClient:
    """Embedding determinista y local para no depender de otro proveedor.

    Es una bolsa de palabras con hashing; suficiente para el catálogo pequeño
    del proyecto y para probar la recuperación sin llamadas externas.
    """

    dimension = 384
    _token_pattern = re.compile(r"\w+", re.UNICODE)
    _stopwords = {
        "a",
        "al",
        "como",
        "con",
        "cuando",
        "de",
        "del",
        "donde",
        "dos",
        "el",
        "ella",
        "en",
        "es",
        "esta",
        "esto",
        "hay",
        "la",
        "las",
        "le",
        "les",
        "lo",
        "los",
        "mas",
        "me",
        "mi",
        "no",
        "o",
        "para",
        "pero",
        "por",
        "que",
        "se",
        "si",
        "son",
        "su",
        "te",
        "tu",
        "un",
        "una",
        "y",
        "yo",
        "qué",
        "cómo",
        "dónde",
        "cuándo",
        "cuál",
    }

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            for token in self._token_pattern.findall(text.lower()):
                if token in self._stopwords:
                    continue
                digest = hashlib.sha256(token.encode("utf-8")).digest()
                index = int.from_bytes(digest[:4], "big") % self.dimension
                sign = 1.0 if digest[4] % 2 == 0 else -1.0
                vector[index] += sign
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append([value / norm for value in vector])
        return vectors


def get_embedding_client() -> EmbeddingClient:
    return HashEmbeddingClient()

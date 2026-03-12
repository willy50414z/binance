from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "litellm_router.json"
_ROUTE_EMBEDDINGS_CACHE: dict[str, tuple[np.ndarray, ...]] = {}


@dataclass(slots=True)
class VectorizerConfig:
    analyzer: str
    ngram_range: tuple[int, int]


@dataclass(slots=True)
class RouteDefinition:
    target_model: str
    score_threshold: float
    utterances: list[str]


@dataclass(slots=True)
class LocalSemanticRouterConfig:
    vectorizer: VectorizerConfig
    default_model: str
    routes: list[RouteDefinition]

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "LocalSemanticRouterConfig":
        path = Path(config_path) if config_path else _CONFIG_PATH
        payload = json.loads(path.read_text(encoding="utf-8"))
        vectorizer_payload = payload["vectorizer"]
        return cls(
            vectorizer=VectorizerConfig(
                analyzer=vectorizer_payload["analyzer"],
                ngram_range=tuple(vectorizer_payload["ngram_range"]),
            ),
            default_model=payload["default_model"],
            routes=[
                RouteDefinition(
                    target_model=item["target_model"],
                    score_threshold=float(item["score_threshold"]),
                    utterances=item["utterances"],
                )
                for item in payload["routes"]
            ],
        )


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return vectors / norms


@lru_cache(maxsize=8)
def _build_vectorizer(config_key: str) -> tuple[LocalSemanticRouterConfig, TfidfVectorizer]:
    config = LocalSemanticRouterConfig.load(config_key)
    utterances = [utterance for route in config.routes for utterance in route.utterances]
    vectorizer = TfidfVectorizer(
        analyzer=config.vectorizer.analyzer,
        ngram_range=config.vectorizer.ngram_range,
        lowercase=True,
    )
    vectorizer.fit(utterances)
    return config, vectorizer


@lru_cache(maxsize=8)
def _get_route_embeddings(config_key: str) -> tuple[np.ndarray, ...]:
    config, vectorizer = _build_vectorizer(config_key)
    route_embeddings: list[np.ndarray] = []
    for route in config.routes:
        route_vectors = vectorizer.transform(route.utterances).toarray().astype(np.float32)
        route_embeddings.append(_normalize_vectors(route_vectors))
    _ROUTE_EMBEDDINGS_CACHE[config_key] = tuple(route_embeddings)
    return _ROUTE_EMBEDDINGS_CACHE[config_key]


def select_model_for_prompt(prompt: str, config_path: str | Path | None = None) -> str:
    if not prompt.strip():
        raise ValueError("prompt must not be empty.")

    resolved_path = str(Path(config_path).resolve()) if config_path else str(_CONFIG_PATH.resolve())
    config, vectorizer = _build_vectorizer(resolved_path)
    route_embeddings = _get_route_embeddings(resolved_path)

    prompt_vector = vectorizer.transform([prompt]).toarray().astype(np.float32)
    prompt_embedding = _normalize_vectors(prompt_vector)[0]

    selected_model = config.default_model
    best_score = float("-inf")
    for route, embeddings in zip(config.routes, route_embeddings):
        score = float(np.max(embeddings @ prompt_embedding))
        if score >= route.score_threshold and score > best_score:
            selected_model = route.target_model
            best_score = score

    return selected_model

"""整合層提案 §11.5：embedding 雲端實作。用 FakeAzureTransport 假造 Azure 的回應，不連網路。"""

from urllib.parse import urlparse

import pytest

from app.integrations.embedding import EmbeddingError, EmbeddingUnavailable
from app.integrations.embedding.cloud import MAX_TEXTS_PER_REQUEST, CloudEmbeddingProvider
from tests.integrations.fake_azure import (
    FakeAzureTransport,
    embeddings_response,
    transient_failures,
)

ENDPOINT = "https://example.openai.azure.com/openai/v1/"
DEPLOYMENT = "test-embedding"
DIM = 4


def make_provider(transport: FakeAzureTransport) -> CloudEmbeddingProvider:
    return CloudEmbeddingProvider(
        endpoint=ENDPOINT,
        api_key="test-key",
        model=DEPLOYMENT,
        dim=DIM,
        http_client=transport.client(),
    )


def vector_by_text(_: int, text: str) -> list[float]:
    """文字 "t7" 得到 [8.0, 1.0, 1.0, 1.0]，用第 1 個數字確認順序。"""
    return [float(int(text.removeprefix("t")) + 1), 1.0, 1.0, 1.0]


def test_embed_sends_deployment_and_dimensions_and_keeps_input_order() -> None:
    transport = FakeAzureTransport([embeddings_response(vector_by_text, reverse_order=True)])

    vectors = make_provider(transport).embed(["t0", "t1", "t2"])

    request = transport.requests[0]
    assert urlparse(str(request.url)).path == "/openai/v1/embeddings"
    body = transport.json_body()
    assert body["model"] == DEPLOYMENT
    assert body["dimensions"] == DIM
    assert body["input"] == ["t0", "t1", "t2"]
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0]
    assert all(len(vector) == DIM for vector in vectors)


def test_embed_splits_requests_over_the_per_request_limit() -> None:
    texts = [f"t{i}" for i in range(MAX_TEXTS_PER_REQUEST + 1)]
    transport = FakeAzureTransport(
        [embeddings_response(vector_by_text), embeddings_response(vector_by_text)]
    )

    vectors = make_provider(transport).embed(texts)

    assert len(transport.requests) == 2
    assert len(transport.json_body(0)["input"]) == MAX_TEXTS_PER_REQUEST
    assert transport.json_body(1)["input"] == [f"t{MAX_TEXTS_PER_REQUEST}"]
    assert [vector[0] for vector in vectors] == [float(i + 1) for i in range(len(texts))]


def test_zero_vector_raises_embedding_error() -> None:
    transport = FakeAzureTransport([embeddings_response(lambda _i, _t: [0.0] * DIM)])

    with pytest.raises(EmbeddingError):
        make_provider(transport).embed(["t0"])


def test_wrong_dimension_raises_embedding_error() -> None:
    transport = FakeAzureTransport([embeddings_response(lambda _i, _t: [1.0] * (DIM - 1))])

    with pytest.raises(EmbeddingError):
        make_provider(transport).embed(["t0"])


@pytest.mark.parametrize("kind", ["429", "500", "503", "timeout"])
def test_transient_errors_raise_embedding_unavailable_after_sdk_retries(kind: str) -> None:
    transport = FakeAzureTransport(transient_failures(kind))

    with pytest.raises(EmbeddingUnavailable):
        make_provider(transport).embed(["t0"])
    assert len(transport.requests) == 3  # 第 1 次加上 SDK 重試 2 次

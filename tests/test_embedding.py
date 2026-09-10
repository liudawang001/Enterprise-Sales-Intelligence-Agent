from app.providers.embedding.fake import DeterministicFakeEmbedding


def test_fake_embedding_is_deterministic_and_normalized() -> None:
    provider = DeterministicFakeEmbedding(dimension=32)
    first = provider.embed_query("集团V网")
    second = provider.embed_query("集团V网")
    assert first == second
    assert len(first) == 32
    assert max(first) <= 1

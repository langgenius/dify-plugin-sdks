from dify_plugin.interfaces.model.openai_compatible import common


def test_join_endpoint_url_normalizes_single_separator() -> None:
    compat = common._CommonOaiApiCompat()

    assert (
        compat._join_endpoint_url("https://example.com/v1", "embeddings")
        == "https://example.com/v1/embeddings"
    )
    assert (
        compat._join_endpoint_url("https://example.com/v1/", "audio/speech")
        == "https://example.com/v1/audio/speech"
    )
    assert compat._join_endpoint_url("", "embeddings") == "/embeddings"

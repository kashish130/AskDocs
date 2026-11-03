import pytest

from app.chunking import chunk_text


def test_empty_text_returns_empty_list() -> None:
    assert chunk_text("") == []
    assert chunk_text(" \n\t  ") == []


def test_short_text_fits_in_one_chunk() -> None:
    text = "Short text"
    chunks = chunk_text(text, chunk_size=800)
    assert chunks == [text]


def test_whitespace_is_normalized() -> None:
    text = "This   is  a   test.\n\nNew line here."
    expected = "This is a test. New line here."
    chunks = chunk_text(text, chunk_size=800)
    assert chunks == [expected]


def test_long_text_is_chunked_correctly() -> None:
    text = "A" * 2000  # 2000 characters of 'A'
    chunks = chunk_text(text, chunk_size=800, overlap=100)
    assert len(chunks) == 3
    assert all(len(chunk) <= 800 for chunk in chunks)


def test_invalid_chunk_overlap_raises() -> None:
    with pytest.raises(ValueError):
        chunk_text("Some text", chunk_size=100, overlap=100)
    with pytest.raises(ValueError):
        chunk_text("Some text", chunk_size=100, overlap=-1)


def test_invalid_chunk_size_raises() -> None:
    with pytest.raises(ValueError, match="chunk_size must be a positive integer."):
        chunk_text("Some text", chunk_size=0)
    with pytest.raises(ValueError, match="chunk_size must be a positive integer."):
        chunk_text("Some text", chunk_size=-10)

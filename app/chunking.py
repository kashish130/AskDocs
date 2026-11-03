def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Chunk text into smaller pieces with optional overlap.

    Args:
        text (str): The input text to be chunked.
        chunk_size (int): The maximum size of each chunk.
        overlap (int): The number of overlapping characters between chunks.

    Returns:
        list[str]: A list of text chunks.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be a non-negative integer less than chunk_size.")
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks: list[str] = []
    start = 0
    step = chunk_size - overlap
    text_length = len(cleaned)
    while start < text_length:
        end = min(start + chunk_size, text_length)
        chunks.append(cleaned[start:end])
        if end == text_length:
            break
        start += step
    return chunks

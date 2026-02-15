import re
from urllib.parse import unquote

# RFC 3986 reserved characters percent-encoding
RESERVED_PERCENT_ENCODINGS = frozenset(
    {
        "%2f",
        "%2F",
        "%3f",
        "%3F",
        "%23",
        "%26",
        "%3d",
        "%3D",
        "%40",
        "%3a",
        "%3A",
        "%5b",
        "%5B",
        "%5d",
        "%5D",
        "%21",
        "%24",
        "%27",
        "%28",
        "%29",
        "%2a",
        "%2A",
        "%2b",
        "%2B",
        "%2c",
        "%2C",
        "%3b",
        "%3B",
        "%25",
        "%20",
    }
)


def safe_unquote(url: str) -> str:
    """
    Safely decode URL-encoded strings, only decoding characters that won't alter URL semantics.
    """
    if not url:
        return url

    result = []
    i = 0
    n = len(url)

    while i < n:
        if url[i] == "%" and i + 2 < n:
            hex_chars = url[i + 1 : i + 3]
            if all(c in "0123456789ABCDEFabcdef" for c in hex_chars):
                percent_encoded = url[i : i + 3]

                if percent_encoded in RESERVED_PERCENT_ENCODINGS:
                    result.append(percent_encoded)
                    i += 3
                    continue

                encoded_sequence = percent_encoded
                j = i + 3
                while j + 2 < n and url[j] == "%":
                    next_hex = url[j + 1 : j + 3]
                    if all(c in "0123456789ABCDEFabcdef" for c in next_hex):
                        next_encoded = url[j : j + 3]
                        if next_encoded in RESERVED_PERCENT_ENCODINGS:
                            break
                        encoded_sequence += next_encoded
                        j += 3
                    else:
                        break

                try:
                    decoded = unquote(encoded_sequence)
                    result.append(decoded)
                    i = j
                    continue
                except Exception:
                    result.append(percent_encoded)
                    i += 3
                    continue

        result.append(url[i])
        i += 1

    return "".join(result)


def decode_http_urls_in_dict(data):
    """
    Traverse all values in the data structure:
    - If it's a string starting with http, apply safe_unquote
    - If it's a list, recursively process each element
    - If it's a dict, recursively process each value
    """
    if isinstance(data, str):
        if "%" in data and "http" in data:
            return safe_unquote(data)
        else:
            return data
    elif isinstance(data, list):
        return [decode_http_urls_in_dict(item) for item in data]
    elif isinstance(data, dict):
        return {key: decode_http_urls_in_dict(value) for key, value in data.items()}
    else:
        return data


def is_huggingface_dataset_or_space_url(url):
    """Check if the URL is a HuggingFace dataset or space URL."""
    if not url:
        return False
    return "huggingface.co/datasets" in url or "huggingface.co/spaces" in url

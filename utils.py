import re


def is_url(text):
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    simple_patterns = [
        r'^https?://\S+',
        r'^www\.\S+',
        r'^\S+\.(com|ru|org|net|info|io|edu|gov|mil|biz|name|museum|co|uk|de|fr|jp|it|cn|br|au|us|ca|eu)\S*'
    ]

    if url_pattern.match(text):
        return True

    for pattern in simple_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True

    return False


def format_size(size):
    if size < 1024:
        return f"{size} Б"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} МБ"
    else:
        return f"{size / (1024 * 1024 * 1024):.2f} ГБ"

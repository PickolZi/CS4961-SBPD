import re

from models import SmartsheetContact

def replace_email_template_placeholders(html_text: str, contact: SmartsheetContact) -> str:
    """
    Replaces all ${KEY} occurrences in `text` using the `contact` dictionary.
    If a KEY is not found in the dictionary, the placeholder is left unchanged.
    Capitaliziation does not matter, however, spacing and color does. Make sure the document has no spaces between the
    braces and make sure the braces along with the rest of the key are the same color, font, and size.
    """
    pattern = re.compile(r"\$\{([^}]+)\}")

    def replacer(match: re.Match) -> str:
        key = match.group(1)

        for k,v in vars(contact).items():
            if k.lower() == key.lower():
                return str(v)
        return match.group(0)

    return pattern.sub(replacer, html_text)
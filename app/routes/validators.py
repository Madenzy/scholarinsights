import re
import secrets
import string

PASSWORD_REQUIREMENTS = (
    'Password must be at least 12 characters long and include an uppercase letter, '
    'a lowercase letter, a number, and a special character.'
)

_SPECIAL_CHARS = '!@#$%^&*?-_'


def password_error(password):
    """Return an error message if the password fails the policy, else None."""
    if not password or len(password) < 12:
        return PASSWORD_REQUIREMENTS
    if not re.search(r'[A-Z]', password):
        return PASSWORD_REQUIREMENTS
    if not re.search(r'[a-z]', password):
        return PASSWORD_REQUIREMENTS
    if not re.search(r'\d', password):
        return PASSWORD_REQUIREMENTS
    if not re.search(r'[^A-Za-z0-9]', password):
        return PASSWORD_REQUIREMENTS
    return None


def generate_password(length=14):
    """Generate a random password that satisfies password_error()'s policy."""
    required = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SPECIAL_CHARS),
    ]
    alphabet = string.ascii_uppercase + string.ascii_lowercase + string.digits + _SPECIAL_CHARS
    chars = required + [secrets.choice(alphabet) for _ in range(length - len(required))]
    for i in range(len(chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return ''.join(chars)

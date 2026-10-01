import re

PASSWORD_REQUIREMENTS = (
    'Password must be at least 12 characters long and include an uppercase letter, '
    'a lowercase letter, a number, and a special character.'
)


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

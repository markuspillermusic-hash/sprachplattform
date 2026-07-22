import secrets
import string


TEMPORARY_PASSWORD_LENGTH = 18
TEMPORARY_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_.!"


def generate_temporary_password(length=TEMPORARY_PASSWORD_LENGTH):
    """Generate a one-time password without persisting its plain text."""
    if length < 14:
        raise ValueError("Temporäre Passwörter müssen mindestens 14 Zeichen lang sein.")
    return "".join(secrets.choice(TEMPORARY_PASSWORD_ALPHABET) for _ in range(length))


def reset_temporary_password(user):
    password = generate_temporary_password()
    user.set_password(password)
    user.must_change_password = True
    user.save(update_fields=["password", "must_change_password"])
    return password


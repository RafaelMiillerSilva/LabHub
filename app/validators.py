"""
Validadores customizados do LabHub.
"""

from django.core import validators
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class CustomUnicodeUsernameValidator(validators.RegexValidator):
    """
    Validador de nome de usuário que permite letras, números, espaços
    e os caracteres @/./+/-/_.
    """
    regex = r"^[\w.@+\- ]+$"
    message = _(
        "Informe um nome de usuário válido. Este valor pode conter apenas letras, "
        "números, espaços e os caracteres @/./+/-/_."
    )
    flags = 0


custom_username_validator = CustomUnicodeUsernameValidator()

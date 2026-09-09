from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'app'
    verbose_name = 'LabHub - Sistema de Gestão'

    def ready(self):
        # Importa os sinais quando o app estiver pronto
        import app.signals  # noqa

        # Configura o validador do User.username para permitir espaços
        from django.contrib.auth.models import User
        from django.contrib.auth.validators import UnicodeUsernameValidator, ASCIIUsernameValidator
        from app.validators import custom_username_validator

        username_field = User._meta.get_field('username')
        validators_list = [
            v for v in getattr(username_field, '_validators', [])
            if not isinstance(v, (UnicodeUsernameValidator, ASCIIUsernameValidator))
        ] + [custom_username_validator]
        setattr(username_field, '_validators', validators_list)
        username_field.__dict__.pop('validators', None)

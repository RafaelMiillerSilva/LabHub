from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    default_auto_field = 'django.db.models.AutoField'
    name = 'app'
    verbose_name = 'LabHub - Sistema de Gestão'

    def ready(self):
        # Importa os sinais quando o app estiver pronto
        import app.signals  # noqa

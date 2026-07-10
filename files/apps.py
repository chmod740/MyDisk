from django.apps import AppConfig


class FilesConfig(AppConfig):
    name = 'files'

    def ready(self):
        import files.signals

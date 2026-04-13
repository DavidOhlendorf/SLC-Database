from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class WaveDocumentStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs["location"] = settings.PRIVATE_UPLOAD_ROOT / "wave_documents"
        super().__init__(*args, **kwargs)


wave_document_storage = WaveDocumentStorage()
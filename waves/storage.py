from django.conf import settings
from django.core.files.storage import FileSystemStorage


wave_document_storage = FileSystemStorage(
    location=settings.PRIVATE_UPLOAD_ROOT / "wave_documents"
)
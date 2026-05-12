class STTError(Exception):
    pass

class DownloadError(STTError):
    pass

class ProcessingError(STTError):
    pass

class TranscriptionError(STTError):
    pass
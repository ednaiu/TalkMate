# Английские тексты ошибок по их кодам. Сообщение без перевода уходит как есть.
ENGLISH = {
    "invalid_email": "Enter a valid email address",
    "invalid_name": "Enter your name (up to 120 characters)",
    "weak_password": "The password must be at least 6 characters long",
    "invalid_birth_date": "Check the date of birth",
    "invalid_gender": "Gender must be male or female",
    "email_taken": "A user with this email is already registered",
    "invalid_credentials": "Wrong email or password",
    "unauthorized": "Your session has expired, please log in again",
    "bad_request": "A JSON object is expected",
    "forbidden": "Administrator rights are required",
    "not_found": "Not found",
    "invalid_code": "The code is wrong or has expired. Request a new one",
    "mail_unavailable": "Could not send the email. Try again later",
    "no_audio": "No audio file was sent",
    "bad_audio_format": "This file format is not supported",
    "bad_slides_format": "The presentation must be attached as a PDF",
    "bad_audio": "Could not read the recording: it must contain at least one second of speech",
    "recognition_unavailable": "The speech recognition service is unavailable",
    "invalid_metric": "Unknown metric",
    "invalid_verdict": "The rating must be correct or wrong",
    "invalid_comment": "The comment must be a string of up to 500 characters",
    "invalid_consent": "share_recordings must be true or false",
    "analysis_unavailable": "The speech analysis server is unavailable",
    "no_signal": "The microphone sent no sound: the recording is silent. Check microphone access",
    "no_speech": "Could not recognize any speech. Speak closer to the microphone",
    "method_not_allowed": "Method not allowed",
    "request_entity_too_large": "The file is too large",
    "internal": "Internal server error",
}


def localized(code, message, language):
    """Сообщение об ошибке на языке интерфейса."""
    return ENGLISH.get(code, message) if language == "en" else message


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message

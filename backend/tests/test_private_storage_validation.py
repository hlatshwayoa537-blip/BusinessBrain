import io
import zipfile
import zlib

import pytest
from fastapi import HTTPException

from app.services import private_storage


class FakeS3:
    def __init__(self, payload):
        self.payload = payload

    def get_object(self, **kwargs):
        return {"Body": io.BytesIO(self.payload)}


def validate(monkeypatch, payload, extension):
    monkeypatch.setattr(private_storage, "s3_client", lambda: FakeS3(payload))
    private_storage.validate_object_content("quarantine/test", extension)


def make_png():
    signature = bytes.fromhex("89504e470d0a1a0a")
    ihdr_data = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    ihdr = len(ihdr_data).to_bytes(4, "big") + b"IHDR" + ihdr_data
    crc = (zlib.crc32(b"IHDR" + ihdr_data) & 0xFFFFFFFF).to_bytes(4, "big")
    return signature + ihdr + crc


def make_ooxml(extension):
    required, content_type = private_storage.OOXML_REQUIRED_PARTS[extension]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b'<Types><Override PartName="/' + required.encode() + b'" ContentType="' + content_type + b'"/></Types>')
        archive.writestr(required, b"<document/>")
    return buffer.getvalue()


def test_pdf_requires_header_and_end_marker(monkeypatch):
    validate(monkeypatch, b"%PDF-1.7\nbody\n%%EOF", ".pdf")
    with pytest.raises(HTTPException) as error:
        validate(monkeypatch, b"%PDF-1.7\nbody without end marker", ".pdf")
    assert error.value.status_code == 422


def test_png_checks_real_signature_and_ihdr_integrity(monkeypatch):
    validate(monkeypatch, make_png(), ".png")
    forged = b"not really png" + make_png()
    with pytest.raises(HTTPException):
        validate(monkeypatch, forged, ".png")
    corrupt_crc = make_png()[:-1] + bytes([make_png()[-1] ^ 0xFF])
    with pytest.raises(HTTPException):
        validate(monkeypatch, corrupt_crc, ".png")


def test_jpeg_requires_soi_and_eoi_markers(monkeypatch):
    validate(monkeypatch, bytes.fromhex("ffd8ff") + b"image-data" + bytes.fromhex("ffd9"), ".jpg")
    with pytest.raises(HTTPException):
        validate(monkeypatch, bytes.fromhex("ffd8ff") + b"truncated", ".jpg")


@pytest.mark.parametrize("extension", [".docx", ".xlsx", ".pptx"])
def test_ooxml_files_require_the_correct_package_content_type(monkeypatch, extension):
    validate(monkeypatch, make_ooxml(extension), extension)
    wrong_type = make_ooxml(".docx")
    with pytest.raises(HTTPException):
        validate(monkeypatch, wrong_type, ".xlsx")


def test_ooxml_rejects_macro_payloads_and_compression_bombs(monkeypatch):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b'<Types><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("word/document.xml", b"<document/>")
        archive.writestr("word/vbaProject.bin", b"macro")
    with pytest.raises(HTTPException):
        validate(monkeypatch, buffer.getvalue(), ".docx")

    bomb = io.BytesIO()
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", b'<Types><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        archive.writestr("word/document.xml", b"A" * 500_000)
    with pytest.raises(HTTPException):
        validate(monkeypatch, bomb.getvalue(), ".docx")


def test_text_files_must_be_nonempty_utf8_without_null_bytes(monkeypatch):
    validate(monkeypatch, b"Supplier invoice,123.45\n", ".csv")
    with pytest.raises(HTTPException):
        validate(monkeypatch, b"\xff\xfe\x00", ".txt")
    with pytest.raises(HTTPException):
        validate(monkeypatch, b"", ".txt")


def test_content_validation_enforces_actual_download_size_limit(monkeypatch):
    with pytest.raises(HTTPException) as error:
        validate(monkeypatch, b"x" * (private_storage.MAX_EVIDENCE_BYTES + 1), ".txt")
    assert error.value.status_code == 413

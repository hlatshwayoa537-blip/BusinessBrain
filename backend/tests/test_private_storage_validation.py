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


def png_chunk(kind, payload):
    crc = (zlib.crc32(kind + payload) & 0xFFFFFFFF).to_bytes(4, "big")
    return len(payload).to_bytes(4, "big") + kind + payload + crc


def make_png():
    signature = bytes.fromhex("89504e470d0a1a0a")
    ihdr_data = (1).to_bytes(4, "big") + (1).to_bytes(4, "big") + bytes([8, 2, 0, 0, 0])
    return (
        signature
        + png_chunk(b"IHDR", ihdr_data)
        + png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
        + png_chunk(b"IEND", b"")
    )


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
    sof = bytes.fromhex("ffc0") + bytes.fromhex("000b") + bytes([8, 0, 1, 0, 1, 1, 1, 0x11, 0])
    sos = bytes.fromhex("ffda") + bytes.fromhex("0008") + bytes([1, 1, 0, 0, 0x3f, 0])
    valid_jpeg = bytes.fromhex("ffd8") + sof + sos + b"\x00" + bytes.fromhex("ffd9")
    validate(monkeypatch, valid_jpeg, ".jpg")
    with pytest.raises(HTTPException):
        validate(monkeypatch, valid_jpeg[:-2], ".jpg")


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


class FakeClamSocket:
    def __init__(self, replies):
        self.replies = list(replies)
        self.sent = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def settimeout(self, value):
        self.timeout = value

    def sendall(self, value):
        self.sent.append(value)

    def recv(self, size):
        return self.replies.pop(0) if self.replies else b""


@pytest.mark.parametrize(
    ("replies", "expected_status"),
    [
        ([b"stream: ", b"OK\\n"], None),
        ([b"stream: Eicar-Test-Signature FOUND\\n"], 422),
        ([b"NOT OK\\n"], 503),
        ([b""], 503),
        ([b"stream: OK"], 503),
    ],
)
def test_clamav_requires_a_complete_explicit_clean_verdict(monkeypatch, replies, expected_status):
    monkeypatch.setattr(private_storage, "s3_client", lambda: FakeS3(b"safe evidence"))
    monkeypatch.setattr(private_storage.settings, "clamav_host", "scanner.internal")
    monkeypatch.setattr(private_storage.settings, "clamav_port", 3310)
    monkeypatch.setattr(private_storage.settings, "clamav_timeout_seconds", 5)
    fake_socket = FakeClamSocket(replies)
    monkeypatch.setattr(private_storage.socket, "create_connection", lambda *args, **kwargs: fake_socket)

    if expected_status is None:
        private_storage.scan_object_with_clamav("quarantine/test")
    else:
        with pytest.raises(HTTPException) as error:
            private_storage.scan_object_with_clamav("quarantine/test")
        assert error.value.status_code == expected_status


def test_ooxml_rejects_corrupt_document_member_crc(monkeypatch):
    payload = bytearray(make_ooxml(".docx"))
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        info = archive.getinfo("word/document.xml")
        data_offset = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    # Flip a compressed document byte without changing the central directory.
    payload[data_offset] ^= 0x01
    with pytest.raises(HTTPException) as error:
        validate(monkeypatch, bytes(payload), ".docx")
    assert error.value.status_code == 422

import io
import socket
import struct
import zipfile
from functools import lru_cache

import boto3
from botocore.config import Config
from fastapi import HTTPException

from app.core.config import settings

MAX_EVIDENCE_BYTES = 25 * 1024 * 1024
MAX_ARCHIVE_ENTRIES = 10_000
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
MAX_ARCHIVE_COMPRESSION_RATIO = 100
OOXML_REQUIRED_PARTS = {
    ".docx": ("word/document.xml", b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"),
    ".xlsx": ("xl/workbook.xml", b"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
    ".pptx": ("ppt/presentation.xml", b"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"),
}
OOXML_MACRO_PARTS = {"word/vbaProject.bin", "xl/vbaProject.bin", "ppt/vbaProject.bin"}


@lru_cache(maxsize=1)
def s3_client():
    if not all([settings.s3_bucket, settings.s3_access_key_id, settings.s3_secret_access_key]):
        raise HTTPException(status_code=503, detail="Private document storage is not configured.")
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def presigned_upload(key: str, content_type: str, max_bytes: int) -> dict:
    return s3_client().generate_presigned_post(
        Bucket=settings.s3_bucket,
        Key=key,
        Fields={"Content-Type": content_type},
        Conditions=[{"Content-Type": content_type}, ["content-length-range", 1, max_bytes]],
        ExpiresIn=settings.s3_upload_url_expire_seconds,
    )


def object_head(key: str):
    return s3_client().head_object(Bucket=settings.s3_bucket, Key=key)


def _valid_ooxml(data: bytes, extension: str) -> bool:
    required_part, required_content_type = OOXML_REQUIRED_PARTS[extension]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ARCHIVE_ENTRIES:
                return False
            if any(info.flag_bits & 0x1 for info in infos):
                return False
            if any(info.filename in OOXML_MACRO_PARTS for info in infos):
                return False
            names = {info.filename for info in infos}
            if "[Content_Types].xml" not in names or required_part not in names:
                return False
            total_uncompressed = sum(info.file_size for info in infos)
            if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                return False
            for info in infos:
                if info.file_size and (
                    info.compress_size == 0
                    or info.file_size / info.compress_size > MAX_ARCHIVE_COMPRESSION_RATIO
                ):
                    return False
            if len(names) != len(infos):
                return False
            # Verify CRCs for every member, including the actual document body.
            # testzip streams members and catches corrupt/truncated ZIP payloads.
            if archive.testzip() is not None:
                return False
            content_types = archive.read("[Content_Types].xml")
            # Require the correct OOXML main-part content type, not just a ZIP
            # containing a conveniently named XML file.
            return required_content_type in content_types
    except (zipfile.BadZipFile, OSError, KeyError, RuntimeError, ValueError):
        return False


def _valid_png(data: bytes) -> bool:
    import zlib

    signature = bytes.fromhex("89504e470d0a1a0a")
    if not data.startswith(signature):
        return False
    offset = len(signature)
    chunk_count = 0
    seen_header = seen_image_data = seen_end = False
    width = height = 0
    while offset + 12 <= len(data):
        chunk_count += 1
        if chunk_count > 10_000:
            return False
        length = int.from_bytes(data[offset:offset + 4], "big")
        chunk_type = data[offset + 4:offset + 8]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            return False
        chunk_payload = data[offset + 8:offset + 8 + length]
        expected_crc = int.from_bytes(data[offset + 8 + length:chunk_end], "big")
        if zlib.crc32(chunk_type + chunk_payload) & 0xFFFFFFFF != expected_crc:
            return False
        if not seen_header:
            if chunk_type != b"IHDR" or length != 13:
                return False
            width = int.from_bytes(chunk_payload[0:4], "big")
            height = int.from_bytes(chunk_payload[4:8], "big")
            if not (0 < width <= 50_000 and 0 < height <= 50_000 and width * height <= 100_000_000):
                return False
            seen_header = True
        elif chunk_type == b"IHDR":
            return False
        if chunk_type == b"IDAT":
            seen_image_data = True
        if chunk_type == b"IEND":
            if length != 0 or not seen_image_data:
                return False
            seen_end = True
            offset = chunk_end
            break
        offset = chunk_end
    return seen_header and seen_image_data and seen_end and offset == len(data)


def _valid_jpeg(data: bytes) -> bool:
    if len(data) < 12 or not data.startswith(bytes.fromhex("ffd8")) or not data.endswith(bytes.fromhex("ffd9")):
        return False
    offset = 2
    found_frame = False
    while offset < len(data) - 2:
        if data[offset] != 0xFF:
            return False
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            return False
        marker = data[offset]
        offset += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            continue
        if offset + 2 > len(data):
            return False
        segment_length = int.from_bytes(data[offset:offset + 2], "big")
        if segment_length < 2 or offset + segment_length > len(data):
            return False
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if segment_length < 8:
                return False
            height = int.from_bytes(data[offset + 3:offset + 5], "big")
            width = int.from_bytes(data[offset + 5:offset + 7], "big")
            components = data[offset + 7]
            if not (0 < width <= 50_000 and 0 < height <= 50_000 and width * height <= 100_000_000 and components > 0):
                return False
            found_frame = True
        if marker == 0xDA:
            return found_frame and data.endswith(bytes.fromhex("ffd9"))
        offset += segment_length
    return False


def _matches_file_signature(data: bytes, extension: str) -> bool:
    if extension == ".pdf":
        return data[:1024].find(b"%PDF-") >= 0 and b"%%EOF" in data[-1024:]
    if extension == ".png":
        return _valid_png(data)
    if extension in {".jpg", ".jpeg"}:
        return _valid_jpeg(data)
    if extension in {".txt", ".csv"}:
        try:
            return b"\x00" not in data and bool(data.decode("utf-8-sig"))
        except UnicodeDecodeError:
            return False
    if extension in OOXML_REQUIRED_PARTS:
        return _valid_ooxml(data, extension)
    return False


def validate_object_content(key: str, extension: str) -> None:
    """Bound and inspect the actual uploaded bytes before malware scanning."""
    response = s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    try:
        body = response["Body"]
        chunks = []
        total = 0
        while True:
            chunk = body.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_EVIDENCE_BYTES:
                raise HTTPException(status_code=413, detail="Evidence file exceeds the 25 MB limit.")
            chunks.append(chunk)
        data = b"".join(chunks)
    finally:
        response["Body"].close()

    if not _matches_file_signature(data, extension):
        raise HTTPException(status_code=422, detail="File contents do not match the selected file type or are incomplete.")


def scan_object_with_clamav(key: str) -> None:
    if not settings.clamav_host:
        raise HTTPException(status_code=503, detail="Malware scanning is not configured. The file remains quarantined.")
    response = s3_client().get_object(Bucket=settings.s3_bucket, Key=key)
    try:
        with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=settings.clamav_timeout_seconds) as sock:
            sock.settimeout(settings.clamav_timeout_seconds)
            sock.sendall(b"zINSTREAM\0")
            body = response["Body"]
            while True:
                chunk = body.read(64 * 1024)
                if not chunk:
                    break
                sock.sendall(struct.pack("!I", len(chunk)) + chunk)
            sock.sendall(struct.pack("!I", 0))
            response_bytes = bytearray()
            while b"\\n" not in response_bytes:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response_bytes.extend(chunk)
                if len(response_bytes) > 4096:
                    break
            result = response_bytes.decode("utf-8", errors="replace").strip()
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Malware scanning service is unavailable. The file remains quarantined.") from exc
    finally:
        response["Body"].close()
    # Accept only ClamAV's explicit clean verdict. A response such as
    # "NOT OK", an empty response, or a truncated protocol reply must never
    # be interpreted as a successful scan.
    if result.endswith(" FOUND"):
        raise HTTPException(status_code=422, detail="The uploaded file failed the malware scan and cannot be shared.")
    if result not in {"stream: OK", "OK"}:
        raise HTTPException(status_code=503, detail="Malware scanner returned an invalid or incomplete response. The file remains quarantined.")


def promote_clean_object(source_key: str, destination_key: str) -> None:
    client = s3_client()
    client.copy_object(Bucket=settings.s3_bucket, Key=destination_key, CopySource={"Bucket": settings.s3_bucket, "Key": source_key}, MetadataDirective="COPY")
    client.delete_object(Bucket=settings.s3_bucket, Key=source_key)


def presigned_download(key: str, filename: str, content_type: str) -> str:
    return s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key, "ResponseContentDisposition": f'attachment; filename="{filename}"', "ResponseContentType": content_type},
        ExpiresIn=settings.s3_download_url_expire_seconds,
    )


def delete_object(key: str) -> None:
    s3_client().delete_object(Bucket=settings.s3_bucket, Key=key)

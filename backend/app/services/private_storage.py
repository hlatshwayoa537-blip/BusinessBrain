import socket
import struct
from functools import lru_cache

import boto3
from botocore.config import Config
from fastapi import HTTPException

from app.core.config import settings

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

def presigned_upload(key: str, content_type: str) -> str:
    return s3_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=settings.s3_upload_url_expire_seconds,
    )

def object_head(key: str):
    return s3_client().head_object(Bucket=settings.s3_bucket, Key=key)

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
            result = sock.recv(4096).decode("utf-8", errors="replace").strip()
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Malware scanning service is unavailable. The file remains quarantined.") from exc
    finally:
        response["Body"].close()
    if not result.endswith("OK"):
        raise HTTPException(status_code=422, detail="The uploaded file failed the malware scan and cannot be shared.")

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

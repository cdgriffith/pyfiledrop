#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from threading import Lock
from collections import defaultdict
import shutil
import argparse
import os
import hashlib
import time
from html import escape
import traceback
from email.utils import parseaddr
import uuid
import string

from bottle import route, run, request, error, HTTPError, static_file, HTTPResponse, template
import jwt
from werkzeug.utils import secure_filename
from PIL import Image
import pillow_avif  # Required for thumbnails, do not delete

storage_path: Path = Path(__file__).parent / "storage"
chunk_path: Path = Path(__file__).parent / "chunk"
thumbnail_path: Path = Path(__file__).parent / "thumbnail"
reported_path: Path = Path(__file__).parent / "reported"

site_name = "pyfiledrop"
allow_downloads = True
dropzone_cdn = "https://cdnjs.cloudflare.com/ajax/libs/dropzone"
dropzone_version = "5.7.6"
dropzone_timeout = "120000"
dropzone_max_file_size = "100000"
dropzone_chunk_size = "1000000"
dropzone_parallel_chunks = "true"
dropzone_force_chunking = "true"
dropzone_accepted_files = "image/*,.psd"

lock = Lock()
chucks = defaultdict(list)
secret = os.urandom(64)

pillow_image_types = (
    ".apng",
    ".avif",
    ".bmp",
    ".dib",
    ".gif",
    ".jfif",
    ".jpeg",
    ".jpg",
    ".png",
    ".psd",
    ".tga",
    ".tif",
    ".tiff",
    ".webp",
    ".xbm",
)

safe_chars = string.ascii_letters + string.digits + " !$%&'()*+,-.:;<=>?@[]^_`{|}~\n"


@error(400)
def handle_400(error_message):
    return HTTPResponse(status=400, body=f"Bad Parameter: {error_message}")


@error(403)
def handle_403(error_message):
    return HTTPResponse(status=403, body=f"Forbidden: {error_message}")


@error(500)
def handle_500(error_message):
    return HTTPResponse(status=500, body=f"Error: {error_message}")


@route("/")
def index():
    jwt_token = jwt.encode({"expires": int(time.time()) + 7 * 24 * 60 * 60}, key=secret, algorithm="HS256")
    index_file = Path(__file__).parent / "index.html"
    terms_file = Path(__file__).parent / "terms.html"
    terms = terms_file.read_text(encoding="utf-8", errors="ignore") if terms_file.exists() else ""
    terms = "".join([x for x in terms if x in safe_chars])
    return template(
        index_file.read_text(),
        jwt_token=jwt_token,
        site_name=site_name,
        dropzone_cdn=dropzone_cdn.rstrip("/"),
        dropzone_version=dropzone_version,
        allow_downloads="true" if allow_downloads else "false",
        dropzone_force_chunking=dropzone_force_chunking,
        dropzone_parallel_chunks=dropzone_parallel_chunks,
        dropzone_timeout=dropzone_timeout,
        dropzone_max_file_size=dropzone_max_file_size,
        dropzone_chunk_size=dropzone_chunk_size,
        dropzone_accepted_files=dropzone_accepted_files,
        terms_and_conditions=escape(terms).replace("\n", "--linebreak--"),
    )


@route("/favicon.ico")
def favicon():
    return (Path(__file__).parent / "favicon.ico").read_bytes()


def save_ip(ip_address, dz_uuid):
    return True
    # with lock:
    #     with open(Path(__file__).parent / "owners", "a") as f:
    #         f.write(f"{dz_uuid}\t{ip_address}")


@route("/upload", method="POST")
def upload():
    token = request.get_header("token")
    if not token:
        print(f"Client did not send a token header")
        raise HTTPError(status=403)
    try:
        jwt_payload = jwt.decode(jwt=token, key=secret, algorithms=["HS256"])
    except Exception as err:
        print(f"Client sent a bad payload: {err}")
        raise HTTPError(status=403)
    else:
        if "expires" not in jwt_payload or jwt_payload["expires"] < time.time():
            raise HTTPError(status=403, body="Please reload page")

    file = request.files.get("file")
    if not file:
        raise HTTPError(status=400, body="No file provided")

    client_ip = request.environ.get("HTTP_X_FORWARDED_FOR", request.environ.get("REMOTE_ADDR"))

    # Chunked download
    try:
        dz_uuid = request.forms["dzuuid"]
        current_chunk = int(request.forms["dzchunkindex"])
        total_chunks = int(request.forms["dztotalchunkcount"])
    except KeyError as err:
        raise HTTPError(status=400, body=f"Not all required fields supplied, missing {err}")
    except ValueError:
        raise HTTPError(status=400, body=f"Values provided were not in expected format")

    if current_chunk == 0:
        save_ip(client_ip, dz_uuid)

    save_dir = chunk_path / dz_uuid

    if not save_dir.exists():
        save_dir.mkdir(exist_ok=True, parents=True)

    # Save the individual chunk
    with open(save_dir / str(request.forms["dzchunkindex"]), "wb") as f:
        file.save(f)

    # See if we have all the chunks downloaded
    with lock:
        chucks[dz_uuid].append(current_chunk)
        completed = len(chucks[dz_uuid]) == total_chunks

    # Concat all the files into the final file when all are downloaded
    if completed:
        hasher = hashlib.new("sha3_256")
        size = 0
        save_path = storage_path / f"{dz_uuid}_{secure_filename(file.filename)}"
        with open(save_path, "wb") as f:
            for file_number in range(total_chunks):
                content = (save_dir / str(file_number)).read_bytes()
                f.write(content)
                hasher.update(content)
                size += len(content)
        if save_path.name.lower().endswith(pillow_image_types):
            try:
                generate_thumbnail(save_path, dz_uuid)
            except Exception:
                traceback.print_exc()
                print("Could not generate thumbnail")
        print(f"{file.filename} has been uploaded")
        shutil.rmtree(save_dir)
        return {"sha3_256": hasher.hexdigest(), "size": size}

    return "Chunk Upload Successful"


@route("/download/<dz_uuid>")
def download(dz_uuid):
    if not allow_downloads:
        raise HTTPError(status=403)
    for file in storage_path.iterdir():
        if file.is_file() and file.name.startswith(dz_uuid):
            return static_file(file.name, root=file.parent.absolute(), download=True)
    return HTTPError(status=404)


@route("/thumbnail/<dz_uuid>.avif")
def thumbnail(dz_uuid):
    file = thumbnail_path / f"{dz_uuid}.avif"
    if not file.exists():
        default_thumb = Path(__file__).parent / "default.avif"
        if not default_thumb.exists():
            return HTTPError(status=404)
        return static_file(default_thumb.name, root=default_thumb.parent, mimetype="image/avif")
    return static_file(file.name, root=file.parent, mimetype="image/avif")


@route("/report", method="POST")
def report():
    data = request.json
    try:
        assert data["email"] and data["uuid"] and data["supporting_text"]
        dz_uuid = uuid.UUID(data["uuid"].strip())
    except (KeyError, AssertionError):
        raise HTTPError(status=400, body="Not all required fields provided")

    email = parseaddr(data["email"].strip())
    if not email[1]:
        return HTTPError(status=400, body="Invalid email address")

    if len(data["supporting_text"].strip()) < 10:
        return HTTPError(status=400, body="Please describe the issue in more detail")

    try:
        shutil.move((thumbnail_path / f"{dz_uuid}.avif"), (reported_path / f"{dz_uuid}.avif"))
    except Exception:
        pass

    for file in Path(storage_path).glob(f"{dz_uuid}*"):
        shutil.move(file, reported_path / file.name)

    return "Report submitted"


def generate_thumbnail(file, dz_uuid):
    save_file = thumbnail_path / f"{dz_uuid}.avif"
    try:
        image = Image.open(file)
        image.thumbnail((64, 64))
        image.save(save_file)
    except Exception:
        traceback.print_exc()
        print(f"Could not generate thumbnail for {file}")
        try:
            os.unlink(save_file)
        except Exception:
            pass


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=16273, required=False)
    parser.add_argument("--host", type=str, default="0.0.0.0", required=False)
    parser.add_argument("-s", "--storage", type=str, default=str(storage_path), required=False)
    parser.add_argument("-c", "--chunks", type=str, default=str(chunk_path), required=False)
    parser.add_argument("-t", "--thumbnails", type=str, default=str(thumbnail_path), required=False)
    parser.add_argument("-r", "--reported", type=str, default=str(reported_path), required=False)
    parser.add_argument(
        "--max-size",
        type=str,
        default=dropzone_max_file_size,
        help="Max file size (Mb)",
    )
    parser.add_argument(
        "--timeout",
        type=str,
        default=dropzone_timeout,
        help="Timeout (ms) for each chuck upload",
    )
    parser.add_argument("--chunk-size", type=str, default=dropzone_chunk_size, help="Chunk size (bytes)")
    parser.add_argument(
        "--file-types",
        type=str,
        default=dropzone_accepted_files,
        help="Allows images by default, set to '' to allow anything. "
        "Use mime types or extensions, i.e. 'image/*,application/pdf,.psd'",
    )
    parser.add_argument("--disable-parallel-chunks", required=False, default=False, action="store_true")
    parser.add_argument("--disable-force-chunking", required=False, default=False, action="store_true")
    parser.add_argument("-d", "--disable-downloads", required=False, default=False, action="store_true")
    parser.add_argument("--site-name", type=str, required=False, default=site_name)
    parser.add_argument("--dz-cdn", type=str, default=None, required=False)
    parser.add_argument("--dz-version", type=str, default=None, required=False)
    return parser.parse_args()


if __name__ == "__main__":

    args = parse_args()
    storage_path = Path(args.storage)
    chunk_path = Path(args.chunks)
    thumbnail_path = Path(args.thumbnails)
    reported_path = Path(args.reported)
    dropzone_chunk_size = args.chunk_size
    dropzone_timeout = args.timeout
    dropzone_max_file_size = args.max_size
    dropzone_accepted_files = args.file_types
    site_name = args.site_name
    try:
        if int(dropzone_timeout) < 1 or int(dropzone_chunk_size) < 1 or int(dropzone_max_file_size) < 1:
            raise Exception("Invalid dropzone option, make sure max-size, timeout, and chunk-size are all positive")
    except ValueError:
        raise Exception("Invalid dropzone option, make sure max-size, timeout, and chunk-size are all integers")

    if args.dz_cdn:
        dropzone_cdn = args.dz_cdn
    if args.dz_version:
        dropzone_version = args.dz_version
    if args.disable_parallel_chunks:
        dropzone_parallel_chunks = "false"
    if args.disable_force_chunking:
        dropzone_force_chunking = "false"
    if args.disable_downloads:
        allow_downloads = False

    storage_path.mkdir(exist_ok=True, parents=True)
    chunk_path.mkdir(exist_ok=True, parents=True)
    thumbnail_path.mkdir(exist_ok=True, parents=True)
    reported_path.mkdir(exist_ok=True, parents=True)

    print(
        f"""Timeout: {int(dropzone_timeout) // 1000} seconds per chunk
Chunk Size: {int(dropzone_chunk_size) // 1024} Kb
Max File Size: {int(dropzone_max_file_size)} Mb
Force Chunking: {dropzone_force_chunking}
Parallel Chunks: {dropzone_parallel_chunks}
Storage Path: {storage_path.absolute()}
Chunk Path: {chunk_path.absolute()}
Thumbnail Path: {thumbnail_path.absolute()}
Reported Path: {reported_path.absolute()}
"""
    )
    run(server="paste", port=args.port, host=args.host)

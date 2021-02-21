#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from threading import Lock
from collections import defaultdict
import shutil
import argparse
import uuid

from bottle import route, run, request, error, response, HTTPError
from werkzeug.utils import secure_filename

storage_path: Path = Path(__file__).parent / "storage"
chunk_path: Path = Path(__file__).parent / "chunk"

dropzone_cdn = "https://cdnjs.cloudflare.com/ajax/libs/dropzone"
dropzone_version = "5.7.6"
dropzone_timeout = "120000"
dropzone_max_file_size = "100000"
dropzone_chunk_size = "1000000"
dropzone_parallel_chunks = "true"
dropzone_force_chunking = "true"

lock = Lock()
chucks = defaultdict(list)


@error(500)
def handle_500(error_message):
    response.status = 500
    response.body = f"Error: {error_message}"
    return response


@route("/")
def index():
    index_file = Path(__file__) / "index.html"
    if index_file.exists():
        return index_file.read_text()
    return f"""
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="{dropzone_cdn.rstrip('/')}/{dropzone_version}/min/dropzone.min.css"/>
    <link rel="stylesheet" href="{dropzone_cdn.rstrip('/')}/{dropzone_version}/min/basic.min.css"/>
    <script type="application/javascript"
        src="{dropzone_cdn.rstrip('/')}/{dropzone_version}/min/dropzone.min.js">
    </script>
    <title>pyfiledrop</title>
</head>
<body>
    <div id="content">
        <form method="POST" action='/upload' class="dropzone dz-clickable" id="dropper" enctype="multipart/form-data">
        </form>

        <script type="application/javascript">
            Dropzone.options.dropper = {{
                paramName: 'file',
                chunking: true,
                forceChunking: {dropzone_force_chunking},
                url: '/upload',
                retryChunks: true,
                parallelChunkUploads: {dropzone_parallel_chunks},
                timeout: {dropzone_timeout}, // microseconds
                maxFilesize: {dropzone_max_file_size}, // megabytes
                chunkSize: {dropzone_chunk_size} // bytes
            }}
        </script>
    </div>
</body>
</html>
    """


@route("/upload", method="POST")
def upload():
    file = request.files.get("file")
    if not file:
        raise HTTPError(status=400, body="No file provided")

    dz_uuid = request.forms.get("dzuuid")
    if not dz_uuid:
        # Assume this file has not been chunked
        with open(storage_path / f"{uuid.uuid4()}_{secure_filename(file.filename)}", "wb") as f:
            file.save(f)
        return "File Saved"

    # Chunked download
    try:
        current_chunk = int(request.forms["dzchunkindex"])
        total_chunks = int(request.forms["dztotalchunkcount"])
    except KeyError as err:
        raise HTTPError(status=400, body=f"Not all required fields supplied, missing {err}")
    except ValueError:
        raise HTTPError(status=400, body=f"Values provided were not in expected format")

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
        with open(storage_path / f"{dz_uuid}_{secure_filename(file.filename)}", "wb") as f:
            for file_number in range(total_chunks):
                f.write((save_dir / str(file_number)).read_bytes())
        print(f"{file.filename} has been uploaded")
        shutil.rmtree(save_dir)

    return "Chunk upload successful"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=16273, required=False)
    parser.add_argument("-s", "--storage", type=str, default=str(storage_path), required=False)
    parser.add_argument("-c", "--chunks", type=str, default=str(chunk_path), required=False)
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
    parser.add_argument("--disable-parallel-chunks", required=False, default=False, action="store_true")
    parser.add_argument("--disable-force-chunking", required=False, default=False, action="store_true")
    parser.add_argument("--dz-cdn", type=str, default=None, required=False)
    parser.add_argument("--dz-version", type=str, default=None, required=False)
    return parser.parse_args()


if __name__ == "__main__":

    args = parse_args()
    storage_path = Path(args.storage)
    chunk_path = Path(args.chunks)
    dropzone_chunk_size = args.chunk_size
    dropzone_timeout = args.timeout
    dropzone_max_file_size = args.max_size
    if args.dz_cdn:
        dropzone_cdn = args.dz_cdn
    if args.dz_version:
        dropzone_version = args.dz_version
    if args.disable_parallel_chunks:
        dropzone_parallel_chunks = "false"
    if args.disable_force_chunking:
        dropzone_force_chunking = "false"

    if not storage_path.exists():
        storage_path.mkdir(exist_ok=True)
    if not chunk_path.exists():
        chunk_path.mkdir(exist_ok=True)

    print(
        f"""Timeout: {int(dropzone_timeout) // 1000} seconds per chunk
Chunk Size: {int(dropzone_chunk_size) // 1024} Kb
Max File Size: {int(dropzone_max_file_size)} Mb
Force Chunking: {dropzone_force_chunking}
Parallel Chunks: {dropzone_parallel_chunks}
Storage Path: {storage_path.absolute()}
Chunk Path: {chunk_path.absolute()}
"""
    )
    run(server="paste", port=args.port)

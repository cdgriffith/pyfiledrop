#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from threading import Lock
from collections import defaultdict
import shutil
import argparse
import uuid
import zlib

from bottle import route, run, request, error, response, HTTPError, static_file
from werkzeug.utils import secure_filename

storage_path: Path = Path(__file__).parent / "storage"
chunk_path: Path = Path(__file__).parent / "chunk"

allow_downloads = False
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

    <div id="content" style="width: 800px; margin: 0 auto;">
        <h2>Upload new files</h2>
        <form method="POST" action='/upload' class="dropzone dz-clickable" id="dropper" enctype="multipart/form-data">
        </form>

        <h2>
            Uploaded
            <input type="button" value="Clear" onclick="clearCookies()" />
        </h2>
        <div id="uploaded">

        </div>

        <script type="application/javascript">
            function clearCookies() {{
                document.cookie = "files=; Max-Age=0";
                document.getElementById("uploaded").innerHTML = "";
            }}

            function getFilesFromCookie() {{
                try {{ return document.cookie.split("=", 2)[1].split("||");}} catch (error) {{ return []; }}
            }}

            function saveCookie(new_file) {{
                    let all_files = getFilesFromCookie();
                    all_files.push(new_file);
                    document.cookie = `files=${{all_files.join("||")}}`;
            }}

            function generateLink(combo){{
                const uuid = combo.split('|^^|')[0];
                const name = combo.split('|^^|')[1];
                if ({'true' if allow_downloads else 'false'}) {{
                    return `<a href="/download/${{uuid}}" download="${{name}}">${{name}}</a>`;
                }}
                return name;
            }}


            function init() {{

                Dropzone.options.dropper = {{
                    paramName: 'file',
                    chunking: true,
                    forceChunking: {dropzone_force_chunking},
                    url: '/upload',
                    retryChunks: true,
                    parallelChunkUploads: {dropzone_parallel_chunks},
                    timeout: {dropzone_timeout}, // microseconds
                    maxFilesize: {dropzone_max_file_size}, // megabytes
                    chunkSize: {dropzone_chunk_size}, // bytes
                    init: function () {{
                        this.on("complete", function (file) {{
                            let combo = `${{file.upload.uuid}}|^^|${{file.upload.filename}}`;
                            saveCookie(combo);
                            document.getElementById("uploaded").innerHTML += generateLink(combo)  + "<br />";
                        }});
                    }}
                }}

                if (typeof document.cookie !== 'undefined' ) {{
                    let content = "";
                     getFilesFromCookie().forEach(function (combo) {{
                        content += generateLink(combo) + "<br />";
                    }});

                    document.getElementById("uploaded").innerHTML = content;
                }}
            }}

            init();

        </script>
    </div>
</body>
</html>
    """


@route("/favicon.ico")
def favicon():
    return zlib.decompress(
        b"x\x9c\xedVYN\xc40\x0c5J%[\xe2\xa3|q\x06\x8e1G\xe1(=ZoV\xb2\xa7\x89\x97R\x8d\x84\x04\xe4\xa5\xcb(\xc9\xb3\x1do"
        b"\x1d\x80\x17?\x1e\x0f\xf0O\x82\xcfw\x00\x7f\xc1\x87\xbf\xfd\x14l\x90\xe6#\xde@\xc1\x966n[z\x85\x11\xa6\xfcc"
        b"\xdfw?s\xc4\x0b\x8e#\xbd\xc2\x08S\xe1111\xf1k\xb1NL\xfcU<\x99\xe4T\xf8\xf43|\xaa\x18\xf8\xc3\xbaHFw\xaaj\x94"
        b"\xf4c[F\xc6\xee\xbb\xc2\xc0\x17\xf6\xf4\x12\x160\xf9\xa3\xfeQB5\xab@\xf4\x1f\xa55r\xf9\xa4KGG\xee\x16\xdd\xff"
        b"\x8e\x9d\x8by\xc4\xe4\x17\tU\xbdDg\xf1\xeb\xf0Zh\x8e\xd3s\x9c\xab\xc3P\n<e\xcb$\x05 b\xd8\x84Q1\x8a\xd6Kt\xe6"
        b"\x85(\x13\xe5\xf3]j\xcf\x06\x88\xe6K\x02\x84\x18\x90\xc5\xa7Kz\xd4\x11\xeeEZK\x012\xe9\xab\xa5\xbf\xb3@i\x00"
        b"\xce\xe47\x0b\xb4\xfe\xb1d\xffk\xebh\xd3\xa3\xfd\xa4:`5J\xa3\xf1\xf5\xf4\xcf\x02tz\x8c_\xd2\xa1\xee\xe1\xad"
        b"\xaa\xb7n-\xe5\xafoSQ\x14'\x01\xb7\x9b<\x15~\x0e\xf4b\x8a\x90k\x8c\xdaO\xfb\x18<H\x9d\xdfj\xab\xd0\xb43\xe1"
        b'\xe3nt\x16\xdf\r\xe6\xa1d\xad\xd0\xc9z\x03"\xc7c\x94v\xb6I\xe1\x8f\xf5,\xaa2\x93}\x90\xe0\x94\x1d\xd2\xfcY~f'
        b"\xab\r\xc1\xc8\xc4\xe4\x1f\xed\x03\x1e`\xd6\x02\xda\xc7k\x16\x1a\xf4\xcb2Q\x05\xa0\xe6\xb4\x1e\xa4\x84\xc6"
        b"\xcc..`8'\x9a\xc9-\n\xa8\x05]?\xa3\xdfn\x11-\xcc\x0b\xb4\x7f67:\x0c\xcf\xd5\xbb\xfd\x89\x9ebG\xf8:\x8bG"
        b"\xc0\xfb\x9dm\xe2\xdf\x80g\xea\xc4\xc45\xbe\x00\x03\xe9\xd6\xbb"
    )


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


@route("/download/<dz_uuid>")
def download(dz_uuid):
    if not allow_downloads:
        raise HTTPError(status=403)
    for file in storage_path.iterdir():
        if file.is_file() and file.name.startswith(dz_uuid):
            return static_file(file.name, root=file.parent.absolute(), download=True)
    return HTTPError(status=404)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", type=int, default=16273, required=False)
    parser.add_argument("--host", type=str, default="0.0.0.0", required=False)
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
    parser.add_argument("-a", "--allow-downloads", required=False, default=False, action="store_true")
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
    if args.allow_downloads:
        allow_downloads = True

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
    run(server="paste", port=args.port, host=args.host)

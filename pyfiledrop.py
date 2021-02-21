#!/usr/bin/env python
# -*- coding: utf-8 -*-
from pathlib import Path
from threading import Lock
from collections import defaultdict
import shutil

from bottle import route, run, request, error, response
from werkzeug.utils import secure_filename

storage_path = Path(__file__).parent / "storage"
chunk_path = Path(__file__).parent / "chunk"
if not storage_path.exists():
    storage_path.mkdir(exist_ok=True)
if not chunk_path.exists():
    chunk_path.mkdir(exist_ok=True)

lock = Lock()
chucks = defaultdict(list)


@error(500)
def handle_500(error):
    response.status = 500
    response.body = f"Error: {error}"
    return response


@route("/")
def index():
    return """
<!doctype html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/dropzone/5.7.6/min/dropzone.min.css"/>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/dropzone/5.7.6/min/basic.min.css"/>
    <script type="application/javascript" 
        src="https://cdnjs.cloudflare.com/ajax/libs/dropzone/5.7.6/min/dropzone.min.js">
    </script>
    <title>pyfiledrop</title>
</head>
<body>
    <div id="content">
        <form method="POST" action='/upload' class="dropzone dz-clickable" id="dropper" enctype="multipart/form-data">
        </form>
        
        <script type="application/javascript">
            Dropzone.options.dropper = {
                paramName: 'file',
                chunking: true,
                forceChunking: true,
                url: '/upload',
                retryChunks: true,
                parallelChunkUploads: true,
                timeout: 120000, // microseconds
                maxFilesize: 100000, // megabytes
                chunkSize: 1000000 // bytes
            }
        </script>
    </div>
</body>
</html>
    """


@route('/upload', method='POST')
def upload():
    try:
        file = request.files['file']
        dz_uuid = request.forms['dzuuid']
        current_chunk = int(request.forms['dzchunkindex'])
        total_chunks = int(request.forms['dztotalchunkcount'])
    except KeyError as err:
        raise Exception(f"Not all required fields supplied, missing {err}")
    save_dir = chunk_path / dz_uuid

    if not save_dir.exists():
        save_dir.mkdir(exist_ok=True, parents=True)

    with open(save_dir / str(request.forms['dzchunkindex']), "wb") as f:
        file.save(f)

    with lock:
        chucks[dz_uuid].append(current_chunk)
        completed = len(chucks[dz_uuid]) == total_chunks

    if completed:
        with open(storage_path / f"{dz_uuid}_{secure_filename(file.filename)}", "wb") as f:
            for file_number in range(total_chunks):
                f.write((save_dir / str(file_number)).read_bytes())
        print(f"{file.filename} has been uploaded")
        shutil.rmtree(save_dir)

    print(f'Chunk {current_chunk + 1} of {total_chunks} for file {file.filename}')
    return "Chunk upload successful"


if __name__ == '__main__':
    run(server='paste', port=6789)

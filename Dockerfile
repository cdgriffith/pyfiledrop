# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY pyfiledrop/* /app
COPY requirements.txt /app
COPY LICENSE /app

# Install any needed packages specified in requirements.txt
RUN --mount=type=cache,target=/root/.cache pip install --no-cache-dir -r requirements.txt

# Define environment variables and default values
ENV PORT=16273
ENV HOST=0.0.0.0
ENV MAX_SIZE=100000
ENV TIMEOUT=120000
ENV CHUNK_SIZE=1000000
ENV FILE_TYPES=image/*,.psd,.arw,video/*,.mp4,.mkv,.zip,.7z,.gzip,.tar,.gz,.rar,.raw,.pdf
ENV DISABLE_PARALLEL_CHUNKS=false
ENV DISABLE_FORCE_CHUNKING=false
ENV DISABLE_DOWNLOADS=false
ENV SITE_NAME="pyfiledrop"
ENV DZ_CDN=https://cdnjs.cloudflare.com/ajax/libs/dropzone
ENV DZ_VERSION=5.9.3
ENV ALLOW_DELETE=false
ENV ADMIN_PASS=pyfileadmin

VOLUME /storage /chunk /thumbnails /reported


# Make port available to the world outside this container
EXPOSE ${PORT}

# Run pyfiledrop.py when the container launches
CMD ["sh", "-c", "python pyfiledrop.py \
--port ${PORT} \
--host ${HOST} \
--storage /storage \
--chunks /chunks \
--thumbnails /thumbnails \
--reported /reported \
--max-size ${MAX_SIZE} \
--timeout ${TIMEOUT} \
--chunk-size ${CHUNK_SIZE} \
--file-types ${FILE_TYPES} \
--disable-parallel-chunks ${DISABLE_PARALLEL_CHUNKS} \
--disable-force-chunking ${DISABLE_FORCE_CHUNKING} \
--disable-downloads ${DISABLE_DOWNLOADS} \
--allow-delete ${ALLOW_DELETE} \
--site-name ${SITE_NAME} \
--dz-cdn ${DZ_CDN} \
--dz-version ${DZ_VERSION} \
--admin-password ${ADMIN_PASS}"]

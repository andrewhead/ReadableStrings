#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import requests
import urlparse
import os.path
from tqdm import tqdm

from models import Resource
from lock import lock_method


logging.basicConfig(level=logging.INFO, format="%(message)s")
LOCK_FILENAME = '/tmp/resource-links-fetcher.lock'
STREAM_CHUNK_SIZE = 1024
MAX_FILE_LENGTH = 536870912  # 512 MB
REQUEST_TIMEOUT = 5
DATA_DIRECTORY = 'data'
if not os.path.exists(DATA_DIRECTORY):
    os.mkdir(DATA_DIRECTORY)


@lock_method(LOCK_FILENAME)
def main(overwrite, show_progress, *args, **kwargs):

    csv_resources = Resource.select().where(Resource.format == 'CSV')
    resource_count = Resource.select().count()
    log_skip = lambda msg, rid: logging.warn("Skipping resource %s: %s", rid, msg)

    for resource_index, resource in enumerate(csv_resources, start=1):

        url = resource.url
        resource_id = resource.resource_id
        if url is None:
            log_skip("Null URL", resource_id)
            continue

        parsed_url = urlparse.urlparse(url)
        path = parsed_url.path
        scheme = parsed_url.scheme

        # Duck out of this routine if the call won't complete or fetch data
        if path == '':
            log_skip("Looks like a home page", resource_id)
            continue
        elif scheme not in ['http', 'https']:
            log_skip("Non-HTTP schema", resource_id)
            continue

        # Compute the name of the destination file
        src_file_name = path.split('/')[-1]
        dest_file_name = resource_id + '-' + src_file_name
        dest_path = os.path.join(DATA_DIRECTORY, dest_file_name)

        if not overwrite and os.path.exists(dest_path):
            log_skip("Data file has already been downloaded.", resource_id)
            continue

        # Fetch code is inspired by that on Stack Overflow:
        # http://stackoverflow.com/questions/22676/how-do-i-download-a-file-over-http-using-python#answer-10744565
        try:
            resp = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            log_skip("Request timed out when trying to reach server.", resource_id)
            continue
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError) as e:
            log_skip("Request error (%s)" % e, resource_id)
            continue

        # Get the total expected size of the file
        content_length = int(resp.headers['content-length']) \
            if 'content-length' in resp.headers else None
        if content_length is None:
            log_skip("Response headers missing 'Content-Length'", resource_id)
            continue
        elif content_length > MAX_FILE_LENGTH:
            log_skip("File is greater than the maximum file length", resource_id)
            continue

        progress_desc = "Downloading resource %d / %d" % (resource_index, resource_count)
        progress_bar = tqdm(
            total=content_length,
            disable=(not show_progress),
            desc=progress_desc,
            unit='byte'
        )

        # Stream data to file
        with open(dest_path, 'wb') as dest_file:
            try:
                for block in resp.iter_content(chunk_size=STREAM_CHUNK_SIZE):
                    dest_file.write(block)
                    progress_bar.update(STREAM_CHUNK_SIZE)
            except requests.exception.ConnectionError as e:
                log_skip("Request error during streaming (%s)" % e, resource_id)
                continue

        progress_bar.close()


def configure_parser(parser):
    parser.description = "Fetch CSV resources for which URLs have been scraped."
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help="Overwrite already-fetched data files. By default, this program will avoid fetching" +
             "files that are already present in the data directory."
    )
    parser.add_argument(
        '--show-progress',
        action='store_true',
        help="Show progress for each file download."
    )

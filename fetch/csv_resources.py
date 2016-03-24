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
        resp = requests.get(url, stream=True)

        # Stream data to file
        progress_desc = "Downloading resource %d / %d" % (resource_index, resource_count)
        with open(dest_path, 'wb') as dest_file:
            for block in tqdm(resp.iter_content(), disable=(not show_progress), desc=progress_desc):
                dest_file.write(block)


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

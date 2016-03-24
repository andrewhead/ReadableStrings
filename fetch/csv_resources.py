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
def main(show_progress, *args, **kwargs):

    csv_resources = Resource.select().where(Resource.format == 'CSV')
    resource_count = Resource.select().count()

    for resource_index, resource in enumerate(csv_resources, start=1):

        url = resource.url
        if url is None:
            logging.warn("Null URL for resource %s", resource.id)
            continue

        # Compute the name of the destination file
        path = urlparse.urlparse(url).path
        src_file_name = path.split('/')[-1]
        dest_file_name = resource.resource_id + '-' + src_file_name
        dest_path = os.path.join(DATA_DIRECTORY, dest_file_name)
        progress_desc = "Downloading resource %d / %d" % (resource_index, resource_count)

        # Fetch code is inspired by that on Stack Overflow:
        # http://stackoverflow.com/questions/22676/how-do-i-download-a-file-over-http-using-python#answer-10744565
        resp = requests.get(url, stream=True)

        # Stream data to file
        with open(dest_path, 'wb') as dest_file:
            for block in tqdm(resp.iter_content(), disable=(not show_progress), desc=progress_desc):
                dest_file.write(block)


def configure_parser(parser):
    parser.description = "Fetch CSV resources for which URLs have been scraped."
    parser.add_argument(
        '--show-progress',
        action='store_true',
        help="Show progress for each file download."
    )

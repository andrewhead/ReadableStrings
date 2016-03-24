#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import time
from peewee import fn

from fetch.api import make_request, default_requests_session
from models import Dataset, Resource
from lock import lock_method
from progressbar import ProgressBar, Percentage, Bar, ETA, Counter, RotatingMarker


logging.basicConfig(level=logging.INFO, format="%(message)s")


URL = "http://catalog.data.gov/api/3/action/package_search"
DATA_FORMAT = 'CSV'
RESULTS_PER_PAGE = 1000  # hard limit for CKAN APIs
DEFAULT_PARAMS = {
    'fq': 'res_format:' + DATA_FORMAT,
    'rows': RESULTS_PER_PAGE,
}
REQUEST_DELAY = 0.5  # set low as there will already be a delay from response latency
LOCK_FILENAME = '/tmp/resource-links-fetcher.lock'


@lock_method(LOCK_FILENAME)
def main(show_progress, *args, **kwargs):

    # Create a new fetch index for the records fetched.
    last_fetch_index = Dataset.select(fn.Max(Dataset.fetch_index)).scalar() or 0
    fetch_index = last_fetch_index + 1

    # Set up progress bar
    if show_progress:
        progress_bar = ProgressBar(widgets=[
            'Progress: ', Percentage(),
            ' ', Bar(marker=RotatingMarker()),
            ' ', ETA(),
            ' Fetched metadata for ', Counter(), ' datasets.'
        ])
        progress_bar.start()

    # Fetch all pages of datasets
    datasets_fetched = 0
    last_page = False
    while not last_page:

        params = DEFAULT_PARAMS.copy()
        params['start'] = datasets_fetched
        resp = make_request(default_requests_session.get, URL, params=params).json()

        if not resp['success']:
            logging.error("Request to URL %s was unsuccessful", URL)

        result = resp['result']
        num_datasets = len(result['results'])
        datasets_fetched += num_datasets

        if show_progress:
            # We can finally initialize the total number of datasets expected
            # only after we get the first round of results.
            progress_bar.maxval = result['count']
            progress_bar.update(datasets_fetched)

        for dataset in result['results']:

            dataset_record = Dataset.create(
                dataset_id=dataset['id'],
                title=dataset['title'],
                license_title=dataset['license_title'],
                fetch_index=fetch_index,
            )

            for resource in dataset['resources']:
                if resource['format'] == DATA_FORMAT:
                    Resource.create(
                        resource_id=resource['id'],
                        dataset=dataset_record,
                        format=resource['format'],
                        url=resource['url'],
                    )

        time.sleep(REQUEST_DELAY)  # enforce a pause between each fetch to be respectful to API
        last_page = datasets_fetched >= result['count']

    if show_progress:
        progress_bar.finish()


def configure_parser(parser):
    parser.description = "Fetch links to CSV resources from Data.gov"
    parser.add_argument(
        '--show-progress',
        action='store_true',
        help="Show progress in loading content from the file. " +
        "Note that this may slow down execution as the program will have " +
        "to count the amount of the file that is being read."
    )

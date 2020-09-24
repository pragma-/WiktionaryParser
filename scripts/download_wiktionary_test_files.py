"""
This utility script downloads HTML and MediaWiki markdown files of specific
words to be used in offline testing.
"""

import requests
import os
from typing import List, Set
from tests import test_core as test
from concurrent.futures import as_completed
from requests_futures.sessions import FuturesSession

from tests.test_core import test_words

current_dir = os.path.dirname(__file__)

tests_dir = os.path.abspath(os.path.join(current_dir, '..', 'tests'))
word_tests_file = os.path.join(tests_dir, 'test.py')
html_test_files_dir = os.path.join(tests_dir, 'html_test_files')
markup_test_files_dir = os.path.join(tests_dir, 'markup_test_files')


wiktionary_base_url = 'https://{}.wiktionary.org/wiki/'
wiktionary_api_url = 'https://{}.wiktionary.org/w/api.php'


def write_file_and_dir(filepath: str, mode: str, content, encoding: str = None):
    dirname = os.path.dirname(filepath)

    if not os.path.isdir(dirname):
        os.makedirs(dirname)

    with open(filepath, mode, encoding=encoding) as f:
        f.write(content)


def save_html_test_file(language:str,
                        word: str,
                        old_id: int,
                        response: requests.Response):
    """Save the HTML of a word definition page."""
    print(f"Saving '{language}-{word}-{old_id}' HTML.")

    filepath = os.path.join(html_test_files_dir,
                            f'{language}-{word}-{old_id}.html')

    write_file_and_dir(filepath, 'wb', response.content)


def create_html_request(language: str,
                        word: str,
                        old_id: int,
                        session: FuturesSession):
    """Create a request to get the HTML of a word definition page."""
    print(f"Creating request for '{language}-{word}-{old_id}' HTML.")

    def on_load(response, *args, **kwargs):
        save_html_test_file(language, word, old_id, response)
    return session.get(wiktionary_base_url.format(language) + word,
                       params={
                           'oldid': old_id
                       }, hooks={
                           'response': on_load
                       })


def save_markup_test_file(word: str,
                          old_id: int,
                          response: requests.Response):
    print(f"Saving '{word}-{old_id}' markup.")
    json = response.json()

    content = json['parse']['wikitext']
    filepath = os.path.join(markup_test_files_dir,
                            f'{word}-{old_id}.txt')

    write_file_and_dir(filepath,
                       'w',
                       content,
                       encoding='utf-8')


def create_markup_request(language:str,
                          word: str,
                          old_id: int,
                          session: FuturesSession):
    """Get a JSON from Wiktionary containing a page's WikiMedia markup
    definition and save said markup.
    """
    print(f"Creating request for '{word}-{old_id}' markup.")

    def on_load(response, *args, **kwargs):
        save_markup_test_file(word, old_id, response)

    return session.get(wiktionary_api_url.format(language),
                       params={
                           'action': 'parse',
                           'oldid': old_id,
                           'prop': 'wikitext',
                           'formatversion': 2,
                           'format': 'json'
                       },
                       hooks={
                           'response': on_load
                       })


def download_test_html_and_markup(words_and_old_ids: List[Set]):
    """Read an array of words and old_ids, then download from Wiktionary the
    HTML and WikiMedia markup for those words.
    """
    with FuturesSession() as session:
        futures = []

        for word, old_id, language in words_and_old_ids:
            futures.append(create_html_request(language, word, old_id, session))

        as_completed(futures)


if __name__ == '__main__':
    download_test_html_and_markup(test_words)

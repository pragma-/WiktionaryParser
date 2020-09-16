from parameterized import parameterized
import unittest
import json
from wiktionaryparser import WiktionaryParser
from deepdiff import DeepDiff
from typing import Dict, List
import mock
from urllib import parse
import os

parser = WiktionaryParser()


tests_dir = os.path.dirname(__file__)
html_test_files_dir = os.path.join(tests_dir, 'html_test_files')
markup_test_files_dir = os.path.join(tests_dir, 'markup_test_files')

test_words = [
    ('grapple', 60361156, 'en'),
    ('cat', 60300266, 'en'),
    ('dog', 60355953, 'en'),
    ('test', 60380981, 'en'),
    ('house', 60395574, 'en'),
    ('game', 60329229, 'en'),
    ('line', 60329678, 'en'),
    ('catch', 60198254, 'en'),
    ('trip up', 59323170, 'en'),
    ('error', 60354714, 'en'),
    ('true', 60221581, 'en'),
    ('golf', 60185260, 'en'),
    ('wave', 60213185, 'en'),
    ('song', 60388804, 'en'),
    ('a', 60361249, 'en')
]


def get_test_words_table(*allowed_words):
    """Convert the test_words array to an array of three element tuples."""
    result = []

    for word, old_id, language in test_words:
        if len(allowed_words) == 0 or (word in allowed_words):
            result.append((language, word, old_id))

    return result


class MockResponse:
    def __init__(self, text: str):
        self.text = text


def mocked_requests_get(*args, **kwargs):
    url = args[0]
    parsed_url = parse.urlparse(url)
    params = kwargs['params']

    word = parsed_url.path.split('/')[-1]
    filepath = os.path.join(html_test_files_dir,
                            f'{word}-{params["oldid"]}.html')
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    return MockResponse(text)


class TestParser(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self.expected_fetch_results = {}
        self.expected_pack_results = {}

        with open('tests/test_fetch_output.json', 'r') as f:
            self.expected_fetch_results = json.load(f)

        with open('tests/test_pack_output.json', 'r') as f:
            self.expected_pack_results = json.load(f)

        super(TestParser, self).__init__(*args, **kwargs)

    @parameterized.expand(get_test_words_table())
    @mock.patch("requests.Session.get", side_effect=mocked_requests_get)
    def test_using_mock_session(self, lang: str, word: str, old_id: int, mock_get):
        self.__test(lang, word, old_id)

    def __test(self, lang: str, word: str, old_id: int):
        parser.set_language(lang)

        print(f"[1/2] Testing fetch('{word}') in '{lang}'")
        fetched_word = parser.fetch(word, old_id=old_id)
        expected_fetch_result = self.expected_fetch_results[lang][word]
        diff_fetched = DeepDiff(fetched_word, expected_fetch_result, ignore_order=True)
        if diff_fetched != {}:
            TestParser.alert_diff(diff_fetched, word, lang, fetched_word)

        print(f"[2/2] Testing pack_definitions_and_examples('{word}') in '{lang}'")
        packed_word = parser.pack_definitions_and_examples(fetched_word)
        expected_pack_result = self.expected_pack_results[lang][word]
        diff_packed = DeepDiff(packed_word, expected_pack_result, ignore_order=True)
        if diff_packed != {}:
            TestParser.alert_diff(diff_packed, word, lang, packed_word)

        self.assertEqual(diff_fetched, {})
        self.assertEqual(diff_packed, {})

    @staticmethod
    def alert_diff(diff: DeepDiff, word: str, lang: str, actual_result):
        print(f"Found mismatch in '{word}' in '{lang}'")
        print(json.dumps(json.loads(diff.to_json()), indent=4))
        print("Actual result:")
        print(json.dumps(actual_result, indent=4))


if __name__ == '__main__':
    unittest.main()

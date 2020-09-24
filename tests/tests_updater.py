from tqdm.asyncio import tqdm

from tests.test_core import *


@mock.patch("requests.Session.get", side_effect=mocked_requests_get)
def update_tests(mock_get):
    fetch_languages = {}
    pack_languages = {}
    with tqdm(total=len(test_words)) as progress_bar:
        for tuple_word in test_words:
            word, old_id, language = tuple_word
            parser.set_language(language)
            result = parser.fetch(word, old_id=old_id)
            fetch_languages.setdefault(language, {}).update({word: result})
            pack_languages.setdefault(language, {}).update({word: parser.pack_definitions_and_examples(result)})
            progress_bar.update()
    with open('test_fetch_output.json', 'w') as f:
        f.write(json.dumps(fetch_languages, ensure_ascii=False, indent=4))
    with open('test_pack_output.json', 'w') as f:
        f.write(json.dumps(pack_languages, ensure_ascii=False, indent=4))


update_tests()

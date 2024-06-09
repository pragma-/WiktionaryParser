import json
import re, requests
import pkgutil
from wiktionaryparser.utils import WordData, Definition, RelatedWord
from bs4 import BeautifulSoup
from itertools import zip_longest
from copy import copy
from string import digits

PARTS_OF_SPEECH = [
    "noun", "verb", "adjective", "adverb", "determiner",
    "article", "preposition", "conjunction", "proper noun",
    "letter", "character", "phrase", "proverb", "idiom",
    "symbol", "syllable", "numeral", "initialism", "interjection",
    "definitions", "pronoun", "particle", "predicative", "participle",
    "suffix",
]

RELATIONS = [
    "synonyms", "antonyms", "hypernyms", "hyponyms",
    "meronyms", "holonyms", "troponyms", "related terms",
    "coordinate terms",
]

TRANSLATIONS = json.loads(pkgutil.get_data(__name__, "translations.json").decode("utf-8"))
LANGUAGES = json.loads(pkgutil.get_data(__name__, "languages.json").decode("utf-8"))

def is_subheading(child, parent):
    child_headings = child.split(".")
    parent_headings = parent.split(".")
    if len(child_headings) <= len(parent_headings):
        return False
    for child_heading, parent_heading in zip(child_headings, parent_headings):
        if child_heading != parent_heading:
            return False
    return True

class WiktionaryParser(object):
    def __init__(self):
        self.url = "https://en.wiktionary.org/wiki/{}?printable=yes"
        self.soup = None
        self.session = requests.Session()
        self.session.mount("http://", requests.adapters.HTTPAdapter(max_retries = 2))
        self.session.mount("https://", requests.adapters.HTTPAdapter(max_retries = 2))
        self.language = 'english'
        self.language_code = 'en'
        self.current_word = None
        self.PARTS_OF_SPEECH = copy(PARTS_OF_SPEECH)
        self.RELATIONS = copy(RELATIONS)
        self.INCLUDED_ITEMS = self.RELATIONS + self.PARTS_OF_SPEECH + ['etymology', 'pronunciation']

    def include_part_of_speech(self, part_of_speech):
        part_of_speech = part_of_speech.lower()
        if part_of_speech not in self.PARTS_OF_SPEECH:
            self.PARTS_OF_SPEECH.append(part_of_speech)
            self.INCLUDED_ITEMS.append(part_of_speech)

    def exclude_part_of_speech(self, part_of_speech):
        part_of_speech = part_of_speech.lower()
        self.PARTS_OF_SPEECH.remove(part_of_speech)
        self.INCLUDED_ITEMS.remove(part_of_speech)

    def include_relation(self, relation):
        relation = relation.lower()
        if relation not in self.RELATIONS:
            self.RELATIONS.append(relation)
            self.INCLUDED_ITEMS.append(relation)

    def exclude_relation(self, relation):
        relation = relation.lower()
        self.RELATIONS.remove(relation)
        self.INCLUDED_ITEMS.remove(relation)

    def translate(self, related_id):
        if self.language_code == "en":
            return related_id
        return TRANSLATIONS[self.language_code].get(related_id, related_id)

    def set_language(self, language_code):
        if language_code is not None:
            self.language_code = language_code.lower()
            self.language = LANGUAGES[self.language_code]
            self.url = f"https://{self.language_code}.wiktionary.org/wiki/{{}}?printable=yes"

    def get_language(self):
        return self.language

    def clean_html(self):
        unwanted_classes = ['sister-wikipedia', 'thumb', 'reference', 'cited-source']
        for tag in self.soup.find_all(True, {'class': unwanted_classes}):
            tag.extract()
        [x.decompose() for x in self.soup.findAll(
            lambda tag: (not tag.contents or len(tag.get_text(strip=True)) <= 0) and not tag.name == 'br')]

    def remove_digits(self, string):
        return string.translate(str.maketrans('', '', digits)).strip()

    def count_digits(self, string):
        return len(list(filter(str.isdigit, string)))

    def get_id_list(self, contents, content_type):
        if content_type == 'etymologies':
            checklist = ['etymology']
        elif content_type == 'pronunciation':
            checklist = ['pronunciation']
        elif content_type == 'definitions':
            checklist = self.PARTS_OF_SPEECH
            if self.language == 'chinese':
                checklist += self.current_word
        elif content_type == 'related':
            checklist = self.RELATIONS
        else:
            return None
        checklist = [self.translate(item) for item in checklist]
        id_list = []
        if len(contents) == 0:
            return [('1', x.title(), x) for x in checklist if self.soup.find(['h2','h3','h4','h5'], {'id': x.title()})]
        for content_tag in contents:
            content_index = content_tag.find_previous().text
            text_to_check = self.remove_digits(content_tag.text).strip().lower()
            if text_to_check in checklist:
                content_id = content_tag.parent['href'].replace('#', '')
                id_list.append((content_index, content_id, text_to_check))
        return id_list

    def no_entry(self):
        languages = self.get_languages()
        disambig = self.get_disambig()
        return {'languages': languages, 'disambig': disambig}

    def get_languages(self):
        contents = self.soup.find_all('h2')
        languages = []
        for content in contents:
            if content.text not in ['Contents', 'Navigation menu']:
                languages.append(content.text)
        return languages

    def get_disambig(self):
        contents = self.soup.find_all('div', {'class': ['disambig-see-also', 'disambig-see-also-2']})
        disambig = []
        for content in contents:
            disambig.append(re.sub(r'See also: ', '', content.text))
        return disambig

    def get_word_data(self, language):
        contents = self.soup.find_all('span', {'class': 'toctext'})
        word_contents = []
        start_index = None
        for content in contents:
            if content.text.lower() == language:
                start_index = content.find_previous().text + '.'
        if len(contents) != 0 and not start_index:
            return self.no_entry()
        if len(contents) == 0:
            headlines = self.soup.find_all('h2')
            did_find_language = False
            for headline in headlines:
                if headline.text.lower() == language:
                    did_find_language = True
            if not did_find_language:
                return self.no_entry()
        included_items = [self.translate(item) for item in self.INCLUDED_ITEMS]
        for content in contents:
            index = content.find_previous().text
            content_text = self.remove_digits(content.text.lower())
            if index.startswith(start_index) and content_text in included_items:
                word_contents.append(content)
        word_data = {
            'examples': self.parse_examples(word_contents),
            'definitions': self.parse_definitions(word_contents),
            'etymologies': self.parse_etymologies(word_contents),
            'related': self.parse_related_words(word_contents),
            'pronunciations': self.parse_pronunciations(word_contents),
        }
        json_obj_list = self.map_to_object(word_data)
        return json_obj_list

    def parse_pronunciations(self, word_contents):
        pronunciation_id_list = self.get_id_list(word_contents, 'pronunciation')
        pronunciation_list = []
        audio_links = []
        pronunciation_div_classes = ['mw-collapsible', 'vsSwitcher']
        for pronunciation_index, pronunciation_id, _ in pronunciation_id_list:
            pronunciation_text = []
            span_tag = self.soup.find_all(['h2','h3','h4','h5'], {'id': pronunciation_id})[0]
            list_tag = span_tag.parent
            list_tag = list_tag.find_next_sibling()
            while list_tag.name != 'div':
                if list_tag.name == 'p':
                    pronunciation_text.append(list_tag.text)
                    break
                for super_tag in list_tag.find_all('sup'):
                    super_tag.clear()
                for list_element in list_tag.find_all('li'):
                    for audio_tag in list_element.find_all('div', {'class': 'mediaContainer'}):
                        audio_links.append(audio_tag.find('source')['src'])
                        audio_tag.extract()
                    for nested_list_element in list_element.find_all('ul'):
                        nested_list_element.extract()
                    if list_element.text and not list_element.find('table', {'class': 'audiotable'}):
                        pronunciation_text.append(list_element.text.strip())
                list_tag = list_tag.find_next_sibling()
            pronunciation_list.append((pronunciation_index, pronunciation_text, audio_links))
        return pronunciation_list

    @staticmethod
    def fix_uppercase(string: str):
        """Makes it so `My definitionRandom sentance` becomes `My definition`"""
        return re.sub(r'(?<=[^\\][a-z])[A-Z].*', "", string)

    def parse_definitions(self, word_contents):
        definition_id_list = self.get_id_list(word_contents, 'definitions')
        definition_list = []
        definition_tag = None
        for def_index, def_id, def_type in definition_id_list:
            definition_text = []
            span_tag = self.soup.find_all(['h2','h3','h4','h5'], {'id': def_id})[0]
            table = span_tag.parent.find_next_sibling()
            while table and table.name not in ['div', 'h2', 'h3', 'h4', 'h5']:
                definition_tag = table
                table = table.find_next_sibling()
                if definition_tag.name == 'p':
                    text_to_append = definition_tag.text.strip()
                    if text_to_append:
                        definition_text.append(f"#{text_to_append}")
                if definition_tag.name in ['ol', 'ul']:
                    for element in definition_tag.find_all('li', recursive=False):
                        if element.text:
                            sub_definitions = element.find_all("li")
                            if sub_definitions:
                                element.find("li").extract()
                                top_definition = element.text.strip()
                                sub_definitions_list = [self.fix_uppercase(sub_definition.text.strip())
                                                        for sub_definition in sub_definitions]
                                sub_definitions_list.insert(0, top_definition)
                                definition_text.append(sub_definitions_list)
                            else:
                                definition_text.append(self.fix_uppercase(element.text.strip()))
            if def_type == 'definitions':
                def_type = ''
            definition_list.append((def_index, definition_text, def_type))
        return definition_list

    def parse_examples(self, word_contents):
        definition_id_list = self.get_id_list(word_contents, 'definitions')
        example_list = []
        for def_index, def_id, def_type in definition_id_list:
            span_tag = self.soup.find_all(['h2','h3','h4','h5'], {'id': def_id})[0]
            table = span_tag.parent
            while table is not None and table.name != 'ol':
                table = table.find_next_sibling()
            examples = []
            while table and table.name == 'ol':
                for quot_list in table.find_all("ul", recursive=True):
                    quot_list.clear()
                for element in table.find_all('dd'):
                    if element.find("span", {"class": "nyms"}) is None:
                        example_text = re.sub(r'\([^)]*\)', '', element.text.strip())
                        if example_text and "\n" not in example_text:
                            index = 0
                            for li in table.find_all("li"):
                                if li == element.parent.parent:
                                    break
                                index += 1
                            examples.append({
                                "index": index,
                                "text": example_text
                            })
                    element.clear()
                example_list.append((def_index, examples, def_type))
                table = table.find_next_sibling()
        return example_list

    def parse_etymologies(self, word_contents):
        etymology_id_list = self.get_id_list(word_contents, 'etymologies')
        etymology_list = []
        etymology_tag = None
        for etymology_index, etymology_id, _ in etymology_id_list:
            etymology_text = ''
            span_tag = self.soup.find_all(['h2','h3','h4','h5'], {'id': etymology_id})[0]
            next_tag = span_tag.parent.find_next_sibling()
            while next_tag:
                if next_tag.get('class') is not None and 'mw-heading' in next_tag.get('class'):
                    break
                etymology_tag = next_tag
                next_tag = next_tag.find_next_sibling()
                if etymology_tag.name == 'p':
                    etymology_text += etymology_tag.text
                else:
                    for list_tag in etymology_tag.find_all('li'):
                        etymology_text += list_tag.text + '\n'
            etymology_list.append((etymology_index, etymology_text.strip()))
        return etymology_list

    def parse_related_words(self, word_contents):
        relation_id_list = self.get_id_list(word_contents, 'related')
        related_words_list = []
        for related_index, related_id, relation_type in relation_id_list:
            words = []
            span_tag = self.soup.find_all(['h2','h3','h4','h5'], {'id': related_id})[0]
            parent_tag = span_tag.parent
            while parent_tag and not parent_tag.find_all('li'):
                parent_tag = parent_tag.find_next_sibling()
            if parent_tag:
                for list_tag in parent_tag.find_all('li'):
                    words.append(list_tag.text)
            related_words_list.append((related_index, words, relation_type))
        return related_words_list

    def map_to_object(self, word_data):
        json_obj_list = []
        if not word_data['etymologies']:
            word_data['etymologies'] = [('', '')]
        for (current_etymology, next_etymology) in zip_longest(word_data['etymologies'], word_data['etymologies'][1:], fillvalue=('999', '')):
            data_obj = WordData()
            data_obj.etymology = current_etymology[1]
            for pronunciation_index, text, audio_links in word_data['pronunciations']:
                if (self.count_digits(current_etymology[0]) == self.count_digits(pronunciation_index)) or (current_etymology[0] <= pronunciation_index < next_etymology[0]):
                    data_obj.pronunciations = text
                    data_obj.audio_links = audio_links
            for definition_index, definition_text, definition_type in word_data['definitions']:
                current_etymology_str = ".".join(f"{int(num):02d}" for num in current_etymology[0].split(".") if num)
                definition_index_str = ".".join(f"{int(num):02d}" for num in definition_index.split(".") if num)
                next_etymology_str = ".".join(f"{int(num):02d}" for num in next_etymology[0].split(".") if num)
                if current_etymology_str <= definition_index_str < next_etymology_str \
                        or is_subheading(current_etymology[0], definition_index):
                    def_obj = Definition()
                    def_obj.text = definition_text
                    def_obj.part_of_speech = definition_type
                    for example_index, examples, _ in word_data['examples']:
                        if example_index.startswith(definition_index):
                            def_obj.example_uses = examples
                    for related_word_index, related_words, relation_type in word_data['related']:
                        if related_word_index.startswith(definition_index):
                            def_obj.related_words.append(RelatedWord(relation_type, related_words))
                    data_obj.definition_list.append(def_obj)
            json_obj_list.append(data_obj.to_json())
        return json_obj_list

    def fetch(self, word, language=None, old_id=None):
        language = self.language if not language else language
        response = self.session.get(self.url.format(word), params={'oldid': old_id})
        self.soup = BeautifulSoup(response.text.replace('>\n<', '><'), 'html.parser')
        self.current_word = word
        self.clean_html()
        return self.get_word_data(language.lower())

    @staticmethod
    def _pack_definitions_and_examples_recursive(
            definitions_list: list, examples_list: list, output_list: list,
            definitions_index=0, examples_index=0
    ):
        global overall_definitions_index

        if definitions_index >= len(definitions_list):
            return

        while definitions_index < len(definitions_list) and type(definitions_list[definitions_index]) is list:
            nested_list = []
            WiktionaryParser._pack_definitions_and_examples_recursive(
                definitions_list[definitions_index], examples_list, nested_list, 0, examples_index
            )
            output_list.append(nested_list)
            definitions_index += 1

            if definitions_index >= len(definitions_list):
                return

        # It's a heading - and examples' indexes ignore headings, so overall_definitions_index won't be incremented
        if definitions_list[definitions_index][0] == "#":
            output_list.append(definitions_list[definitions_index])
            definitions_index += 1
        else:
            examples_to_pack = []
            while (examples_index < len(examples_list) and
                   examples_list[examples_index]["index"] <= overall_definitions_index):
                if examples_list[examples_index]["index"] == overall_definitions_index:
                    examples_to_pack.append(examples_list[examples_index]["text"])
                examples_index += 1
            if examples_to_pack:
                output_list.append({
                    "text": definitions_list[definitions_index],
                    "examples": examples_to_pack
                })
            else:
                output_list.append(definitions_list[definitions_index])
            overall_definitions_index += 1
            definitions_index += 1

        WiktionaryParser._pack_definitions_and_examples_recursive(
            definitions_list, examples_list, output_list, definitions_index, examples_index
        )

    @staticmethod
    def pack_definitions_and_examples(word: list) -> list:
        def pack(definitions_list: list, examples_list: list, output_list: list):
            global overall_definitions_index
            overall_definitions_index = 0
            WiktionaryParser._pack_definitions_and_examples_recursive(definitions_list, examples_list, output_list)

        if not word or not word[0]["definitions"] or not word[0]["definitions"][0]["text"]:
            return []

        etymologies_list = []
        for etymology in word:
            parts_of_speech_list = []
            for part_of_speech in etymology["definitions"]:
                part_of_speech_name = part_of_speech["partOfSpeech"]
                definitions = part_of_speech["text"]
                examples = part_of_speech["examples"]
                packed_definitions_and_examples = []
                pack(definitions, examples, packed_definitions_and_examples)
                if packed_definitions_and_examples:
                    parts_of_speech_list.append({
                        "part_of_speech": part_of_speech_name,
                        "text": packed_definitions_and_examples
                    })
            if parts_of_speech_list:
                etymologies_list.append(parts_of_speech_list)
        return etymologies_list

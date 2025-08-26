from setuptools import setup,find_packages

with open('readme.md', 'r') as readme:
  long_desc = readme.read()

setup(
  name = 'wiktionaryparser',
  version = '0.1.06',
  description = 'A tool to parse word data from wiktionary.com into a JSON object',
  long_description = long_desc,
  long_description_content_type='text/markdown',
  packages = ['wiktionaryparser', 'tests'],
  data_files=[('testOutput', ['tests/test_fetch_output.json', 'tests/test_pack_output.json']), ('readme', ['readme.md']), ('requirements', ['requirements.txt'])],
  author = 'Suyash Behera',
  author_email = 'sne9x@outlook.com',
  maintainer = 'Pragmatic Software',
  maintainer_email = 'pragma78@gmail.com',
  url = 'https://github.com/pragma-/WiktionaryParser',
  download_url = 'https://github.com/pragma-/WiktionaryParser/archive/master.zip',
  keywords = ['Parser', 'Wiktionary'],
  install_requires = ['beautifulsoup4','requests'],
  classifiers=[
   'Development Status :: 5 - Production/Stable',
   'License :: OSI Approved :: MIT License',
  ],
  package_data={'': ['languages.json', 'translations.json']},
  include_package_data=True
)

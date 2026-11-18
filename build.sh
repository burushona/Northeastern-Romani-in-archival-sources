#!/bin/sh
# Rebuild the CLDF dataset, the search page and the source texts from the PDF of the book.
# usage: sh build.sh path/to/book.pdf
set -e
PDF=${1:?usage: sh build.sh book.pdf}
mkdir -p raw docs/sources
python3 scripts/extract_pdf.py "$PDF" 447 581 scripts/hyphenated_words.txt raw/paras.json   # word index, pp. 447-581
python3 scripts/parse.py raw/paras.json raw/parsed.json
python3 scripts/source_texts.py "$PDF" docs/sources raw/source_pages.json                     # source texts, pp. 94-446
python3 scripts/build_cldf.py raw/parsed.json raw/source_pages.json .

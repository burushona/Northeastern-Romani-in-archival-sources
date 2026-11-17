#!/bin/sh
# Rebuild the CLDF dataset and the search page from the PDF of the book.
# usage: sh build.sh path/to/book.pdf      (the index is on pp. 447–581)
set -e
PDF=${1:?usage: sh build.sh book.pdf}
mkdir -p raw
python3 scripts/extract_pdf.py "$PDF" 447 581 scripts/hyphenated_words.txt raw/paras.json
python3 scripts/parse.py raw/paras.json raw/parsed.json
python3 scripts/build_cldf.py raw/parsed.json .

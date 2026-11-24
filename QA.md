# Checks on the published text

The index was converted automatically from the PDF of the book.

## Corrected misprints

The misprints below are corrected during conversion: `scripts/apply_corrections.py` applies `scripts/corrections.tsv` to the text taken from the PDF before parsing it. In `cldf/attestations.csv` the affected forms carry the reason in the `Corrected` column; on the search page they are marked “corrected”. To correct another misprint, add a line to `corrections.tsv` and run `build.sh` again.

| Entry | In the book | Corrected |
|---|---|---|
| mangél | … 3 мэ манге́л Добр. 1908 (bracket not closed) | … 3 мэ манге́л) Добр. 1908 |
| kedél, s- | … мн. скыдэ́нпе Добр. 1893 (bracket not closed) | … мн. скыдэ́нпе) Добр. 1893 |
| džidó | Гол. 1789 | Гол. 1879 |
| bérš | Gl. 1878 | Gl. 1877 |
| na | Лек. 1829 | Лек. 1827 |
| vavír | Дор. 1908 | Добр. 1908 |
| pušúm | Григ. 1851, 1851 | Григ. 1851, 1852 |

The list of sources (p. 8) gives Bardanes's list as “Источник 2”; it is Источник 1. This is corrected in `scripts/sources.json`.

## Other

* *dlúgo¹*: the citation «Патк. 1900» is set in italics; this is handled during conversion.
* The list of sources cites Grigor'ev's material as [Böhtlingk 1852, 1854], but the bibliography has *Boehtlingk 1853* (and Böhtlingk 1854). `sources.bib` uses the bibliography entries.

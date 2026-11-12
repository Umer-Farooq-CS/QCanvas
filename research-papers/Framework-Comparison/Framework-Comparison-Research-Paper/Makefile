FILENAME=paper

LATEX=pdflatex
LATEXOPT=--shell-escape
NONSTOP=--interaction=nonstopmode

LATEXMK=latexmk
LATEXMKOPT=-pdf

all: ${FILENAME}.pdf

${FILENAME}.pdf: ${FILENAME}.tex references.bib sections/*.tex
	$(LATEXMK) $(LATEXMKOPT) -pdflatex="$(LATEX) $(LATEXOPT) $(NONSTOP) %O %S" $(FILENAME).tex

clean:
	latexmk -c $(FILENAME)

distclean:
	latexmk -C $(FILENAME)
	find . -type f -name '*.aux'         -delete
	find . -type f -name '*.bbl'         -delete
	find . -type f -name '*.blg'         -delete
	find . -type f -name '*.log'         -delete
	find . -type f -name '*.out'         -delete
	find . -type f -name '*.fls'         -delete
	find . -type f -name '*.fdb_latexmk' -delete
	find . -type f -name '*.synctex.gz'  -delete
	find . -type f -name '*.toc'         -delete
	find . -type f -name '*.snm'         -delete
	find . -type f -name '*.nav'         -delete

debug:
	$(LATEX) $(LATEXOPT) $(FILENAME)

.PHONY: all clean distclean debug

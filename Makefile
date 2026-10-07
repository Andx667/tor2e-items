# make        -> check the database, then the PDF in build/
# make check  -> only check the database against src/rules.toml
# make site   -> site/data.js for the item wizard (then open site/index.html)
# make test   -> check that the wizard finds the same problems as the checker
# make clean
.PHONY: pdf check site test clean
pdf:
	python3 tools/build.py
check:
	python3 tools/check.py
site:
	python3 tools/site.py
test:
	python3 tools/test_site.py
clean:
	rm -rf build

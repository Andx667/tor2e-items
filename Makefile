# make        -> check the database, then the PDF in build/
# make check  -> only check the database against src/rules.toml
# make clean
.PHONY: pdf check clean
pdf:
	python3 tools/build.py
check:
	python3 tools/check.py
clean:
	rm -rf build

all:
	@echo "Nothing to do!"

develop:
	pip install --editable .

doc:
	sphinx-apidoc -f -o doc smaug_iot
	$(MAKE) -C doc html

clean:
	$(MAKE) -C doc clean

test:
	py.test -v


.PHONY: all doc develop clean test

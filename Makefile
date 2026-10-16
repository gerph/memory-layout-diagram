##
# Run the tests for the Memory Layout Diagram tool.
#
#   make tests          Run the unit tests and the integration tests
#   make unittests      Run only the unit tests (python unittest)
#   make integration    Run only the expectation tests (riscos-tooltester)

PYTHON ?= python3
TOOLTESTER ?= riscos-tooltester

.PHONY: tests unittests integration

tests: unittests integration

unittests:
	$(PYTHON) -m unittest discover -s testcode -v

integration:
	$(TOOLTESTER) -show-command -show-output $(CURDIR)/testcode/mld testcode

ZIPS = KoboTouchExtended.zip KePub\ Output.zip KePub\ Input.zip \
       KePub\ Metadata\ Reader.zip KePub\ Metadata\ Writer.zip
CSS = $(wildcard css/*.css)
TRANSLATIONS = $(wildcard translations/*.mo)
ALL_SOURCES = $(shell find . -type f -name '*.py' -not -name 'pygettext.py')
ALL_TESTS = $(shell find tests -type f -name '*.py')

all: $(ZIPS)

KoboTouchExtended.zip: common.py container.py $(wildcard device/*.py) \
	$(TRANSLATIONS) $(CSS) plugin-import-name-kobotouch_extended.txt \
	device_init

	$(eval FILES := __init__.py)
	$(foreach f,$^,$(if $(wildcard $(f)),$(eval FILES += $(f))))
	-/usr/bin/zip -u "$@" $(FILES)
	rm -f __init__.py

KePub\ Output.zip: common.py container.py conversion/kepub_output.py \
	conversion/output_config.py $(TRANSLATIONS) $(CSS) conversion_out_init \
	plugin-import-name-kepubout.txt conversion/output_init

	$(eval FILES := __init__.py conversion/__init__.py)
	$(foreach f,$^,$(if $(wildcard $(f)),$(eval FILES += $(f))))
	-/usr/bin/zip -u "$@" $(FILES)
	rm -f __init__.py conversion/__init__.py

KePub\ Input.zip: common.py container.py conversion/kepub_input.py \
	conversion/input_config.py $(TRANSLATIONS) conversion_in_init \
	plugin-import-name-kepubin.txt conversion/input_init

	$(eval FILES := __init__.py conversion/__init__.py)
	$(foreach f,$^,$(if $(wildcard $(f)),$(eval FILES += $(f))))
	-/usr/bin/zip -u "$@" $(FILES)
	rm -f __init__.py conversion/__init__.py

KePub\ Metadata\ Reader.zip: common.py metadata/reader.py metadata/__init__.py \
	$(TRANSLATIONS) md_reader_init plugin-import-name-kepubmdreader.txt

	$(eval FILES := __init__.py)
	$(foreach f,$^,$(if $(wildcard $(f)),$(eval FILES += $(f))))
	-/usr/bin/zip -u "$@" $(FILES)
	rm -f __init__.py

KePub\ Metadata\ Writer.zip: common.py metadata/writer.py metadata/__init__.py \
	$(TRANSLATIONS) md_writer_init plugin-import-name-kepubmdwriter.txt

	$(eval FILES := __init__.py)
	$(foreach f,$^,$(if $(wildcard $(f)),$(eval FILES += $(f))))
	-/usr/bin/zip -u "$@" $(FILES)
	rm -f __init__.py

%_init: %_init.py
	cp -f $@.py $(dir $@)__init__.py

test: $(ZIPS) test_py2 test_py3

test_py%:
	@for test_file in $(CURDIR)/tests/test_*.py; do \
		CALIBRE_DIR=$(shell mktemp -d); \
		mkdir -p "$$CALIBRE_DIR/config" "$$CALIBRE_DIR/tmp"; \
		export CALIBRE_CONFIG_DIRECTORY="$$CALIBRE_DIR/config"; \
		export CALIBRE_TEMP_DIR="$$CALIBRE_DIR/tmp"; \
		for plugin in $(CURDIR)/*.zip; do \
			$(CURDIR)/calibre-py$*/calibre-customize -a "$$plugin"; \
		done; \
		PYTHONDONTWRITEBYTECODE="true" $(CURDIR)/calibre-py$*/calibre-debug "$$test_file"; \
		rm -rf "$$CALIBRE_DIR"; \
		unset CALIBRE_CONFIG_DIRECTORY CALIBRE_TEMP_DIR; \
	done;

pot: translations/messages.pot

translations/messages.pot: $(ALL_SOURCES)
	/usr/bin/env python3 -B ./pygettext.py -p translations $(ALL_SOURCES)

clean:
	rm -f *.zip

.PHONY: all clean test pot

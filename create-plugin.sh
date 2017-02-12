#!/bin/sh

common="container.py common.py __init__.py "
translations="translations/*.mo"
css="css/*.css"

echo "Creating KoboTouchExtended..."
cp -f device_init.py __init__.py
# shellcheck disable=SC2086
zip -ru KoboTouchExtended.zip ${common} device/*.py ${css} ${translations} plugin-import-name-kobotouch_extended.txt
rm -f __init__.py

echo "Creating KePub Output..."
cp -f conversion_out_init.py __init__.py
cp -f conversion/output_init.py conversion/__init__.py
# shellcheck disable=SC2086
zip -ru "KePub Output.zip" ${common} conversion/__init__.py conversion/kepub_output.py conversion/output_config.py ${css} ${translations} plugin-import-name-kepubout.txt
rm -f __init__.py

echo "Creating KePub Input..."
cp -f conversion_in_init.py __init__.py
cp -f conversion/input_init.py conversion/__init__.py
# shellcheck disable=SC2086
zip -ru "KePub Input.zip" ${common} conversion/__init__.py conversion/kepub_input.py conversion/input_config.py ${translations} plugin-import-name-kepubin.txt
rm -f __init__.py
rm -f conversion/__init__.py

echo "Creating KePub Metadata Reader..."
cp -f md_reader_init.py __init__.py
# shellcheck disable=SC2086
zip -ru "KePub Metadata Reader.zip" __init__.py common.py metadata/__init__.py metadata/reader.py ${translations} plugin-import-name-kepubmdreader.txt
rm -f __init__.py

echo "Creating KePub Metadata Writer..."
cp -f md_writer_init.py __init__.py
# shellcheck disable=SC2086
zip -ru "KePub Metadata Writer.zip" __init__.py common.py metadata/__init__.py metadata/writer.py ${translations} plugin-import-name-kepubmdwriter.txt
rm -f __init__.py


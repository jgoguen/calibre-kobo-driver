#!/bin/sh

echo "Creating KoboTouchExtended..."
cp -f device_init.py __init__.py
zip -ru KoboTouchExtended.zip container.py common.py __init__.py device plugin-import-name-kobotouch_extended.txt css translations
rm -f __init__.py

echo "Creating KePub Output..."
cp -f conversion_out_init.py __init__.py
cp -f conversion/output_init.py conversion/__init__.py
zip -ru "KePub Output.zip" container.py common.py __init__.py conversion/__init__.py conversion/kepub_output.py conversion/output_config.py plugin-import-name-kepubout.txt css translations
rm -f __init__.py

echo "Creating KePub Input..."
cp -f conversion_in_init.py __init__.py
cp -f conversion/input_init.py conversion/__init__.py
zip -ru "KePub Input.zip" container.py common.py __init__.py conversion/__init__.py conversion/kepub_input.py conversion/input_config.py plugin-import-name-kepubin.txt css translations
rm -f __init__.py
rm -f conversion/__init__.py

echo "Creating KePub Metadata Reader..."
cp -f md_reader_init.py __init__.py
zip -ru "KePub Metadata Reader.zip" __init__.py translations/*.mo metadata/__init__.py metadata/reader.py common.py plugin-import-name-kepubmdreader.txt
rm -f __init__.py

echo "Creating KePub Metadata Writer..."
cp -f md_writer_init.py __init__.py
zip -ru "KePub Metadata Writer.zip" __init__.py translations/*.mo metadata/__init__.py metadata/writer.py common.py plugin-import-name-kepubmdwriter.txt
rm -f __init__.py

touch __init__.py

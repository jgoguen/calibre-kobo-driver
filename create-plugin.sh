#!/bin/sh

cp -f device_init.py __init__.py
zip -ru KoboTouchExtended.zip container.py common.py __init__.py device plugin-import-name-kobotouch_extended.txt css translations
rm -f __init__.py

cp -f conversion_init.py __init__.py
zip -ru "KePub Output.zip" container.py common.py __init__.py conversion plugin-import-name-koboconversion.txt css translations
rm -f __init__.py

cp -f md_reader_init.py __init__.py
zip -ru "Read KEPUB metadata.zip" __init__.py translations/*.mo metadata/__init__.py metadata/reader.py common.py plugin-import-name-kepubmdreader.txt

cp -f md_writer_init.py __init__.py
zip -ru "Set KEPUB metadata.zip" __init__.py translations/*.mo metadata/__init__.py metadata/writer.py common.py plugin-import-name-kepubmdwriter.txt

touch __init__.py

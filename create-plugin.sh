#!/bin/sh

cp -f device_init.py __init__.py
zip -ru KoboTouchExtended.zip container.py common.py __init__.py device plugin-import-name-kobotouch_extended.txt css
rm -f __init__.py

cp -f conversion_init.py __init__.py
zip -ru "KePub Output.zip" container.py common.py __init__.py conversion plugin-import-name-kobotouch_extended.txt css
rm -f __init__.py

touch __init__.py

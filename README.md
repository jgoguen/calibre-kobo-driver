# Calibre driver for Kobo Touch/Glo/Mini
An extension of the existing KoboTouch driver provided with Calibre. This plugin allows modifying ePub files to enable extra Kobo features.

**Please note**: There is currently no way to save the modified books back into your Calibre library, so books are processed in transit to 
your device every time.

#Installation
To install this plugin from source, you have two options:

1. Create a ZIP file named `KoboTouchExtended.zip`, include these files, and add the ZIP file to Calibre using the Preferences menu:
	1. \_\_init\_\_.py
	1. container.py
	1. driver.py
	1. plugin-import-name-kobotouch\_extended.txt
1. Shut down Calibre and run `calibre-customize -b /path/to/calibre-kobo-driver`
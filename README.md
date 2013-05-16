# Calibre driver for Kobo Touch/Glo/Mini
An extension of the existing KoboTouch driver provided with Calibre. This plugin allows modifying ePub files to enable 
extra Kobo features.

**Please note**: Modified books are not saved back into your Calibre library to prevent issues with overwriting library 
configurations unexpectedly, so books are processed in transit to your device every time. In most cases, the extra time 
required should not be noticeable.

#Download
To download this plugin, either clone the repository or [download a snapshot of the `master` branch][zipdownload] by clicking on the big **ZIP** button near the top of the page.

[zipdownload]: https://github.com/jgoguen/calibre-kobo-driver/archive/master.zip

#Installation
The current release version of this plugin may be installed directly within calibre:

1. Open calibre's preferences, choose **Plugins**, and click **Get new plugins**
1. Select the **KoboTouchExtended** plugin from the list of available plugins and click **Install**
	1. Don't see it? You may already have it installed. Restart calibre and see if you are notified of a pending update.
1. Restart calibre

To install this plugin from source, you must create a ZIP file named `KoboTouchExtended.zip` and include these files:

1. \_\_init\_\_.py
1. container.py
1. driver.py
1. hyphenator.py
1. plugin-import-name-kobotouch\_extended.txt

To create the ZIP file:

1. Windows users can run the `create-plugin.ps1` script (requires that Powershell allow running unsigned scripts, which is not the default setting).
1. Linux and Mac OS X users can run the `create-plugin.sh` script (either grant it executable permissions first, or run `sh create-plugin.sh`).
1. Create an empty ZIP file and add the files noted above.
1. Select the files noted-above, right-click, and add the files to a new ZIP file. This may also be referred to as a "Compressed Folder" or only be available once you choose the "Archive" option, depending on your operating system.

Add the resulting ZIP file to calibre:

1. Preferences
1. Plugins
1. Load plugin from file

You may also shut down Calibre and run `calibre-customize -b /path/to/calibre-kobo-driver` from the command line to have calibre add the plugin itself, although this will add files that are not necessary.

# Usage
To use this plugin after installing:

1. Connect your Kobo Touch/Glo/Mini device and wait for it to be detected by calibre
1. Select the book(s) you want to send to your device.
1. Click the **Send to device** button.

## Hyphenation
This plugin includes the ability to add soft hyphens to converted ePubs. Soft hyphens are just like regular hyphens except that soft hyphens are only visible where they occur as the last character of a line, giving you the nice hyphenation expected of professional books. Enabling hyphenation requires a little work:

1. Download the LibreOffice (or OpenOffice) hyphenation dictionary for your language
	1. This will be a file with the 'oxt' extension. This is just a ZIP archive with a different name.
1. Unzip the OXT file and look for the file named as `hyph_[language].dic`.
1. Copy the hyphenation dictionary to the KoboTouchExtended configuration directory
	1. To find the configuration directory, open calibre's preferences, choose **Miscellaneous**, and click **Open calibre configuration directory**
	1. Go to the **plugins** directory
	1. Go to the **KoboTouchExtended** directory, creating it if it does not exist.
1. Copy the hyphenation dictionary as `hyph.dic` to use this as the default hyphenation dictionary if no  language-specific dictionary can be found
	1. This is also a good choice if you only read in one language. You may still enable other languages if required using the directions in the next step.
1. Enable extra hyphenation languages by copying the hyphenation dictionaries as `hyph_[lang].dic`, where `[lang]` is the ISO 639 3-letter language code (ISO 639-3, or ISO 639-2/T if no ISO 639-3 code exists)

## Kobo JavaScript Extraction
This plugin includes the ability to extract the Kobo JavaScript file from a free Kobo-supplied KePub which is not encumbered by any Digital Restrictions Management (DRM). Enabling this requires a little work:

1. Obtain a KePub file from Kobo which is provided to you without any Digital Restrictions Management.
	1. Some of [Kobo's free eBooks][kobofreebooks] are provided without DRM
	1. In some regions, Kobo devices are sold with free ebooks in the `.kobo/kepub/` folder which do not have DRM
1. Copy the KePub file to the KoboTouchExtended configuration directory
	1. To find the configuration directory, open calibre's preferences, choose **Miscellaneous**, and click **Open calibre configuration directory**
	1. Go to the **plugins** directory
	1. Go to the **KoboTouchExtended** directory, creating it if it does not exist.
1. Rename the KePub file to `reference.kepub.epub`
	1. Windows users must be sure to [show file extensions in Windows Explorer][winshowext] to be able to properly rename the file.

Once this file is in place and correctly named this plugin will automatically extract the Kobo JavaScript file, add it to books during conversion, and add appropriate references to content files.

[kobofreebooks]: http://www.kobobooks.com/lists/freeebooks/RYnbq2Rd7kSXf7MOhDofOQ-1.html
[winshowext]: http://support.microsoft.com/kb/865219

# Reporting a Bug
Found a bug with this plugin? Great! Please use the Github issue tracker to send me reports of issues or questions. Under no circumstances should I be emailed directly unless I have asked to have something sent to me. Any emails I haven't asked for will be silently ignored. Everyone can benefit from a public bug tracker, but only one person benefits from a private email.

When submitting a bug, I require the following information as a minimum, but any additional information is good to include:

1. What version of calibre and this plugin you are using. If you are not on the latest version of either, I will require that you update before I accept any bug report.
1. The full error message reported by calibre, if any.
1. For issues processing books, whether or not you have a book that you are able to send me that demonstrates the issue. Please be aware of any copyright restrictions that may prohibit sending me a book.
1. The calibre debug log.
	1. To get the calibre debug log, click the arrow beside the "Preferences" menu, choose "Restart in debug mode", repeat the same action that caused the issue, and close calibre. The debug log will be automatically displayed to you.

# Known Issues
The hyphenation feature may cause the Kobo device to fail to properly recognize words when you tap and hold a word to search for it in the dictionary. This may manifest as the device only selecting part of a word, in which case you may drag the selection to encompass the entire word as a workaround. It may also manifest as the Kobo saying that "word" could not be found and the closest match is "word". To avoid this, do not enable hyphenation.

The hyphenation feature frequently causes some display issues. The workaround is to not use hyphenation; it is a known issue that KePub files with soft hyphens are not always properly displayed. Most commonly noticed are:

1. There may be extra space, possibly a lot of extra space, when formatting changes (e.g. normal font to italics) or after punctuation.
1. There may be extra space at the end of a line. The amount of space appears to be proportional to the number of soft hyphens on that line, but is not always present even when there are a large number of soft hyphens.

Bookmarks, annotations, highlighting, and anything else that's highly dependent on your current position may work fine or may have slight issues. You may find that some books work better or worse than others. This issue is pending investigation.

If you have previously installed this plugin in calibre 0.9.18 or earlier, then you upgrade to calibre 0.9.19 or later and can't update the plugin, you must manually replace the plugin ZIP file:

1. Download the latest version of the code.
1. Generate a new plugin ZIP file. **Do not** use the `calibre-customize` method.
1. Shut down calibre entirely.
1. Open the calibre plugin directory.
	1. Don't know where this is? Before you close calibre, open calibre's preferences, choose **Miscellaneous**, and click the **Open calibre configuration directory** button. The plugin directory is in there.
1. Replace the file named **KoboTouchExtended.zip** with the new version you created. Please make sure the file name remains the same.

If you get an error similar to the following:
```
Traceback (most recent call last):
File "site-packages\calibre\gui2\preferences\plugins.py", line 310, in add_plugin
File "site-packages\calibre\customize\ui.py", line 361, in add_plugin
File "site-packages\calibre\customize\ui.py", line 53, in load_plugin
File "site-packages\calibre\customize\zipplugin.py", line 169, in load
File "importlib__init__.py", line 37, in import_module
File "site-packages\calibre\customize\zipplugin.py", line 147, in load_module
File "calibre_plugins.kobotouch_extended.__init__", line 4
<!DOCTYPE html>
^
SyntaxError: invalid syntax
```
The solution is to go back to the top of this file and read it again.

In some circumstances people have reported that while reading a book uploaded with this plugin they suddenly realize that a large amount of time (two hours or more) has passed without their awareness of the passage of time. The only known solution is to finish reading your current book. Voracious readers tend to report this issue more frequently. Please note, sleep is only a temporary resolution. 

# Kobo KePub Plugins

This provides a series of [calibre][calibre] extensions enabling calibre to work with ePub files with Kobo's additional features (called **KePub**). The following plugins are provided:

- `KoboTouchExtended`: This is a device driver plugin extending the functionality of the existing KoboTouch driver provided with Calibre to enable extra Kobo features. **Please note**: modified books are not saved back into your Calibre library to prevent issues with overwriting library configurations unexpectedly, so books are processed in transit to your device every time. In most cases, the extra time required should not be noticeable.
- `KePub Output`: This is a conversion plugin allowing calibre to convert any supported input format to KePub.
- `KePub Metadata Writer`: This is a metadata plugin which supports the `KePub Output` plugin. Installing this plugin allows calibre to write KePub metadata to the book as it is written out in calibre's conversion process. It serves no purpose without the `KePub Output` plugin.
- `KePub Input`: This is a conversion plugin allowing calibre to convert KePub to any supported output format.
- `KePub Metadata Reader`: This is a metadata plugin which allows calibre to read KePub metadata when converting a book from KePub format. It currently serves no purpose without the `KePub Input` plugin.

**WARNING: THE KEPUB FILE STRUCTURE IS NOT YET FULLY UNDERSTOOD. DO NOT, UNDER ANY CIRCUMSTANCES, DELETE THE FILES FOR THE SOURCE FORMAT. ALWAYS HAVE A NON-KEPUB FORMAT FOR YOUR BOOKS.**

## Installation

The current release version of this plugin may be installed directly within calibre:

1. Open calibre's preferences, choose `Plugins`, and click `Get new plugins`
1. Select the name of the plugin(s) you want to install from the list of available plugins and click `Install`
    1. Don't see it? You may already have it installed. Restart calibre and see if you are notified of a pending update.
    1. If you want to install multiple plugins, you must select and install them one at a time. Calibre will ask you to restart after each one, but you can safely wait until all desired plugins have been installed to restart calibre.
1. Restart calibre

## Download

To download this plugin, either clone the repository or download a snapshot. It is not necessary to download this plugin in this way unless you want to install from source for some reason, such as plugin development.

### Install from source

Please note, installation from source is only supported on Linux and Mac OS X 10.11 and later. Simply run the `create-plugin.sh` script to generate the ZIP file package for all plugins.

Windows users can run the `create-plugin.ps1` script, which requires that PowerShell allow running unsigned scripts (which is not the default setting and is dangerous to leave enabled). This PowerShell script is not regularly tested and is wholly unsupported; if it does not work for you and you know how to fix it, please submit a bug report with a patch or a corrected PowerShell script. Any bug reports for the PowerShell script which do not include a patch and a description of what problem is solved will be ignored.

Add the resulting ZIP file to calibre:

1. `Preferences`
1. `Plugins`
1. `Load plugin from file`

## Usage

To use the device driver plugin after installing:

1. Connect your supported Kobo device and wait for it to be detected by calibre
1. Select the book(s) you want to send to your device.
1. Click the **Send to device** button.

To use the conversion output format plugin after installing:

1. Choose the book you want to convert to KePub format
1. Choose the **KEPUB** format from the list of output formats (top-right of the conversion window)
1. Choose **KePub Options** from the left menu and make your option selections
1. Click **OK**

**WARNING: THE KEPUB FILE STRUCTURE IS NOT YET FULLY UNDERSTOOD. DO NOT, UNDER ANY CIRCUMSTANCES, DELETE THE FILES FOR THE SOURCE FORMAT. ALWAYS HAVE A NON-KEPUB FORMAT FOR YOUR BOOKS.**

To use the conversion input format plugin after installing:

1. Choose the KePub book you want to convert to a different format
1. Choose the desired target format from the list of output formats (top-right of the conversion window)
1. Click **OK**

### Adding Arbitrary CSS

The device driver plugin, through the base KoboTouch driver provided with calibre, has the ability to copy all rules from a specific CSS file into each book as it is uploaded. To support easily maintaining device-specific CSS files, the device driver can copy a CSS file into the correct place to allow adding it to each book. To do this, locate the calibre plugin directory, create a CSS file in there, and ensure that the **Modify CSS** option is selected in the driver preferences. To locate the calibre plugin directory, open calibre's preferences, choose **Miscellaneous**, and click the **Open calibre configuration directory** button. The plugin directory is in there.

The name of the CSS file must be in the format `kobo_extra_<DEVICE>.css`. The following replacements for `<DEVICE>` are currently supported (capitalization is important):

- Kobo Aura H2O &mdash; AURAH2O (`kobo_extra_AURAH2O.css`)
- Kobo Aura HD &mdash; AURAHD (`kobo_extra_AURAHD.css`)
- Kobo Aura &mdash; AURA (`kobo_extra_AURA.css`)
- Kobo Clara &mdash; CLARA (`kobo_extra_CLARA.css`)
- Kobo Forma &mdash; FORMA (`kobo_extra_FORMA.css`)
- Kobo Glo &mdash; GLO (`kobo_extra_GLO.css`)
- Kobo Glo HD &mdash; GLOHD (`kobo_extra_GLOHD.css`)
- Kobo Libra &mdash; LIBRA (`kobo_extra_LIBRA.css`)
- Kobo Mini &mdash; MINI (`kobo_extra_MINI.css`)
- Kobo Touch &mdash; TOUCH (`kobo_extra_TOUCH.css`)

Please note, this will blindly overwrite any `kobo_extra.css` you may have already sent to your Kobo device! If you have created the `kobo_extra.css` file on your Kobo device already and you want to make use of this feature, you must copy `kobo_extra.css` to the location specified above.

Please also be aware that support for some Kobo devices (e.g. the Aura H2O, Libra, Forma, etc.) was only added in later calibre versions than the minimum required for this plugin. Accordingly, you'll need to be running the appropriate minimum calibre version for this feature to work for all devices.

### Hyphenation

The driver plugin and the conversion output plugin includes the ability to add a CSS file to each book enabling KePub hyphenation. The standard hyphenation dictionaries provided on Kobo devices are somewhat deficient for some languages; fixing this (or adding your own dictionary) requires a little work and requires that you can create gzipped tarballs (.tgz files). Note that you can only update existing dictionaries, you cannot add new ones.

1. Somewhere on your computer, create the directory structure `usr/local/Kobo/hyphenDicts` (capitalization is important)
1. Download the LibreOffice hyphenation dictionary for your language
    1. This will be a file with the `oxt` extension. This is just a ZIP archive with a different name.
1. Unzip the OXT file (Windows users need to rename the file to change the extension to `zip`, which requires Explorer to be configured to [show file extensions][winshowext], which is a good idea to do anyway) and look for the file named as `hyph_[language].dic`.
1. Copy the hyphenation dictionary to the `hyphenDicts` folder without changing the name.
1. Add the `usr` folder to `KoboRoot.tgz`
    1. UNIX users (Linux, Solaris, BSD, Mac, etc.) can, from a terminal window, run `tar czf KoboRoot.tgz usr/` from wherever you put the `usr` directory.
    1. Windows users, you're on your own. It has been reported that using the free [7-Zip archiver][7zip] you can create .tgz files. See [this article][wintargz] for more details.
        1. If you follow these directions exactly, your file will have the extension `.tar.gz`. You can safely rename this to `.tgz` after the file has been created and ignore the Windows warning about changing file extensions.

Once you have created `KoboRoot.tgz` copy it to the `.kobo` directory on your Kobo device, unmount/eject the drive, and unplug the device. You will see a screen indicating that the Kobo device is updating; it is not, but this method takes advantage of the Kobo update mechanism to load the necessary dictionary files and the Kobo device cannot distinguish between this and a real software update. Make sure you keep your version of `KoboRoot.tgz` around, you will need to re-apply it after every Kobo software update!

Provided languages are:

1. U.S. English (en\_US)
1. French (fr\_FR)
1. Spanish (es\_ES)
1. German (de\_DE)
1. Italian (it\_IT)
1. Portugese (pt\_PT)
1. Dutch (nl\_NL)

Please note that even with this feature, hyphenation is not exact. Also remember that you can only update existing dictionaries.

### Kobo JavaScript Extraction

Both the driver and conversion output plugins include the ability to extract the Kobo JavaScript file from a free Kobo-supplied KePub which is not encumbered by any Digital Restrictions Management (DRM). To avoid distributing any of Kobo's copyrighted work, enabling this requires a little work:

1. Obtain a KePub file from Kobo which is provided to you without any Digital Restrictions Management.
    1. Some of [Kobo's free eBooks][kobofreebooks] are provided without DRM
    1. In some regions, Kobo devices are sold with free ebooks in the `.kobo/kepub/` folder on the device which do not have DRM
1. Copy the KePub file to the calibre plugins directory
    1. To find the plugins directory, open calibre's preferences, choose **Miscellaneous**, and click **Open calibre configuration directory**
    1. Go to the **plugins** directory
1. Rename the KePub file to `reference.kepub.epub`
    1. Windows users must be sure to [show file extensions in Windows Explorer][winshowext] to be able to properly rename the file.

Once this file is in place and correctly named, the driver and conversion output plugins will automatically extract the Kobo JavaScript file, add it to books during conversion, and add appropriate references to content files.

### Generated KePub File Copying

On occasion, such as for debugging purposes, you may wish to have easy access to the generated KePub file. There is an option in the device driver plugin which allows you to enter the full, absolute path to a directory where all generated files will be copied to once they have been converted. This directory must:

1. Be somewhere you can write to
1. Contain no variables
    1. OS X and Linux users may use a tilde (~) to refer to their home directory instead of typing it in full (/home/jgoguen/calibre-debug may be entered as ~/calibre-debug). Windows users must always enter a full path.

The final path will be a combination of this path and the save template for the plugin. If your debug path is `/home/jgoguen/calibre-debug` and your save template is `{author_sort}/{title}` then a KePub file would be copied to, for example, `/home/jgoguen/calibre-debug/Camerata, Jo/A History of Vanguard Industries.kepub.epub`. Directories will be created as needed.

## Contributing

Decided you want to contribute to the development of these plugins? Awesome! You have many options:

1. **Contribute code**, whether for existing bug reports, for new bugs that you found, or for new features that you really want to see implemented. To contribute code, you may fork the repository and send a BitBucket pull request, or you may send me a PM on MobileRead with a git patch file.
1. **Submit bug reports**. Bug reports are my to-do list for this plugin; any requests anywhere else are likely to get missed and forgotten and direct emails **will be silently ignored**. Although I'm happy to discuss the plugins on the MobileRead forums, I may still ask you to create a bug report; this is so I actually remember to investigate your request!
1. **Test pre-released code** from BitBucket. Between releases, new code is committed to the BitBucket repository and may be installed using directions provided in this file. Based on your testing, you may submit bug reports, provide feedback, think of new feature requests, or just generally enjoy early access (and not necessarily stable code!) to upcoming versions of the plugin.

You may also prefer to contribute in some other way. You may [donate to me via PayPal][paypaldonate], [contribute to my fundraiser][driverfundraiser], or you may also contribute by answering questions from other people who may have issues, purchasing items from my wishlists (not yet linked, I'll get on that soon-ish), continuing to use this plugin and providing feedback, and probably a few other ways I haven't thought of yet.

## Asking Questions

Wondering how to do something? Want to know if something is possible? Ask your question on the MobileRead Forum thread for the relevant plugin

- [`KoboTouchExtended`][devicethread]
- [`KePub Output`][kepubout]
- [`KePub Metadata Writer`][mdwriter]
- [`KePub Input`][kepubin]
- [`KePub Metadata Reader`][mdreader]

# Reporting a Bug

Found a bug with this plugin? Great! I want to hear from you! Go to [GitHub and submit a new bug report](https://github.com/jgoguen/calibre-kobo-driver/issues/new). Under no circumstances should I be emailed directly unless I have asked to have something sent to me. Any emails I haven't asked for **may be silently ignored** at my sole discretion. Everyone can benefit from a public bug tracker, but only one person benefits from a private email.

When submitting a bug, I require the following information as a minimum, but any additional information is good to include:

1. What version of calibre and plugin you are using. If you are not on the latest plugin version, I will require that you update before I accept any bug report. If you are not on the latest version of calibre, I may not be able to reproduce the issue and may ask you to install multiple test versions and provide debug logging.
1. The full error message reported by calibre, if any.
1. For issues processing books, whether or not you have a book that you are able to send me that demonstrates the issue. DO NOT UPLOAD EBOOK FILES TO THE ISSUE TRACKER! Under no circumstances should copyrighted content be uploaded to a public bug. If a book file is needed, I will send you a link to use to upload one.
1. The calibre debug log. No bug is accepted without this provided.
    1. To get the calibre debug log, click the arrow beside the "Preferences" menu, choose "Restart in debug mode", repeat the same action that caused the issue, and close calibre. The debug log will be automatically displayed to you.

## Known Issues

When using Kobo firmware 2.9.0 or later, sideloaded KePub files do not display full in-book statistics available on official book files.

If you have previously installed the device driver plugin in calibre 0.9.18 or earlier, then you upgrade to calibre 0.9.19 or later and can't update the plugin or install the conversion output format plugin, you must manually replace the device driver plugin ZIP file:

1. Download the latest version of the code.
1. Generate a new plugin ZIP file.
1. Shut down calibre entirely.
1. Open the calibre plugin directory.
    1. Don't know where this is? Before you close calibre, open calibre's preferences, choose **Miscellaneous**, and click the **Open calibre configuration directory** button. The plugin directory is in there.
1. Replace the file named **KoboTouchExtended.zip** with the new version you created. Please make sure the file name remains the same.

If you get an error similar to the following:

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

The solution is to go back to the top of this file and read it again.

In some circumstances people have reported that while reading a book uploaded with this plugin they suddenly realize that a large amount of time (two hours or more) has passed without their awareness of the passage of time. The only known solution is to finish reading your current book. Voracious readers tend to report this issue more frequently. Please note, sleep is only a temporary resolution.

[7zip]: http://www.7-zip.org/download.html
[bugtracker]: https://bitbucket.org/jgoguen/calibre-kobo-driver/issues?status=new&status=open
[calibre]: https://calibre-ebook.com
[devicethread]: https://www.mobileread.com/forums/showthread.php?t=211135
[driverfundraiser]: http://gogetfunding.com/project/kobo-touch-extended-driver-development
[kepubin]: https://www.mobileread.com/forums/showthread.php?t=263594
[kepubout]: https://www.mobileread.com/forums/showthread.php?t=220565
[kobofreebooks]: http://www.kobobooks.com/lists/freeebooks/RYnbq2Rd7kSXf7MOhDofOQ-1.html
[mdreader]: https://www.mobileread.com/forums/showthread.php?t=261009
[mdwriter]: https://www.mobileread.com/forums/showthread.php?t=261010
[paypaldonate]: https://www.paypal.com/cgi-bin/webscr?cmd=_s-xclick&hosted_button_id=UXNT7PRVZ5HGA
[winshowext]: http://support.microsoft.com/kb/865219
[wintargz]: http://gettingeek.com/how-to-create-tarball-compress-to-gzip-under-windows-tar-gz-379.html

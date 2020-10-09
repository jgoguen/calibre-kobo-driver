<!-- vim: set filetype=markdown:expandtab:ts=2:sts=2:sw=2: -->
<!-- markdownlint-enable -->
# Kobo KePub plugins

![CI](https://github.com/jgoguen/calibre-kobo-driver/workflows/CI/badge.svg) ![Lint](https://github.com/jgoguen/calibre-kobo-driver/workflows/Lint/badge.svg)

This provides a series of [calibre][calibre] extensions enabling calibre to work
with ePub files with Kobo's extra features (called **KePub**). The following
plugins are available:

- `KoboTouchExtended`: This is a device driver plugin extending the
  capabilities of the existing `KoboTouch` driver provided with Calibre to
  enable extra Kobo features. **Please note**: modified books are not saved back
  into your Calibre library to prevent issues with overwriting library
  configurations, so books get converted in transit to your device every time.
  In general, the extra time required should not be noticeable.
- `KePub Output`: This is a conversion plugin allowing calibre to convert any
  supported input format to KePub.
- `KePub Metadata Writer`: This is a metadata plugin which supports the
  `KePub Output` plugin. Installing this plugin allows calibre to write KePub
  metadata to the book as it's written out in calibre's conversion process. It
  serves no purpose without the `KePub Output` plugin.
- `KePub Input`: This is a conversion plugin allowing calibre to convert KePub
  to any supported output format.
- `KePub Metadata Reader`: This is a metadata plugin which allows calibre to
  read KePub metadata when converting a book from KePub format. It serves no
  purpose without the `KePub Input` plugin.

**WARNING: THE KEPUB FILE STRUCTURE IS NOT YET FULLY UNDERSTOOD. DO NOT, UNDER
ANY CIRCUMSTANCES, DELETE THE FILES FOR THE SOURCE FORMAT. ALWAYS HAVE A
NON-KEPUB FORMAT FOR YOUR BOOKS.**

When viewing a KePub book on a Kobo reader, a different viewer displays
the contents than an ePub file. The main benefits of using the KePub viewer are:

- Page numbers show the number of page turns remaining in the current chapter
  instead of the estimated number of pages for the entire book.
  - The `KoboTouchExtended` driver has an option to use full-book page numbers
    instead if you prefer that.
- Reading statistics (time left in this chapter, time for the next chapter,
  time to complete the book)
- The book title is at the top of each page.
- The chapter title, if any, is at the bottom of each page with the page
  numbers.

Depending on your preferences, there are some areas where the ePub renderer is
a better choice than the KePub renderer:

- Better hyphenation. The KePub renderer sometimes hyphenates words in the wrong
  place if they have trailing punctuation.
- Full justification works. The KePub renderer sometimes doesn't
  correctly justify lines with symbols represented by HTML entities (such as
  em-dashes or ellipses).
- Embedded fonts are better supported.

## Installation

To install the current release version of this plugin directly within calibre:

1. Open calibre's preferences, choose `Plugins`, and click `Get new plugins`
1. Select the name of the plugins you want to install from the list of
   available plugins and click `Install`
    1. Don't see it? You may already have it installed. Restart calibre and see
       if you get a notification of a pending update.
    1. If you want to install more than one plugin, you must select and install
       them one at a time. Calibre displays a notification asking you to restart
       after each one, but you can wait until after you've installed all desired
       plugins to restart calibre.
1. Restart calibre

## Download

To download this plugin, either clone the repository or download a snapshot. It
is not necessary to download this plugin in this way unless you want to install
from source for some reason, such as plugin development.

### Install from source

Please note, installation from source is not supported on Windows or macOS prior
to 11 (Big Sur). Run `scripts/build.sh` to generate the ZIP file package for all
plugins. You must have `python3` and `zsh` installed.

Windows users may be able to use Windows Subsystem for Linux to run the build
script, but this is not tested or supported.

Add the resulting ZIP file to calibre:

1. `Preferences`
1. `Plugins`
1. `Load plugin from file`

## Usage

To use the device driver plugin after installing:

1. Connect your supported Kobo device and wait for calibre to detect it
1. Select the books you want to send to your device.
1. Click the **Send to device** button.

To use the conversion output format plugin after installing:

1. Choose the book you want to convert to KePub format
1. Choose the **KEPUB** format from the list of output formats (top-right of the
   conversion window)
1. Choose **KePub Options** from the left menu and make your option selections
1. Click **OK**

**WARNING: THE KEPUB FILE STRUCTURE IS NOT YET FULLY UNDERSTOOD. DO NOT, UNDER
ANY CIRCUMSTANCES, DELETE THE FILES FOR THE SOURCE FORMAT. ALWAYS HAVE A
NON-KEPUB FORMAT FOR YOUR BOOKS.**

To use the conversion input format plugin after installing:

1. Choose the KePub book you want to convert to a different format
1. Choose the desired target format from the list of output formats (top-right
   of the conversion window)
1. Click **OK**

### Special Note

You should turn off the built-in KoboTouch driver (authored by David Forrester)
while using this plugin. On rare occasions, calibre may inadvertently select the
built-in KoboTouch driver instead of this plugin. But do not turn off the
built-in Kobo driver.

### Adding Arbitrary Styles

The device driver plugin, through the base KoboTouch driver provided with
calibre, can copy all rules from a specific CSS file into each book during
upload. To support maintaining device-specific CSS files, the device driver can
copy a CSS file into the correct place to allow adding it to each book. To do
this, locate the calibre plugin directory, create a CSS file in there, and
select the **Modify CSS** option in the driver preferences. To locate the
calibre plugin directory, open calibre's preferences, choose **Miscellaneous**,
and click the **Open calibre configuration directory** button. The plugin
directory is in there.

The name of the CSS file must be in the format `kobo_extra_<DEVICE>.css`. The
plugins support the following replacements for `<DEVICE>` (capitalization is
important):

- Kobo Aura H2O&mdash;AURAH2O (`kobo_extra_AURAH2O.css`)
- Kobo Aura HD&mdash;AURAHD (`kobo_extra_AURAHD.css`)
- Kobo Aura&mdash;AURA (`kobo_extra_AURA.css`)
- Kobo Clara&mdash;CLARA (`kobo_extra_CLARA.css`)
- Kobo Forma&mdash;FORMA (`kobo_extra_FORMA.css`)
- Kobo Glo&mdash;GLO (`kobo_extra_GLO.css`)
- Kobo Glo HD&mdash;GLOHD (`kobo_extra_GLOHD.css`)
- Kobo Libra&mdash;LIBRA (`kobo_extra_LIBRA.css`)
- Kobo Mini&mdash;MINI (`kobo_extra_MINI.css`)
- Kobo Touch&mdash;TOUCH (`kobo_extra_TOUCH.css`)

Please note, this overwrites any `kobo_extra.css` you may have already sent to
your Kobo device. If you have created the `kobo_extra.css` file on your Kobo
device already and you want to make use of this feature, you must copy
`kobo_extra.css` to the calibre plugin directory.

Please also be aware that support for some Kobo devices (the Aura H2O, Libra,
Forma, etc.) was not added until later calibre versions than the earliest
version required for this plugin. Accordingly, you'll need to be running a
calibre version with support for your device for this feature to work for all
devices.

### Hyphenation

The driver plugin and the conversion output plugin includes the ability to add a
CSS file to each book enabling KePub hyphenation. The standard hyphenation
dictionaries provided on Kobo devices are somewhat deficient for some languages;
fixing this (or adding your own dictionary) requires a little work and requires
that you can create gzipped tarballs (.tgz files). Note that you can update
existing dictionaries but you cannot add new ones.

1. Somewhere on your computer, create the directory structure
   `usr/local/Kobo/hyphenDicts` (capitalization is important)
1. Download the LibreOffice hyphenation dictionary for your language
    1. You're looking for a file with the `oxt` extension. This is just a ZIP
       archive with a different name.
1. Unzip the OXT file (Windows users need to rename the file to change the
   extension to `zip`, which requires configuring Explorer to [show file
   extensions][winshowext], which is a good idea to do anyway) and look for the
   file named as `hyph_[language].dic`.
1. Copy the hyphenation dictionary to the `hyphenDicts` folder without changing
   the name.
1. Add the `usr` folder to `KoboRoot.tgz`
    1. UNIX users (Linux, Solaris, BSD, Mac, etc.) can, from a terminal window,
       run `tar czf KoboRoot.tgz usr/` from wherever you put the `usr` directory.
    1. Windows users, you're on your own. You may be able to use the free [7-Zip
       archiver][7zip] to create .tgz files. See [this article][wintargz] for
       more details.
        1. If you follow these directions, your file should have the extension
           `.tar.gz`. Rename this to `.tgz` after creating the file and ignore
           the Windows warning about changing file extensions.

Once you have created `KoboRoot.tgz` copy it to the `.kobo` directory on your
Kobo device, unmount/eject the drive, and unplug the device. You'll see a screen
indicating that the Kobo device is updating; it isn't, but this method takes
advantage of the Kobo update mechanism to load the necessary dictionary files
and the Kobo device cannot distinguish between this and a real software update.
Make sure you keep your version of `KoboRoot.tgz` around, you'll need to
re-apply it after every Kobo software update.

Provided languages are:

1. United States English (en\_US)
2. French (fr\_FR)
3. Spanish (es\_ES)
4. German (de\_DE)
5. Italian (it\_IT)
6. Portuguese (pt\_PT)
7. Dutch (nl\_NL)

Please note that even with this feature, hyphenation is not exact. Also remember
that you can update existing dictionaries but not add new dictionaries.

### Kobo JavaScript Extraction

Both the driver and conversion output plugins include the ability to extract the
Kobo JavaScript file from a free Kobo-supplied KePub which is not encumbered by
any Digital Restrictions Management (DRM). To avoid distributing any of Kobo's
copyrighted work, enabling this requires a little work:

1. Get a KePub file from Kobo without any Digital Restrictions Management.
    1. Some of [Kobo's free ebooks][kobofreebooks] do not have DRM.
    1. In some regions, Kobo devices have free ebooks pre-loaded in the
       `.kobo/kepub/` folder on the device which do not have DRM.
1. Copy the KePub file to the calibre plugins directory
    1. To find the plugins directory, open calibre's preferences, choose
       **Miscellaneous**, and click **Open calibre configuration directory**
    1. Go to the **plugins** directory
1. Rename the KePub file to `reference.kepub.epub`
    1. Windows users must be sure to [show file extensions in Windows
       Explorer][winshowext] to be able to rename the file.

Once this file is in place with the correct name, the driver and conversion
output plugins automatically extracts the Kobo JavaScript file, add it to books
during conversion, and add appropriate references to content files.

### Generated KePub File Copying

On occasion, such as for debugging purposes, you may wish to have easy access to
the generated KePub file. The device driver plugin has an option which allows
you to enter the full, absolute path to a directory to copy generated files to
after conversion. This directory must:

1. Be somewhere you can write to
1. Contain no variables
    1. OS X and Linux users may use a tilde (~) to refer to their home directory
       instead of typing it in full (`~/calibre-debug` instead of
       `/home/jgoguen/calibre-debug`). Windows users must always enter a full
       path.

The final path is a combination of this path and the save template for the
plugin. If your debug path is `/home/jgoguen/calibre-debug` and your save
template is `{author_sort}/{title}` then a KePub file gets copied to, for
example, `/home/jgoguen/calibre-debug/Camerata, Jo/A History of Vanguard
Industries.kepub.epub`. Directories get created as needed.

## Contributing

Decided you want to contribute to the development of these plugins?

1. **Contribute code**, whether for existing bug reports, for new bugs that you
   found, or for new features that you want to see implemented. To contribute
   code, you may fork the repository and send a Github pull request, or you may
   send me a PM on MobileRead with a git patch file.
1. **Submit bug reports**. Bug reports are my to-do list for this plugin; any
   requests anywhere else may get missed and forgotten and direct emails **are
   ignored**. Although I'm happy to discuss the plugins on the MobileRead
   forums, I may still need you to create a bug report; this is so I actually
   remember to investigate your request.
1. **Test pre-released code** from Github. Between releases, new code is
   committed to the Github repository. Submit any bug reports, feedback, feature
   requests you think of during your testing.
1. **Translate text**. Translations use the [Transifex translation
   project](https://www.transifex.com/joel-goguen/calibre-kobo-driver/).

You may also prefer to contribute in some other way. You may contribute by
answering questions from other people who may have issues, continuing to use
this plugin and providing feedback, assisting with purchasing new Kobo readers
for continued testing, and probably other ways I haven't thought of yet.

### Contributors

Thanks goes to these, and others, for their help and contributions to this
project ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tr>
    <td align="center"><a href="https://github.com/hub2git"><img src="https://avatars3.githubusercontent.com/u/7141051?v=4" width="100px;" alt=""/><br /><sub><b>hub2git</b></sub></a><br /><a href="https://github.com/jgoguen/calibre-kobo-driver/commits?author=hub2git" title="Documentation">📖</a></td>
    <td align="center"><a href="https://github.com/dchawisher"><img src="https://avatars0.githubusercontent.com/u/22660616?v=4" width="100px;" alt=""/><br /><sub><b>dchawisher</b></sub></a><br /><a href="https://github.com/jgoguen/calibre-kobo-driver/issues?q=author%3Adchawisher" title="Bug reports">🐛</a></td>
    <td align="center"><a href="https://github.com/Byte6d65"><img src="https://avatars3.githubusercontent.com/u/66903648?v=4" width="100px;" alt=""/><br /><sub><b>Byte6d65</b></sub></a><br /><a href="https://github.com/jgoguen/calibre-kobo-driver/issues?q=author%3AByte6d65" title="Bug reports">🐛</a></td>
    <td align="center"><a href="https://github.com/NiLuJe"><img src="https://avatars3.githubusercontent.com/u/111974?v=4" width="100px;" alt=""/><br /><sub><b>NiLuJe</b></sub></a><br /><a href="https://github.com/jgoguen/calibre-kobo-driver/commits?author=NiLuJe" title="Code">💻</a></td>
    <td align="center"><a href="https://github.com/davidfor"><img src="https://avatars0.githubusercontent.com/u/4010598?v=4" width="100px;" alt=""/><br /><sub><b>David</b></sub></a><br /><a href="https://github.com/jgoguen/calibre-kobo-driver/commits?author=davidfor" title="Code">💻</a></td>
  </tr>
</table>

<!-- markdownlint-enable -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

## Asking Questions

Wondering how to do something? Want to know if something is possible? Post your
question on the MobileRead Forum thread for the relevant plugin:

- [`KoboTouchExtended`][devicethread]
- [`KePub Output`][kepubout]
- [`KePub Metadata Writer`][mdwriter]
- [`KePub Input`][kepubin]
- [`KePub Metadata Reader`][mdreader]

## Reporting a Bug

Found a bug with this plugin? Please go to [Github and submit a new bug
report](https://github.com/jgoguen/calibre-kobo-driver/issues/new). Under no
circumstances should you send a direct email without first checking with me. At
my sole discretion **I may not read emails I haven't asked for**. Everyone
benefits from a public bug tracker, but one person benefits from a private
email.

When submitting a bug, I require the following information but any extra
information is good to include:

1. What version of calibre and plugin you are using. If you are not on the
   latest plugin version, you must update before submitting any bug report. If
   you are not on the latest version of calibre, I may not be able to reproduce
   the issue.
2. The full error message reported by calibre, if any.
3. For issues processing books, if you have a book that you are able to include
   that demonstrates the issue or not. DO NOT UPLOAD EBOOK FILES TO THE ISSUE
   TRACKER! Under no circumstances are you allowed to upload copyrighted content
   to a public bug. If I need a book file I'll send you a link to use to upload
   one.
4. The calibre debug log. Bug reports without this get the `needs-information`
   tag applied.
    1. To get the calibre debug log, click the arrow beside the "Preferences"
       menu, choose "Restart in debug mode", repeat the same action that caused
       the issue, and close calibre. The debug log is automatically displayed to
       you.

## Known Issues

If you have installed the device driver plugin in calibre 0.9.18 or
earlier, then you upgrade to calibre 0.9.19 or later and can't update the
plugin or install the conversion output format plugin, you must manually
replace the device driver plugin ZIP file:

1. Download the latest version of the code.
1. Generate a new plugin ZIP file.
1. Shut down calibre entirely.
1. Open the calibre plugin directory.
    1. Don't know where this is? Before you close calibre, open calibre's
       preferences, choose **Miscellaneous**, and click the **Open calibre
       configuration directory** button. The plugin directory is in there.
1. Replace the file named **KoboTouchExtended.zip** with the new version you
   created. Please make sure the filename remains the same.

If you get an error like the following:

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

The solution is to re-read the Known Issues section.

[7zip]: http://www.7-zip.org/download.html
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

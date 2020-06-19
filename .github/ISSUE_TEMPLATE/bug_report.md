---
name: Bug report
about: Report an error in the current functionality of a plugin from this repository
title: ''
labels: ''
assignees: ''
---
<!-- markdownlint-disable MD025 MD034 -->

# Bug Checklist

These items are mandatory. If you need help finding this information submit the
bug report with as much completed as you can and ask for help finding the rest.

- [ ] I am using the latest version of calibre to report this bug, which is:
- [ ] I am using an official calibre release, not one from a third party (e.g.
    your Linux distro, Flatpak, Chocolatey package, Homebrew, etc.)
- [ ] I am using the latest version of this plugin, which is:
- [ ] My operating system is (e.g. Windows 10, Windows 8.1, Windows 8, macOS
    10.15.5, Fedora 32, Arch Linux, etc.):
- [ ] I have included the full, complete, unmodified debug log from calibre
  - Directions for getting the debug log are under the "Logs" header below.
- [ ] I have translated the text in any screenshots and logs to English, or all
    screenshots and logs included are in English.

These items are optional. Fill in as much of them as possible. If something is
not applicable to your bug report, note that.

- [ ] I have installed the Scramble Epub plugin (see
    https://www.mobileread.com/forums/showthread.php?t=267998) and will attach
    a **scrambled** copy of the book I'm having problems with (attach a file by
    dragging and dropping onto the Github editor).
  - [ ] If this is a conversion bug, I will also attach a **scrambled** copy of
    the converted book.
- [ ] The path to my calibre library or to a book in my calibre library has
    non-ASCII characters: yes/no
- [ ] If I am using Windows 10, I (have/have not) enabled Windows' beta support
      for Unicode (see
      https://www.mobileread.com/forums/showpost.php?p=3988195&postcount=2052)
- [ ] If I am using Windows 10, does this bug happens with beta Unicode support
    both enabled and disabled, only when enabled, or only when disabled?

# Describe the bug

A clear and concise description of what the bug is.

## Steps to Reproduce

Steps to reproduce the behavior (as detailed as you can):

1. Go to '...'
1. Click on '....'
1. Scroll down to '....'
1. See error

## Expected behavior

A clear and concise description of what you expected to happen.

## Actual behaviour

A clear and concise description of the actual behaviour you observe. This may be a summary of the bug description.

## Screenshots

If applicable, add screenshots to help explain your problem. If you are using
calibre in any language other than English, please either provide a translation
of any relevant text to English or switch calibre to use English first.

## Logs

Restart calibre in debug mode. Paste the full calibre debug log here. To get the
debug log:

1. Find the `Preferences` button in the calibre toolbar.
1. Click the arrow to the right of `Preferences`.
1. Select the `Restart in debug mode` menu item.
   1. This will shut down and restart calibre immediately. Calibre will
      automatically restart, but it may take a few seconds.
   1. You will see a notification informing you that you have started calibre
      in debug mode. Click `OK`.
1. Do the minimum possible steps to reproduce the bug.
1. Close calibre.
   1. This will automatically display the debug log. Copy and paste the entire
      log in the blank space here (between `` ```text `` and `` ``` ``)

```text

```

## Additional context

Add any other information you think might be helpful.

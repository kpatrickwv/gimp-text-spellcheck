# Spellcheck Text Layers for GIMP 3

A GIMP 3 plug-in that spellchecks every text layer in an image. Layers with
misspelled words are flagged with a red color tag in the Layers dock, and a
review dialog walks you through each word with suggested corrections.

Built for images with many text layers, where checking each one by eye is
slow and error-prone.

## Features

- Checks every text layer in the image, including layers inside groups
- Flags layers with misspellings using a red color tag, and restores any
  color tag the layer had before once it's fixed
- Review dialog with suggestions, plus Replace, Replace All, Ignore,
  Ignore All, and Add to Dictionary
- Preserves styling: bold, italics, colors, and fonts on individual words
  survive corrections
- Matches capitalization: "Teh" becomes "The", "TEH" becomes "THE"
- Personal dictionary shared across all your images
- Per-image ignore list saved inside the .xcf file
- Every change can be undone with Ctrl+Z
- Works on Linux, macOS, and Windows with no extra software to install

## Requirements

GIMP 3.0 or newer. Developed and tested on GIMP 3.2. It will not work on
GIMP 2.10.

## Installation

1. Download `text-spellcheck.zip` from the
   [Releases page](https://github.com/kpatrickwv/gimp-text-spellcheck/releases).
   **Don't use the green "Code > Download ZIP" button.** GIMP requires the
   plug-in folder to be named exactly `text-spellcheck`, and that button
   names it something else, so the plug-in silently won't load.

2. Unzip it into your personal GIMP plug-ins folder, so you end up with
   `plug-ins/text-spellcheck/text-spellcheck.py`. To find the folder, open
   **Edit > Preferences > Folders > Plug-ins** in GIMP. Typical locations:

   | System | Folder |
   | --- | --- |
   | Linux | `~/.config/GIMP/3.2/plug-ins/` |
   | Linux (Flatpak) | `~/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins/` |
   | macOS | `~/Library/Application Support/GIMP/3.2/plug-ins/` |
   | Windows | `%APPDATA%\GIMP\3.2\plug-ins\` |

   Replace `3.2` with your GIMP version if it's different.

3. On Linux and macOS, make the script executable:

   ```bash
   chmod +x ~/.config/GIMP/3.2/plug-ins/text-spellcheck/text-spellcheck.py
   ```

   (Adjust the path to match your folder from step 2.)

4. Restart GIMP.

## Usage

Open an image and choose **Tools > Spellcheck Text Layers...**

Text layers containing misspelled words turn red in the Layers dock, and
the review dialog opens on the first one. For each word:

| Button | What it does |
| --- | --- |
| Replace | Fix this occurrence |
| Replace All | Fix this word in every text layer |
| Ignore | Skip this occurrence (the layer stays flagged) |
| Ignore All | Ignore this word everywhere in this image (saved in the .xcf) |
| Add to Dictionary | Never flag this word again, in any image |

**Keyboard:** arrow keys choose a suggestion, Enter replaces, and
Alt + the underlined letter triggers a button.

If there's no good suggestion, type your correction in the **Change to**
box. Only the word itself is replaced. Punctuation around it is left alone,
so don't retype a trailing period or comma.

Running the check again clears old red tags first, so the tags always
reflect the current state of the image.

## Your dictionary

Words added with **Add to Dictionary** are saved one per line in
`spellcheck-words.txt` in your GIMP profile folder (the folder that
contains `plug-ins`). You can edit it in any text editor, or copy it to
another computer.

## Limitations

- **English only** for now.
- **It checks spelling, not usage.** A real word used wrongly, like "untie"
  for "unite" or "there" for "their", won't be flagged.
- **Suggestions are ranked by how common a word is**, so the list sometimes
  includes rare words further down. The top suggestion is usually right.
- **Corrections to split-styled words:** if a word is styled partway
  through (half bold, half not), the corrected word takes the style of its
  first letter.

## Troubleshooting

**The plug-in doesn't appear in the Tools menu.** Check that the folder is
named exactly `text-spellcheck`, that it's in a folder listed under
**Edit > Preferences > Folders > Plug-ins**, and on Linux/macOS that the
script is executable. Then restart GIMP.

**Something goes wrong.** Launch GIMP from a terminal and run the plug-in
again. Python errors appear in the terminal. Please include that output
when you [open an issue](https://github.com/kpatrickwv/gimp-text-spellcheck/issues).

## Credits

Spellchecking uses [pyspellchecker](https://github.com/barrust/pyspellchecker)
by Tyler Barrus, bundled under its MIT license (see
`text-spellcheck/vendor/spellchecker/LICENSE`).

## License

MIT. See [LICENSE](LICENSE).

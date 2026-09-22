Spellcheck Text Layers - GIMP 3 plug-in
=======================================

INSTALL
1. In GIMP, open Edit > Preferences > Folders > Plug-ins to see your
   plug-in folders. Use the one inside your personal profile, typically:
     Linux:    ~/.config/GIMP/3.2/plug-ins/
     Flatpak:  ~/.var/app/org.gimp.GIMP/config/GIMP/3.2/plug-ins/
     macOS:    ~/Library/Application Support/GIMP/3.2/plug-ins/
     Windows:  %APPDATA%\GIMP\3.2\plug-ins\
2. Copy the whole "text-spellcheck" folder there. The folder name must
   stay exactly "text-spellcheck" (it has to match the .py file inside).
3. Linux/macOS only: make the script executable:
     chmod +x text-spellcheck/text-spellcheck.py
4. Restart GIMP.

USE
Tools > Spellcheck Text Layers...
Text layers with misspelled words get a red color tag in the Layers dock.
The review dialog walks through each word. Keyboard: arrow keys pick a
suggestion, Enter replaces, Alt+underlined letter triggers a button.

  Replace            fix this occurrence
  Replace All        fix this word in every text layer
  Ignore             skip this occurrence (layer stays flagged)
  Ignore All         ignore this word in this image (saved in the .xcf)
  Add to Dictionary  never flag this word again, in any image

Every change is undoable with Ctrl+Z. Running the check again clears the
old red tags first and restores any color tag a layer had before.

YOUR DICTIONARY
Words you add are stored one per line in "spellcheck-words.txt" in your
GIMP profile folder (the folder that contains plug-ins/). You can edit it
by hand or copy it between machines.

CREDITS
Spellchecking uses pyspellchecker by Tyler Barrus (MIT license, see
vendor/spellchecker/LICENSE).

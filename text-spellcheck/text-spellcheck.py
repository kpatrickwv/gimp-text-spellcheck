#!/usr/bin/env python3
# Spellcheck Text Layers - a GIMP 3 plug-in.
# https://github.com/kpatrickwv/gimp-text-spellcheck
# Version 1.0.0, MIT License
# Flags text layers containing misspelled words with a red color tag and
# walks through them in a review dialog with suggested corrections.

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [_HERE, os.path.join(_HERE, "vendor")]

import gi
gi.require_version("Gimp", "3.0")
gi.require_version("GimpUi", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gimp, GimpUi, GLib, Gtk

import spellcore

PROC_NAME = "plug-in-text-spellcheck"
FLAG_PARASITE = "text-spellcheck-flag"        # on layers we colored red
IGNORE_PARASITE = "text-spellcheck-ignore"    # on the image: "Ignore All" words
# Undoable so Ctrl+Z restores our markers along with the color tags they track.
PARASITE_FLAGS = (getattr(Gimp, "PARASITE_PERSISTENT", 1)
                  | getattr(Gimp, "PARASITE_UNDOABLE", 2))


# ---------------------------------------------------------------------------
# GIMP helpers
# ---------------------------------------------------------------------------

def make_parasite(name, text):
    data = text.encode("utf-8")
    try:
        return Gimp.Parasite.new(name, PARASITE_FLAGS, list(data))
    except TypeError:
        return Gimp.Parasite.new(name, PARASITE_FLAGS, data)


def parasite_text(parasite):
    data = parasite.get_data()
    return bytes(data).decode("utf-8", "replace") if data else ""


def all_layers(parent_items):
    for layer in parent_items:
        yield layer
        if layer.is_group():
            yield from all_layers(layer.get_children())


def text_layers(image):
    result = []
    for layer in all_layers(image.get_layers()):
        if layer.is_text_layer():
            result.append(Gimp.TextLayer.get_by_id(layer.get_id()))
    return result


def read_layer(tl):
    markup = tl.get_markup()
    if markup:
        return spellcore.LayerText(markup, True)
    return spellcore.LayerText(tl.get_text() or "", False)


def write_layer(tl, lt, old_plain):
    old_name = tl.get_name()
    if lt.is_markup:
        tl.set_markup(lt.serialize())
    else:
        tl.set_text(lt.serialize())
    # Keep auto-named layers in sync with their corrected text, in case
    # GIMP didn't rename it already.
    new_name = spellcore.auto_layer_name(lt.plain)
    if (old_name == spellcore.auto_layer_name(old_plain)
            and tl.get_name() == old_name and new_name != old_name):
        tl.set_name(new_name)


def set_flag(layer, flagged):
    """Color a layer red (remembering its old tag), or restore it."""
    p = layer.get_parasite(FLAG_PARASITE)
    if flagged:
        if p is None:
            prev = int(layer.get_color_tag())
            layer.attach_parasite(make_parasite(FLAG_PARASITE, str(prev)))
        layer.set_color_tag(Gimp.ColorTag.RED)
    elif p is not None:
        if layer.get_color_tag() == Gimp.ColorTag.RED:
            try:
                layer.set_color_tag(Gimp.ColorTag(int(parasite_text(p))))
            except (ValueError, TypeError):
                layer.set_color_tag(Gimp.ColorTag.NONE)
        layer.detach_parasite(FLAG_PARASITE)


# ---------------------------------------------------------------------------
# Review session
# ---------------------------------------------------------------------------

class Session:
    def __init__(self, image, checker):
        self.image = image
        self.checker = checker
        self.layers = text_layers(image)
        p = image.get_parasite(IGNORE_PARASITE)
        self.ignores = {w for w in parasite_text(p).split("\n") if w} if p else set()
        self.idx = 0
        self.cursor = 0
        self.current = None   # (layer, LayerText, start, end, word)
        self.replaced = 0

    def issues(self, tl):
        lt = read_layer(tl)
        return lt, self.checker.misspellings(lt.plain, self.ignores)

    def refresh_flags(self, layers=None):
        layers_to_check = self.layers if layers is None else layers
        for tl in layers_to_check:
            set_flag(tl, bool(self.issues(tl)[1]))

    def clear_stale_flags(self):
        # Layers flagged on an earlier run that are no longer text layers.
        for layer in all_layers(self.image.get_layers()):
            if not layer.is_text_layer() and layer.get_parasite(FLAG_PARASITE):
                set_flag(layer, False)

    def advance(self):
        while self.idx < len(self.layers):
            tl = self.layers[self.idx]
            lt, found = self.issues(tl)
            for s, e, w in found:
                if s >= self.cursor:
                    self.current = (tl, lt, s, e, w)
                    return True
            self.idx += 1
            self.cursor = 0
        self.current = None
        return False

    def _edit(self, fn):
        self.image.undo_group_start()
        try:
            fn()
        finally:
            self.image.undo_group_end()
        Gimp.displays_flush()

    def replace(self, new):
        tl, lt, s, e, w = self.current
        if new == w:
            self.ignore_once()
            return
        old_plain = lt.plain

        def do():
            lt.replace(s, e, new)
            write_layer(tl, lt, old_plain)
            set_flag(tl, bool(self.issues(tl)[1]))
        self._edit(do)
        self.cursor = s + len(new)
        self.replaced += 1
        self.advance()

    def replace_all(self, new):
        tl_cur, _, s_cur, _, w_cur = self.current
        key = spellcore.normalize(w_cur)
        # If the replacement is just a case-matched word, re-case it per
        # occurrence ("teh" -> "the", "TEH" -> "THE"); otherwise use it as typed.
        adaptive = new == spellcore.match_case(w_cur, new.lower())
        new_cursor = None

        def do():
            nonlocal new_cursor
            for tl in self.layers:
                lt, found = self.issues(tl)
                targets = [x for x in found if spellcore.normalize(x[2]) == key]
                if not targets:
                    continue
                old_plain = lt.plain
                delta_before = 0
                for s, e, w in reversed(targets):
                    rep = spellcore.match_case(w, new.lower()) if adaptive else new
                    lt.replace(s, e, rep)
                    if tl.get_id() == tl_cur.get_id():
                        if s < s_cur:
                            delta_before += len(rep) - (e - s)
                        elif s == s_cur:
                            new_cursor = s + len(rep)
                    self.replaced += 1
                if tl.get_id() == tl_cur.get_id() and new_cursor is not None:
                    new_cursor += delta_before
                write_layer(tl, lt, old_plain)
                set_flag(tl, bool(self.issues(tl)[1]))
        self._edit(do)
        if new_cursor is not None:
            self.cursor = new_cursor
        self.advance()

    def ignore_once(self):
        self.cursor = self.current[3]
        self.advance()

    def ignore_all(self):
        self.ignores.add(spellcore.normalize(self.current[4]))
        self._edit(lambda: self.image.attach_parasite(
            make_parasite(IGNORE_PARASITE, "\n".join(sorted(self.ignores)))))
        self._after_word_accepted()

    def add_to_dictionary(self):
        self.checker.add_word(self.current[4])
        self._after_word_accepted()

    def _after_word_accepted(self):
        # The word may appear in layers already reviewed; unflag those too.
        self._edit(self.refresh_flags)
        self.advance()


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class ReviewDialog:
    def __init__(self, session):
        self.s = session
        GimpUi.init(PROC_NAME)
        d = self.dialog = GimpUi.Dialog(use_header_bar=False,
                                        title="Spellcheck Text Layers",
                                        role=PROC_NAME)
        d.add_button("_Close", Gtk.ResponseType.CLOSE)
        d.set_default_size(560, -1)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        outer.set_border_width(12)
        d.get_content_area().pack_start(outer, True, True, 0)

        self.layer_label = Gtk.Label(xalign=0)
        outer.pack_start(self.layer_label, False, False, 0)

        self.context = Gtk.Label(xalign=0, wrap=True, selectable=False)
        self.context.set_max_width_chars(60)
        frame = Gtk.Frame()
        ctx_box = Gtk.Box(border_width=8)
        ctx_box.pack_start(self.context, True, True, 0)
        frame.add(ctx_box)
        outer.pack_start(frame, False, False, 0)

        body = Gtk.Box(spacing=12)
        outer.pack_start(body, True, True, 0)

        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.pack_start(left, True, True, 0)

        change_row = Gtk.Box(spacing=6)
        lbl = Gtk.Label(label="Change _to:", use_underline=True)
        self.entry = Gtk.Entry()
        lbl.set_mnemonic_widget(self.entry)
        self.entry.connect("activate", lambda *_: self.on_replace())
        change_row.pack_start(lbl, False, False, 0)
        change_row.pack_start(self.entry, True, True, 0)
        left.pack_start(change_row, False, False, 0)

        self.store = Gtk.ListStore(str)
        self.view = Gtk.TreeView(model=self.store, headers_visible=False)
        self.view.append_column(Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=0))
        self.view.get_selection().connect("changed", self.on_suggestion_selected)
        self.view.connect("row-activated", lambda *_: self.on_replace())
        scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        scroll.set_min_content_height(170)
        scroll.add(self.view)
        sug_lbl = Gtk.Label(label="_Suggestions:", use_underline=True, xalign=0)
        sug_lbl.set_mnemonic_widget(self.view)
        left.pack_start(sug_lbl, False, False, 0)
        left.pack_start(scroll, True, True, 0)

        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        body.pack_start(right, False, False, 0)
        self.buttons = []
        for label, handler, tip in [
            ("_Replace", self.on_replace, "Replace this occurrence"),
            ("Replace _All", self.on_replace_all, "Replace this word in every text layer"),
            ("_Ignore", self.on_ignore, "Skip this occurrence (the layer stays flagged)"),
            ("I_gnore All", self.on_ignore_all, "Ignore this word everywhere in this image (saved with the image)"),
            ("Add to _Dictionary", self.on_add, "Never flag this word again, in any image"),
        ]:
            b = Gtk.Button.new_with_mnemonic(label)
            b.set_tooltip_text(tip)
            b.connect("clicked", lambda _b, h=handler: h())
            right.pack_start(b, False, False, 0)
            self.buttons.append(b)

        self.status = Gtk.Label(xalign=0)
        self.status.get_style_context().add_class("dim-label")
        outer.pack_start(self.status, False, False, 0)

    # -- display -----------------------------------------------------------

    def show_current(self):
        cur = self.s.current
        if cur is None:
            self.layer_label.set_markup("<b>Spellcheck complete</b>")
            n = self.s.replaced
            self.context.set_text(
                "No more misspelled words." if n == 0 else
                f"Done. {n} correction{'s' if n != 1 else ''} made.")
            self.entry.set_text("")
            self.store.clear()
            for w in self.buttons + [self.entry, self.view]:
                w.set_sensitive(False)
            self.status.set_text("Layers still flagged red have words you skipped with Ignore.")
            self.dialog.get_widget_for_response(Gtk.ResponseType.CLOSE).grab_focus()
            return

        tl, lt, s, e, w = cur
        esc = GLib.markup_escape_text
        self.layer_label.set_markup(
            f"<b>Layer:</b> {esc(tl.get_name())}   "
            f"<span alpha='60%'>({self.s.idx + 1} of {len(self.s.layers)} text layers)</span>")

        plain = lt.plain
        a, b = max(0, s - 60), min(len(plain), e + 60)
        before = ("…" if a > 0 else "") + plain[a:s]
        after = plain[e:b] + ("…" if b < len(plain) else "")
        self.context.set_markup(
            esc(before.replace("\n", " ")) +
            "<span foreground='#d33' weight='bold' underline='error' underline_color='#d33'>"
            + esc(w) + "</span>" + esc(after.replace("\n", " ")))

        self.store.clear()
        suggestions = self.s.checker.suggestions(w)
        for sug in suggestions:
            self.store.append([sug])
        self.entry.set_text(suggestions[0] if suggestions else w)
        if suggestions:
            self.view.get_selection().select_path(Gtk.TreePath.new_first())
        self.view.set_sensitive(bool(suggestions))
        self.view.grab_focus() if suggestions else self.entry.grab_focus()
        self.status.set_text("" if suggestions else "No suggestions. Type a correction or ignore the word.")

        try:
            self.s.image.set_selected_layers([tl])
        except Exception:
            pass

    def on_suggestion_selected(self, selection):
        model, it = selection.get_selected()
        if it is not None:
            self.entry.set_text(model[it][0])

    # -- actions -----------------------------------------------------------

    def _guard(self, fn):
        try:
            fn()
        except Exception as exc:
            Gimp.message(f"Spellcheck: {exc}")
            self.s.advance()
        self.show_current()

    def on_replace(self):
        new = self.entry.get_text()
        if self.s.current and new.strip():
            self._guard(lambda: self.s.replace(new))

    def on_replace_all(self):
        new = self.entry.get_text()
        if self.s.current and new.strip():
            self._guard(lambda: self.s.replace_all(new))

    def on_ignore(self):
        if self.s.current:
            self._guard(self.s.ignore_once)

    def on_ignore_all(self):
        if self.s.current:
            self._guard(self.s.ignore_all)

    def on_add(self):
        if self.s.current:
            self._guard(self.s.add_to_dictionary)

    def run(self):
        self.show_current()
        self.dialog.show_all()
        self.dialog.run()
        self.dialog.destroy()


# ---------------------------------------------------------------------------
# Plug-in registration
# ---------------------------------------------------------------------------

class TextSpellcheck(Gimp.PlugIn):
    def do_query_procedures(self):
        return [PROC_NAME]

    def do_set_i18n(self, name):
        return False

    def do_create_procedure(self, name):
        proc = Gimp.ImageProcedure.new(self, name, Gimp.PDBProcType.PLUGIN,
                                       self.run, None)
        proc.set_image_types("*")
        proc.set_sensitivity_mask(Gimp.ProcedureSensitivityMask.ALWAYS)
        proc.set_menu_label("_Spellcheck Text Layers...")
        proc.add_menu_path("<Image>/Tools")
        proc.set_documentation(
            "Spellcheck all text layers",
            "Flags text layers containing misspelled words with a red color "
            "tag and opens a review dialog with suggested corrections.",
            name)
        proc.set_attribution("kpatrickwv", "kpatrickwv", "2026")
        return proc

    def run(self, procedure, run_mode, image, drawables, config, run_data):
        try:
            user_dict = os.path.join(Gimp.directory(), "spellcheck-words.txt")
            checker = spellcore.Checker(user_dict)
        except Exception as exc:
            return procedure.new_return_values(
                Gimp.PDBStatusType.EXECUTION_ERROR,
                GLib.Error(f"Could not load the spellcheck dictionary: {exc}"))

        session = Session(image, checker)
        if not session.layers:
            Gimp.message("This image has no text layers to check.")
            return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())

        image.undo_group_start()
        try:
            session.clear_stale_flags()
            session.refresh_flags()
        finally:
            image.undo_group_end()
        Gimp.displays_flush()

        if run_mode == Gimp.RunMode.INTERACTIVE:
            session.advance()
            ReviewDialog(session).run()

        return procedure.new_return_values(Gimp.PDBStatusType.SUCCESS, GLib.Error())


Gimp.main(TextSpellcheck.__gtype__, sys.argv)

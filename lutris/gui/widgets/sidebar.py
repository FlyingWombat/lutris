"""Sidebar for the main window"""
from gettext import gettext as _

from gi.repository import GObject, Gtk, Pango

from lutris import platforms, runners, services
from lutris.database import categories as categories_db
from lutris.database import games as games_db
from lutris.game import Game
from lutris.gui.config.runner import RunnerConfigDialog
from lutris.gui.dialogs.runner_install import RunnerInstallDialog
from lutris.gui.dialogs.runners import RunnersDialog
from lutris.gui.widgets.utils import load_icon_theme
from lutris.util.jobs import AsyncCall

TYPE = 0
SLUG = 1
ICON = 2
LABEL = 3
GAMECOUNT = 4


class SidebarRow(Gtk.ListBoxRow):
    """A row in the sidebar containing possible action buttons"""
    MARGIN = 9
    SPACING = 6

    def __init__(self, id_, type_, name, icon, application=None):
        """Initialize the row

        Parameters:
            id_: identifier of the row
            type: type of row to display (still used?)
            name (str): Text displayed on the row
            icon (GtkImage): icon displayed next to the label
            application (GtkApplication): reference to the running application
        """
        super().__init__()
        self.application = application
        self.type = type_
        self.id = id_
        self.runner = None
        self.name = name

        self.box = Gtk.Box(spacing=self.SPACING, margin_start=self.MARGIN, margin_end=self.MARGIN)
        self.add(self.box)

        if not icon:
            icon = Gtk.Box(spacing=self.SPACING, margin_start=self.MARGIN, margin_end=self.MARGIN)
        self.box.add(icon)
        label = Gtk.Label(
            label=name,
            halign=Gtk.Align.START,
            hexpand=True,
            margin_top=self.SPACING,
            margin_bottom=self.SPACING,
            ellipsize=Pango.EllipsizeMode.END,
        )
        self.box.pack_start(label, True, True, 0)
        self.btn_box = Gtk.Box(spacing=3, no_show_all=True, valign=Gtk.Align.CENTER, homogeneous=True)
        self.box.pack_end(self.btn_box, False, False, 0)
        self.connect("realize", self.on_realize)

    def get_actions(self):
        return []

    def is_row_active(self):
        """Return true if the row is hovered or is the one selected"""
        flags = self.get_state_flags()
        # Naming things sure is hard... But "prelight" instead of "hover"? Come on...
        return flags & Gtk.StateFlags.PRELIGHT or flags & Gtk.StateFlags.SELECTED

    def do_state_flags_changed(self, previous_flags):  # pylint: disable=arguments-differ
        if self.id:
            self.update_buttons()
        Gtk.ListBoxRow.do_state_flags_changed(self, previous_flags)

    def update_buttons(self):
        if self.is_row_active():
            self.btn_box.show()
        elif self.btn_box.get_visible():
            self.btn_box.hide()

    def create_button_box(self):
        """Adds buttons in the button box based on the row's actions"""
        for action in self.get_actions():
            btn = Gtk.Button(tooltip_text=action[1], relief=Gtk.ReliefStyle.NONE, visible=True)
            image = Gtk.Image.new_from_icon_name(action[0], Gtk.IconSize.MENU)
            image.show()
            btn.add(image)
            btn.connect("clicked", action[2])
            self.btn_box.add(btn)

    def on_realize(self, widget):
        self.create_button_box()


class ServiceSidebarRow(SidebarRow):

    def __init__(self, service):
        super().__init__(
            service.id,
            "service",
            service.name,
            Gtk.Image.new_from_icon_name(service.icon, Gtk.IconSize.MENU)
        )
        self.service = service

    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        return [
            ("view-refresh-symbolic", _("Reload"), self.on_refresh_clicked)
        ]

    def on_refresh_clicked(self, _button):
        """Reload the service games"""
        self.service.wipe_game_cache()
        AsyncCall(self.service.load, None)


class OnlineServiceSidebarRow(ServiceSidebarRow):
    def get_buttons(self):
        return {
            "refresh": ("view-refresh-symbolic", _("Reload"), self.on_refresh_clicked),
            "disconnect": ("system-log-out-symbolic", _("Disconnect"), self.on_connect_clicked),
            "connect": ("avatar-default-symbolic", _("Connect"), self.on_connect_clicked)
        }

    def get_actions(self):
        buttons = self.get_buttons()
        if self.service.is_authenticated():
            return [buttons["refresh"], buttons["disconnect"]]
        return [buttons["connect"]]

    def on_connect_clicked(self, button):
        buttons = self.get_buttons()
        if self.service.is_authenticated():
            self.service.logout()
            new_button = buttons["connect"]
        else:
            self.service.login()
            new_button = buttons["disconnect"]
        button.set_tooltip_text(new_button[1])
        button.set_image(Gtk.Image.new_from_icon_name(new_button[0], Gtk.IconSize.MENU))


class RunnerSidebarRow(SidebarRow):
    def get_actions(self):
        """Return the definition of buttons to be added to the row"""
        if not self.id:
            return []
        entries = []

        # Creation is delayed because only installed runners can be imported
        # and all visible boxes should be installed.
        self.runner = runners.import_runner(self.id)()
        if self.runner.multiple_versions:
            entries.append((
                "system-software-install-symbolic",
                _("Manage Versions"),
                self.on_manage_versions,
            ))
        if self.runner.runnable_alone:
            entries.append(("media-playback-start-symbolic", _("Run"), self.runner.run))
        entries.append(("emblem-system-symbolic", _("Configure"), self.on_configure_runner))
        return entries

    def on_configure_runner(self, *_args):
        """Show runner configuration"""
        self.application.show_window(RunnerConfigDialog, runner=self.runner)

    def on_manage_versions(self, *_args):
        """Manage runner versions"""
        dlg_title = _("Manage %s versions") % self.runner.name
        RunnerInstallDialog(dlg_title, self.get_toplevel(), self.runner.name)


class SidebarHeader(Gtk.Box):
    """Header shown on top of each sidebar section"""

    def __init__(self, name):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.get_style_context().add_class("sidebar-header")
        label = Gtk.Label(
            halign=Gtk.Align.START,
            hexpand=True,
            use_markup=True,
            label="<b>{}</b>".format(name),
        )
        label.get_style_context().add_class("dim-label")
        box = Gtk.Box(margin_start=9, margin_top=6, margin_bottom=6, margin_right=9)
        box.add(label)
        self.add(box)
        if name == _("Runners"):
            manage_runners_button = Gtk.Button.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.MENU)
            manage_runners_button.props.action_name = "win.manage-runners"
            manage_runners_button.props.relief = Gtk.ReliefStyle.NONE
            manage_runners_button.set_margin_right(16)
            manage_runners_button.get_style_context().add_class("sidebar-button")
            box.add(manage_runners_button)
        self.add(Gtk.Separator())
        self.show_all()


class LutrisSidebar(Gtk.ListBox):
    __gtype_name__ = "LutrisSidebar"

    def __init__(self, application, selected=None):
        super().__init__()
        self.application = application
        self.get_style_context().add_class("sidebar")
        self.installed_runners = []
        self.active_platforms = games_db.get_used_platforms()
        self.runners = sorted(runners.__all__)
        self.platforms = sorted(platforms.__all__)
        self.categories = categories_db.get_categories()
        if selected:
            row_type, row_id = selected.split(":")
        else:
            row_type, row_id = ("runner", "all")

        GObject.add_emission_hook(RunnersDialog, "runner-installed", self.update)
        GObject.add_emission_hook(RunnersDialog, "runner-removed", self.update)
        GObject.add_emission_hook(Game, "game-updated", self.update)
        GObject.add_emission_hook(Game, "game-removed", self.update)

        load_icon_theme()

        self.add(
            SidebarRow(
                "running",
                "dynamic_category",
                _("Running"),
                Gtk.Image.new_from_icon_name("media-playback-start-symbolic", Gtk.IconSize.MENU)
            )
        )

        self.add(
            SidebarRow(
                "installed",
                "dynamic_category",
                _("Installed"),
                Gtk.Image.new_from_icon_name("drive-harddisk-symbolic", Gtk.IconSize.MENU)
            )
        )

        self.add(
            SidebarRow(
                "favorite",
                "category",
                _("Favorites"),
                Gtk.Image.new_from_icon_name("favorite-symbolic", Gtk.IconSize.MENU)
            )
        )

        service_classes = services.get_services()
        for service_name in service_classes:
            service = service_classes[service_name]()
            row_class = OnlineServiceSidebarRow if service.online else ServiceSidebarRow
            self.add(row_class(service))

        all_row = RunnerSidebarRow(None, "runner", _("All"), None)
        self.add(all_row)
        for runner_name in self.runners:
            icon_name = runner_name.lower().replace(" ", "") + "-symbolic"
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            runner = runners.import_runner(runner_name)()
            self.add(RunnerSidebarRow(runner_name, "runner", runner.human_name, icon, application=self.application))

        self.add(SidebarRow(None, "platform", _("All"), None))
        for platform in self.platforms:
            icon_name = (platform.lower().replace(" ", "").replace("/", "_") + "-symbolic")
            icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
            self.add(SidebarRow(platform, "platform", platform, icon))

        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.update()
        for row in self.get_children():
            if row.type == row_type and row.id == row_id:
                self.select_row(row)
                break
        self.show_all()

    def _filter_func(self, row):
        if not row or not row.id or row.type in ("category", "dynamic_category", "service"):
            return True
        if row.type == "runner":
            if row.id is None:
                return True  # 'All'
            return row.id in self.installed_runners
        return row.id in self.active_platforms

    def _header_func(self, row, before):
        if row.get_header():
            return
        if not before:
            row.set_header(SidebarHeader(_("Library")))
        elif before.type in ("category", "dynamic_category") and row.type == "service":
            row.set_header(SidebarHeader(_("Sources")))
        elif before.type == "service" and row.type == "runner":
            row.set_header(SidebarHeader(_("Runners")))
        elif before.type == "runner" and row.type == "platform":
            row.set_header(SidebarHeader(_("Platforms")))

    def update(self, *_args):
        self.installed_runners = [runner.name for runner in runners.get_installed()]
        self.active_platforms = games_db.get_used_platforms()
        self.invalidate_filter()
        return True

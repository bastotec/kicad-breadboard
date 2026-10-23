"""Real wx event tests; run with wxPython and a supported display (e.g. Xvfb)."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_inspector import example
from plugins.breadboard.model.inspector import EMPTY_DETAILS
from plugins.breadboard.model.session import save_session, load_session

HAS_WX = importlib.util.find_spec('wx') is not None
HAS_DISPLAY = sys.platform != 'linux' or bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))


@unittest.skipUnless(HAS_WX and HAS_DISPLAY, 'wxPython and a supported display are required')
class InspectorUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import wx
        cls.app = wx.App(False)

    def setUp(self):
        from plugins.breadboard.prefs import Preferences
        from plugins.breadboard.window import BreadboardWindow
        with patch('plugins.breadboard.window.load_prefs', return_value=Preferences()):
            self.win = BreadboardWindow()
        board, netlist = example()
        self.win.board = board
        self.win.netlist = netlist
        self.win.canvas.netlist = netlist
        self.win.canvas.reload_board(board)
        self.win.tray.board = board
        self.win.tray.load_netlist(netlist)
        self.app.Yield()

    def tearDown(self):
        self.win.Destroy()
        self.app.Yield()

    def click(self, x, y):
        import wx
        canvas = self.win.canvas
        # Route through wx's event dispatcher using actual canvas coordinates.
        for kind in (wx.wxEVT_LEFT_DOWN, wx.wxEVT_LEFT_UP):
            event = wx.MouseEvent(kind)
            event.SetPosition(wx.Point(round(x * canvas._zoom + canvas._pan_x),
                                       round(y * canvas._zoom + canvas._pan_y)))
            canvas.GetEventHandler().ProcessEvent(event)
        self.app.Yield()

    def test_session_switch_loads_associated_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            net_path = Path(directory) / 'second.net'
            net_path.write_text('''(export (version "E")
                (components (comp (ref "R1") (value "100k")
                    (libsource (lib "Device") (part "R_Small")
                        (description "Second resistor"))))
                (nets (net (code "1") (name "SECOND_SIGNAL")
                    (node (ref "R1") (pin "1")))))''', encoding='utf-8')
            session_path = Path(directory) / 'second.kicad_bbrd'
            save_session(example()[0], str(net_path), str(session_path))
            self.win._project_path = str(Path(directory) / 'previous')
            self.win._on_load(path=str(session_path))
            with patch.object(self.win, '_export_netlist') as export, \
                    patch('plugins.breadboard.window.wx.MessageBox'):
                self.win._on_update(None)
            export.assert_not_called()
            self.assertIsNone(self.win._project_path)
            self.app.Yield()
            self.click(*self.win.canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1)))
            text = self.win._component_details.GetValue()
            self.assertIn('Value: 100k', text)
            self.assertIn('Symbol: R_Small', text)
            self.assertIn('net: SECOND_SIGNAL', text)
            self.assertNotIn('Value: 10k', text)
            self.assertIs(self.win.canvas.netlist, self.win.netlist)
            self.assertIs(self.win.tray.netlist, self.win.netlist)
            self.assertEqual(self.win._netlist_path, str(net_path))

    def test_session_without_available_netlist_clears_old_metadata(self):
        import wx
        with tempfile.TemporaryDirectory() as directory:
            missing = str(Path(directory) / 'missing.net')
            invalid = Path(directory) / 'invalid.net'
            invalid.write_bytes(b'\xff')
            for netlist_path in (None, missing, str(invalid)):
                with self.subTest(netlist_path=netlist_path):
                    board, netlist = example()
                    self.win.netlist = netlist
                    self.win.canvas.netlist = netlist
                    self.win.tray.load_netlist(netlist)
                    self.win._refresh_terminal_choices()
                    self.win._refresh_probe_choices()
                    self.win._netlist_path = 'previous.net'
                    self.win._project_path = str(Path(directory) / 'previous')
                    session_path = Path(directory) / 'second.kicad_bbrd'
                    save_session(board, netlist_path, str(session_path))
                    with patch.object(self.win, '_export_netlist') as export, \
                            patch('plugins.breadboard.window.wx.MessageBox'):
                        self.win._on_load(path=str(session_path))
                        self.win._on_update(None)
                    export.assert_not_called()
                    self.assertIsNone(self.win._project_path)
                    self.app.Yield()
                    self.click(*self.win.canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1)))
                    text = self.win._component_details.GetValue()
                    self.assertIn('Value: Unknown', text)
                    self.assertIn('No matching schematic metadata', text)
                    self.assertNotIn('net: SIGNAL', text)
                    self.assertIsNone(self.win.netlist)
                    self.assertIsNone(self.win.canvas.netlist)
                    self.assertIsNone(self.win._netlist_path)
                    self.assertEqual(self.win.tray.netlist.components, {})
                    for choice in (*self.win._term_choices.values(),
                                   *self.win._probe_choices.values()):
                        self.assertEqual(choice.GetItems(), ['(unassigned)'])
                    saved_path = Path(directory) / 'resaved.kicad_bbrd'
                    with patch('plugins.breadboard.window.wx.FileDialog') as dialog:
                        instance = dialog.return_value.__enter__.return_value
                        instance.ShowModal.return_value = wx.ID_OK
                        instance.GetPath.return_value = str(saved_path)
                        self.win._on_save(None)
                    self.assertIsNone(load_session(str(saved_path))['netlist_path'])

    def test_session_preserves_electrical_assignments(self):
        from plugins.breadboard.model.breadboard import TieHole
        with tempfile.TemporaryDirectory() as directory:
            net_path = Path(directory) / 'ground.net'
            net_path.write_text('''(export (version "E")
                (components (comp (ref "R1") (value "10k")
                    (libsource (lib "Device") (part "R"))))
                (nets (net (code "1") (name "0")
                    (node (ref "R1") (pin "1")))))''', encoding='utf-8')
            session_path = Path(directory) / 'ground.kicad_bbrd'
            resaved_path = Path(directory) / 'resaved.kicad_bbrd'
            for warm in (False, True):
                for assignment in ('', 'CHASSIS'):
                    with self.subTest(warm=warm, assignment=assignment):
                        board, netlist = example()
                        board.assign_terminal('GND', assignment)
                        board.assign_terminal('V1', 'SUPPLY')
                        for name in ('FG_GND', 'SCOPE_GND'):
                            board.assign_probe_net(name, assignment)
                            board.place_probe(name, TieHole(10, 'a'))
                        board.add_wire(TieHole(10, 'b'), TieHole(20, 'b'))
                        save_session(board, str(net_path), str(session_path))
                        self.win.netlist = netlist if warm else None
                        self.win.canvas.netlist = self.win.netlist
                        self.win.tray.load_netlist(netlist if warm else type(netlist)({}, []))
                        self.win._on_load(path=str(session_path))
                        self.app.Yield()
                        self.assertIsNotNone(self.win.netlist.net_by_name('0'))
                        self.assertEqual(self.win.board.get_terminal_net('GND'),
                                         board.get_terminal_net('GND'))
                        for name in ('FG_GND', 'SCOPE_GND'):
                            self.assertEqual(self.win.board.get_probe_net(name), assignment)
                        save_session(self.win.board, self.win._netlist_path, str(resaved_path))
                        self.assertEqual(resaved_path.read_bytes(), session_path.read_bytes())
            self.win._load_netlist(str(net_path))
            self.assertEqual(self.win.board.get_terminal_net('GND'), '0')
            for name in ('FG_GND', 'SCOPE_GND'):
                self.assertEqual(self.win.board.get_probe_net(name), '0')

    def test_schematic_update_clears_removed_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            net_path = Path(directory) / 'updated.net'
            for replacement in ('', '''(comp (ref "R1") (value "100k")
                    (libsource (lib "Device") (part "Potentiometer")))'''):
                with self.subTest(replacement=replacement):
                    board, netlist = example()
                    self.win.board = board
                    self.win.netlist = netlist
                    self.win.canvas.netlist = netlist
                    self.win.canvas.reload_board(board)
                    self.win.tray.board = board
                    self.win.tray.load_netlist(netlist)
                    self.win._project_path = directory
                    net_path.write_text(f'''(export (version "E")
                        (components {replacement}
                            (comp (ref "U1") (value "RC4558")
                                (libsource (lib "Amplifier_Operational") (part "RC4558"))))
                        (nets))''', encoding='utf-8')
                    self.app.Yield()
                    self.click(*self.win.canvas.layout.hole_xy(board.hole_for_pin('R1', 1)))
                    self.assertIn('Reference: R1', self.win._component_details.GetValue())
                    with patch.object(self.win, '_export_netlist', return_value=net_path):
                        self.win._on_update(None)
                        self.assertNotIn('R1', board.placements)
                        self.assertIsNone(self.win.canvas.selected_ref)
                        self.assertEqual(self.win._component_details.GetValue(), EMPTY_DETAILS)
                        self.click(*self.win.canvas.layout.hole_xy(board.hole_for_pin('U1', 1)))
                        self.win._on_update(None)
                    self.assertEqual(self.win.canvas.selected_ref, 'U1')
                    self.assertIn('Value: RC4558', self.win._component_details.GetValue())

    def test_click_switch_empty_clear_delete_and_reload(self):
        canvas = self.win.canvas
        details = self.win._component_details
        self.assertFalse(details.IsEditable())
        first = canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1))
        second = canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 2))
        self.click((first[0] + second[0]) / 2, (first[1] + second[1]) / 2)
        self.assertIn('Reference: R1', details.GetValue())
        self.click(-100, -100)
        # Pin click also selects a component, independently of body hit testing.
        self.click(*canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1)))
        self.assertIn('Reference: R1', details.GetValue())
        self.click(*canvas.layout.hole_xy(self.win.board.hole_for_pin('U1', 1)))
        self.assertIn('Reference: U1', details.GetValue())
        self.click(-100, -100)
        self.assertEqual(details.GetValue(), EMPTY_DETAILS)
        self.click(*canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1)))
        canvas.set_mode('wire')
        self.assertEqual(details.GetValue(), EMPTY_DETAILS)
        canvas.set_mode('select')
        self.click(*canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1)))
        canvas.delete_selection()
        self.assertEqual(details.GetValue(), EMPTY_DETAILS)
        canvas.undo()
        self.assertEqual(details.GetValue(), EMPTY_DETAILS)
        self.click(*canvas.layout.hole_xy(self.win.board.hole_for_pin('R1', 1)))
        self.win.netlist.components['R1'].value = '22k'
        self.win._on_canvas_placed('R1')
        self.assertIn('Value: 22k', details.GetValue())
        canvas.reload_board(example()[0])
        self.assertEqual(details.GetValue(), EMPTY_DETAILS)

"""Real wx event tests; run with wxPython and a supported display (e.g. Xvfb)."""
import importlib.util
import os
import sys
import unittest
from unittest.mock import patch

from test_inspector import example
from plugins.breadboard.model.inspector import EMPTY_DETAILS

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

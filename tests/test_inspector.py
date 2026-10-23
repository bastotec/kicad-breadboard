"""Synthetic component metadata and session compatibility regression tests."""
import json
from pathlib import Path
import tempfile
import unittest

from plugins.breadboard.model.breadboard import Breadboard, PlacedComponent, TieHole
from plugins.breadboard.model.netlist import Netlist, NetlistComponent, Net, NetlistPin
from plugins.breadboard.model.inspector import component_details, EMPTY_DETAILS
from plugins.breadboard.model.session import save_session, load_session


def example():
    board = Breadboard()
    board.place(PlacedComponent('R1', 'R', {1: TieHole(10, 'e'), 2: TieHole(15, 'e')}))
    board.place(PlacedComponent('U1', 'RC4558', {1: TieHole(20, 'f')}))
    netlist = Netlist({
        'R1': NetlistComponent('R1', '10k', 'R', 'Device', 'Resistor'),
        'U1': NetlistComponent('U1', 'LM358', 'LM358', 'Amplifier_Operational'),
    }, [Net(1, 'SIGNAL', [NetlistPin('R1', 1), NetlistPin('U1', 1)])])
    return board, netlist


class InspectorTests(unittest.TestCase):
    def test_selection_switch_clear_and_missing_placement(self):
        board, netlist = example()
        self.assertIn('Reference: R1', component_details(board, netlist, 'R1'))
        self.assertIn('Reference: U1', component_details(board, netlist, 'U1'))
        self.assertEqual(component_details(board, netlist, None), EMPTY_DETAILS)
        board.remove('U1')
        self.assertEqual(component_details(board, netlist, 'U1'), EMPTY_DETAILS)

    def test_identity_is_separate_from_renderer(self):
        board, netlist = example()
        text = component_details(board, netlist, 'U1')
        self.assertIn('Value: LM358', text)
        self.assertIn('Renderer template: RC4558 (dual op-amp) (RC4558)', text)
        self.assertIn('not verified part identity or package', text)
        self.assertIn('Description: Unknown', text)
        self.assertNotIn('http', text)

    def test_known_metadata_update_and_unknowns(self):
        board, netlist = example()
        text = component_details(board, netlist, 'R1')
        self.assertIn('Pin 1: e10 — net: SIGNAL', text)
        self.assertIn('Pin 2: e15 — net: Unknown', text)
        netlist.components['R1'].value = '22k'
        board.get_placement('R1').pin_holes[1] = TieHole(12, 'e')
        self.assertIn('Value: 22k', component_details(board, netlist, 'R1'))
        self.assertIn('Pin 1: e12', component_details(board, netlist, 'R1'))
        self.assertIn('Value: Unknown', component_details(board, None, 'R1'))
        self.assertIn('No matching schematic metadata', component_details(board, None, 'R1'))
        board.get_placement('R1').type_id = 'unrecognized'
        self.assertIn('Renderer template: Unknown (unrecognized)',
                      component_details(board, netlist, 'R1'))

    def test_inspection_preserves_session_bytes_and_connectivity(self):
        board, netlist = example()
        board.add_wire(TieHole(10, 'a'), TieHole(20, 'a'))
        holes = [TieHole(10, 'e'), TieHole(20, 'e'), TieHole(15, 'e')]

        def connections(b):
            uf = b.build_connectivity()
            return [uf.connected(a, z) for a in holes for z in holes]

        before = connections(board)
        self.assertTrue(board.build_connectivity().connected(holes[0], holes[1]))
        self.assertFalse(board.build_connectivity().connected(holes[0], holes[2]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'example.kicad_bbrd'
            save_session(board, None, str(path))
            original = path.read_bytes()
            for ref in ('R1', 'U1', None, 'missing'):
                component_details(board, netlist, ref)
            save_session(board, None, str(path))
            self.assertEqual(path.read_bytes(), original)
            restored = load_session(str(path))['board']
            self.assertEqual(connections(restored), before)
            self.assertEqual(connections(board), before)
            self.assertEqual(json.loads(original)['version'], 1)
            save_session(restored, None, str(path))
            self.assertEqual(path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()

"""Read-only presentation of existing component and placement metadata."""
from __future__ import annotations

from typing import Optional

from .breadboard import Breadboard
from .components import ALL_DEFS
from .netlist import Netlist


EMPTY_DETAILS = 'Select a placed component to see its known details.'


def component_details(board: Breadboard, netlist: Optional[Netlist],
                      ref: Optional[str]) -> str:
    """Describe a selection without guessing part identity or changing the model.

    Rendering definitions are heuristic layouts, not manufacturer part data.
    Schematic nets below describe intent, not validated breadboard connectivity.
    """
    placed = board.get_placement(ref) if ref else None
    if placed is None:
        return EMPTY_DETAILS

    comp = netlist.components.get(ref) if netlist else None
    unknown = 'Unknown'
    lines = [f'Reference: {ref}']
    for label, attribute in [('Value', 'value'), ('Symbol', 'symbol'),
                             ('Library', 'lib'), ('Description', 'description')]:
        lines.append(f'{label}: {getattr(comp, attribute, "") or unknown}')
    if comp is None:
        lines.append('No matching schematic metadata is loaded.')

    template = ALL_DEFS.get(placed.type_id)
    template_name = template.display_name if template else unknown
    lines.extend(['', f'Renderer template: {template_name} ({placed.type_id})',
                  'Template only; not verified part identity or package.', '',
                  'Placed pins / schematic nets:'])
    nets = netlist.nets_for_ref(ref) if netlist else {}
    for pin, hole in sorted(placed.pin_holes.items()):
        net = nets.get(pin)
        net_name = net.name if net and net.name else unknown
        lines.append(f'Pin {pin}: {hole!r} — net: {net_name}')
    if not placed.pin_holes:
        lines.append('Unknown')
    return '\n'.join(lines)

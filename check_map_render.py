"""Offline render regression: require all state shapes and finite map legends."""
from pathlib import Path
import xml.etree.ElementTree as ET

import vl_convert as vl

from fec_explorer.origins import STATES, choropleth

values = STATES.copy()
values['records'] = range(1, 52)
values['recorded_amount'] = values.records * 100.25

for label, measure, amounts in [
    ('amount', 'Reported amount', values.recorded_amount),
    ('count', 'Record count', values.recorded_amount),
    ('signed', 'Reported amount', values.recorded_amount - 2000),
    ('zero', 'Reported amount', values.recorded_amount * 0),
]:
    frame = values.assign(recorded_amount=amounts)
    spec = choropleth(frame, measure).to_dict()
    svg = vl.vegalite_to_svg(spec)
    assert 'NaN' not in svg, f'{label}: invalid numeric output'
    tree = ET.fromstring(svg)
    shapes = [e for e in tree.iter() if e.tag.endswith('path') and 'State:' in e.get('aria-label', '')]
    assert len(shapes) == 51, f'{label}: expected 51 state/DC shapes, got {len(shapes)}'
    assert all(e.get('d') for e in shapes), f'{label}: empty state geometry'
    assert len({e.get('fill') for e in shapes}) > 1 or label == 'zero', f'{label}: missing color variation'

print('PASS: SVG rendering contains 51 state/DC geometries, valid colors, and no NaN for amount, count, signed, and zero measures.')

# A dominant Maryland value must not affect the remaining states' color domain.
frame = values.copy()
frame.loc[frame.state == 'MD', 'recorded_amount'] = 1e12
svg = vl.vegalite_to_svg(choropleth(frame, 'Reported amount', exclude_state='MD').to_dict())
tree = ET.fromstring(svg)
shapes = [e for e in tree.iter() if e.tag.endswith('path') and 'State:' in e.get('aria-label', '')]
md = next(e for e in shapes if 'State: Maryland' in e.get('aria-label', ''))
assert md.get('fill') == '#d1d5db'
assert 'Excluded from color scale and map shares' in md.get('aria-label', '')
assert all('Included in color scale' in e.get('aria-label', '') for e in shapes if e is not md)
assert len(shapes) == 51 and 'NaN' not in svg
assert len({e.get('fill') for e in shapes if e is not md}) > 1
print('PASS: Maryland outlier is gray while remaining states retain color variation.')

frame.loc[frame.state == 'CA', 'recorded_amount'] = 2e12
svg = vl.vegalite_to_svg(choropleth(frame, 'Reported amount', exclude_state='CA').to_dict())
shapes = [e for e in ET.fromstring(svg).iter() if e.tag.endswith('path') and 'State:' in e.get('aria-label', '')]
assert len(shapes) == 51 and 'NaN' not in svg
assert next(e for e in shapes if 'State: California' in e.get('aria-label', '')).get('fill') == '#d1d5db'
assert next(e for e in shapes if 'State: Maryland' in e.get('aria-label', '')).get('fill') != '#d1d5db'
print('PASS: excluded state can change without continuing to exclude Maryland.')

import xml.etree.ElementTree as ET

import pytest
import vl_convert as vl
from origins import STATES,choropleth

pytestmark=pytest.mark.rendering


@pytest.mark.parametrize('measure,mode,excluded',[
    ('Reported amount','positive',None),('Record count','positive',None),
    ('Reported amount','signed',None),('Reported amount','zero',None),
    ('Reported amount','positive','MD'),('Record count','positive','CA'),
])
def test_map_renders_states_and_finite_legends(measure,mode,excluded):
    frame=STATES.copy()
    frame['records']=range(1,52)
    frame['recorded_amount']=frame.records*100.25
    if mode=='signed':frame.recorded_amount-=2000
    if mode=='zero':frame.recorded_amount=0.0
    if excluded:frame.loc[frame.state==excluded,'recorded_amount']=1e12
    svg=vl.vegalite_to_svg(choropleth(frame,measure,exclude_state=excluded).to_dict())
    assert 'NaN' not in svg
    shapes=[e for e in ET.fromstring(svg).iter() if e.tag.endswith('path') and 'State:' in e.get('aria-label','')]
    assert len(shapes)==51 and all(e.get('d') for e in shapes)
    if mode!='zero':assert len({e.get('fill') for e in shapes})>1
    if excluded:
        name=STATES.loc[STATES.state==excluded,'state_name'].iloc[0]
        shape=next(e for e in shapes if f'State: {name};' in e.get('aria-label',''))
        assert shape.get('fill')=='#d1d5db'
        assert 'Excluded from color scale and map shares' in shape.get('aria-label','')

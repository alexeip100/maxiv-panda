import struct
import numpy as np
import pytest
from maxiv_panda.map_exchange import MapData, write_ibw_map
from maxiv_panda.ibw_parser import _extract_point_axis_from_note, _detect_dim2_label_from_note

@pytest.mark.parametrize('secondary', [np.array([484.,484.3,485.8]), np.array([485.8,484.3,484.])])
def test_igor_v5_header_and_measured_axes(tmp_path, secondary):
    x=np.array([455.,454.5,454.,453.5]); z=np.arange(12,dtype=float).reshape(3,4)-5.7
    path=tmp_path/'map.ibw'
    write_ibw_map(path, MapData(x,secondary,z,'Kinetic Energy [eV]','Photon Energy [eV]',{'title':'Test map','normalization':'at_ke'}))
    raw=path.read_bytes()
    assert struct.unpack_from('<h',raw,0)[0] == 5
    assert sum(struct.unpack('<192h',raw[:384])) % 65536 == 0
    assert struct.unpack_from('<i',raw,4)[0] == 320 + z.nbytes
    assert struct.unpack_from('<i',raw,76)[0] == z.size  # v5 npnts
    assert struct.unpack_from('<h',raw,80)[0] == 4 # double precision
    assert struct.unpack_from('<2i',raw,132) == (len(x),len(secondary))
    # Igor: x dimension fastest, Fortran-ordered array shape (x, secondary).
    np.testing.assert_array_equal(np.frombuffer(raw[384:384+z.nbytes],dtype='<f8').reshape((len(x),len(secondary)),order='F').T,z)
    note=raw[384+z.nbytes:].decode('utf-8')
    np.testing.assert_allclose(_extract_point_axis_from_note(note,len(secondary)),secondary)
    assert _detect_dim2_label_from_note({'Dimension 2 name':'Photon Energy [eV]'},note)=='Photon Energy [eV]'
    assert 'normalization' in note

def test_reject_nonuniform_electron_axis(tmp_path):
    with pytest.raises(ValueError,match='regularly spaced'):
        write_ibw_map(tmp_path/'bad.ibw',MapData([1,2,4],[20,21],np.ones((2,3))))

def test_iteration_axis_note_units(tmp_path):
    path=tmp_path/'iter.ibw'
    write_ibw_map(path,MapData([1.,2.,3.],[1,2.5,4.],np.ones((3,3)),secondary_label='Region Iteration [a.u.]'))
    note=path.read_bytes()[384+9*8:].decode('utf-8')
    assert 'Point 2=2.5 a.u.' in note
    assert _extract_point_axis_from_note(note,3)==[1,2.5,4]

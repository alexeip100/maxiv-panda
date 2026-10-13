import numpy as np
import pytest
from maxiv_panda.map_exchange import MapData, write_ascii_map, read_ascii_map
from maxiv_panda.txt_parser import parse_structured_txt

@pytest.mark.parametrize('photon_axis', [[485., 485.3, 486.7], [486.7, 485.3, 485.]])
def test_matrix_and_txt_import(tmp_path, photon_axis):
    x=np.array([450., 449.5, 449.]); y=np.array(photon_axis)
    z=np.arange(9,dtype=float).reshape(3,3)-4
    data=MapData(x,y,z,'Kinetic Energy [eV]','Photon Energy [eV]',{'title':'ResAuger map','normalization':'none','subtraction':'reference'})
    path=tmp_path/'map.txt'
    write_ascii_map(path,data)
    recovered=read_ascii_map(path)
    np.testing.assert_array_equal(recovered.electron_energy,x)
    np.testing.assert_array_equal(recovered.secondary_energy,y)
    np.testing.assert_array_equal(recovered.intensity,z)
    assert recovered.metadata==data.metadata
    parsed=parse_structured_txt(path)
    region=parsed.regions[0]
    assert region.dim2_name()=='Photon Energy [eV]'
    np.testing.assert_array_equal(region.data[:,1:],z.T)


def test_bad_axis_rejected(tmp_path):
    with pytest.raises(ValueError):
        write_ascii_map(tmp_path/'bad.txt',MapData([1,1],[2,3],[[1,2],[3,4]]))

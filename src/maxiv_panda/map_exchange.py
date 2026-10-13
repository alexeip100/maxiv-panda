"""Portable, versioned ASCII exchange for the *measured-grid* 2D map.

The first numeric row contains electron-energy positions; the first column of
subsequent rows contains the secondary-axis positions. Nothing is interpolated.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path

import numpy as np

MAGIC = "# PANDA_MAP_ASCII_V1"


@dataclass
class MapData:
    electron_energy: np.ndarray
    secondary_energy: np.ndarray
    intensity: np.ndarray
    electron_label: str = "Binding Energy [eV]"
    secondary_label: str = "Iteration"
    metadata: dict = field(default_factory=dict)

    def validate(self) -> None:
        x = np.asarray(self.electron_energy, dtype=float)
        y = np.asarray(self.secondary_energy, dtype=float)
        z = np.asarray(self.intensity, dtype=float)
        if x.ndim != 1 or y.ndim != 1 or z.shape != (len(y), len(x)):
            raise ValueError("Map dimensions do not match the two energy axes")
        if len(x) < 2 or len(y) < 2 or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError("Map axes must contain at least two finite coordinates")
        if not np.isfinite(z).all():
            raise ValueError("Cannot export a map containing non-finite intensities")
        if np.any(np.diff(x) == 0) or np.any(np.diff(y) == 0):
            raise ValueError("Map axes must not contain repeated coordinates")


def write_ascii_map(path: str | Path, data: MapData) -> None:
    data.validate()
    path = Path(path)
    meta = dict(data.metadata)
    meta["electron_label"] = data.electron_label
    meta["secondary_label"] = data.secondary_label
    header = json.dumps(meta, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    x = np.asarray(data.electron_energy, dtype=float)
    y = np.asarray(data.secondary_energy, dtype=float)
    z = np.asarray(data.intensity, dtype=float)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(MAGIC + "\n")
        stream.write("# metadata=" + header + "\n")
        stream.write("# First row: electron axis; first column: secondary axis\n")
        stream.write("nan " + " ".join(format(v, ".17g") for v in x) + "\n")
        for yy, row in zip(y, z):
            stream.write(format(yy, ".17g") + " " + " ".join(format(v, ".17g") for v in row) + "\n")


def read_ascii_map(path: str | Path) -> MapData:
    path = Path(path)
    with path.open("r", encoding="utf-8-sig") as stream:
        magic = stream.readline().rstrip("\r\n")
        if magic != MAGIC:
            raise ValueError("Not a PANDA ASCII 2D map (unsupported header)")
        line = stream.readline().rstrip("\r\n")
        if not line.startswith("# metadata="):
            raise ValueError("Missing map metadata")
        metadata = json.loads(line.split("=", 1)[1])
    numeric = np.loadtxt(path, comments="#", dtype=float, ndmin=2)
    if numeric.shape[0] < 3 or numeric.shape[1] < 3:
        raise ValueError("Map must contain at least two points on each axis")
    out = MapData(
        electron_energy=numeric[0, 1:],
        secondary_energy=numeric[1:, 0],
        intensity=numeric[1:, 1:],
        electron_label=str(metadata.pop("electron_label", "Binding Energy [eV]")),
        secondary_label=str(metadata.pop("secondary_label", "Iteration")),
        metadata=metadata,
    )
    out.validate()
    return out


# Binary Wave v5. The 2D Igor array is (electron points, secondary points)
# in Fortran order, matching PANDA's IBW reader and Igor's x/y dimension order.
def write_ibw_map(path: str | Path, data: MapData) -> None:
    """Write a real Igor Binary Wave v5, with both axes and processing note.

    The photon/iteration axis is additionally stored as explicit Point N note
    values, so irregular scans do not get silently reduced to an affine grid.
    The electron axis must be uniformly spaced because PANDA's existing IBW
    loader derives it from native Igor wave scaling.
    """
    import ctypes as ct
    import re
    import struct

    data.validate()
    x = np.asarray(data.electron_energy, dtype=float)
    y = np.asarray(data.secondary_energy, dtype=float)
    z = np.asarray(data.intensity, dtype='<f8')
    dx = float((x[-1] - x[0]) / (len(x) - 1))
    if not np.allclose(x, x[0] + dx*np.arange(len(x)), rtol=0, atol=max(1e-8, abs(dx)*1e-5)):
        raise ValueError('Igor IBW requires a regularly spaced electron-energy axis. Use ASCII matrix for this map.')

    class BinHeader5(ct.Structure):
        _pack_ = 2
        _fields_ = [('version',ct.c_int16),('checksum',ct.c_int16),
          ('wfmSize',ct.c_int32),('formulaSize',ct.c_int32),('noteSize',ct.c_int32),
          ('dataEUnitsSize',ct.c_int32),('dimEUnitsSize',ct.c_int32*4),
          ('dimLabelsSize',ct.c_int32*4),('sIndicesSize',ct.c_int32),
          ('optionsSize1',ct.c_int32),('optionsSize2',ct.c_int32)]

    class WaveHeader5(ct.Structure):
        _pack_ = 2
        _fields_ = [('next',ct.c_byte*4),('creationDate',ct.c_uint32),
          ('modDate',ct.c_uint32),('npnts',ct.c_int32),('type',ct.c_int16),
          ('dLock',ct.c_int16),('whpad1',ct.c_byte*6),('whVersion',ct.c_int16),
          ('bname',ct.c_char*32),('whpad2',ct.c_int32),('dFolder',ct.c_byte*4),
          ('nDim',ct.c_int32*4),('sfA',ct.c_double*4),('sfB',ct.c_double*4),
          ('dataUnits',ct.c_char*4),('dimUnits',(ct.c_char*4)*4),
          ('fsValid',ct.c_int16),('whpad3',ct.c_int16),
          ('botFullScale',ct.c_double),('topFullScale',ct.c_double),
          ('dataEUnits',ct.c_byte*4),('dimEUnits',(ct.c_byte*4)*4),
          ('dimLabels',(ct.c_byte*4)*4),('waveNoteH',ct.c_byte*4),
          ('platform',ct.c_char),('spare',ct.c_char),
          ('waveDimLabelEncoding',ct.c_byte),('textWaveContentEncoding',ct.c_byte),
          ('whUnused',ct.c_int32*13),('vRefNum',ct.c_int32),
          ('dirID',ct.c_int32),('private',ct.c_byte*28)]

    if ct.sizeof(BinHeader5) != 64 or ct.sizeof(WaveHeader5) != 320:
        raise RuntimeError('Unsupported Igor binary header packing')
    name = re.sub('[^A-Za-z0-9_]', '_', str(data.metadata.get('title','PANDA_Map')))
    if not name or not name[0].isalpha(): name = 'PANDA_'+name
    name = name[:31]
    notes = [
       'Region Name='+str(data.metadata.get('title','PANDA processed map')).replace('\r',' ').replace('\n',' '),
       'Spectrum Name='+name,
       'Axis Label='+data.electron_label,
       'Energy Scale='+('Kinetic' if 'kinetic' in data.electron_label.lower() else 'Binding' if 'binding' in data.electron_label.lower() else 'Unknown'),
       'Dimension 2 name='+data.secondary_label,
       'PANDA_MAP_IBW_V1=1',
       'PANDA metadata='+json.dumps(data.metadata,ensure_ascii=True,allow_nan=False,separators=(',',':')),
    ]
    # Explicit point coordinates even for non-uniform scans.
    unit = 'eV' if ('energy' in data.secondary_label.lower() or 'phe' in data.secondary_label.lower()) else 'a.u.'
    notes += ['Point '+str(i+1)+'='+format(v,'.17g')+' '+unit for i,v in enumerate(y)]
    note = ('\r'.join(notes)+'\r').encode('utf-8')
    h, w = BinHeader5(), WaveHeader5()
    h.version = 5
    h.wfmSize = 320 + z.nbytes
    h.noteSize = len(note)
    w.npnts = z.size
    w.type = 4  # NT_FP64
    w.whVersion = 1
    w.bname = name.encode('ascii')
    w.nDim[0], w.nDim[1] = len(x), len(y)
    w.sfA[0], w.sfB[0] = dx, float(x[0])
    w.sfA[1], w.sfB[1] = float((y[-1]-y[0])/(len(y)-1)), float(y[0])
    w.dataUnits = b'a.u.'
    w.dimUnits[0].value = b'eV'
    if 'energy' in data.secondary_label.lower() or 'phe' in data.secondary_label.lower():
        w.dimUnits[1].value = b'eV'
    w.platform = b'2'
    raw_header = bytes(h)+bytes(w)
    # Checksum is a signed 16-bit sum over the 384-byte v5 headers.
    total = sum(struct.unpack('<192h',raw_header))
    h.checksum = (-total + 32768) % 65536 - 32768
    with Path(path).open('wb') as fp:
        fp.write(bytes(h)); fp.write(bytes(w))
        fp.write(np.asarray(z.T, dtype='<f8').tobytes(order='F'))
        fp.write(note)

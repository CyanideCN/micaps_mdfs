# cython: language_level=3
include "table.py"

from libc.string cimport memcpy

import struct
import datetime

def create_dict(dict _dict, index, int size):
    if index not in _dict.keys():
        _dict[index] = [None] * size

corr_dtype = {1:'x', 2:'h', 3:'i', 4:'q', 5:'f', 6:'d', 7:'s'}
corr_size = {1:1, 2:2, 3:4, 4:8, 5:4, 6:8, 7:1}

cdef inline short _ushort(bytes buf):
    return buf[0] + (buf[1] << 8)

cdef float _float(bytes buffer):
    cdef char* buf = buffer
    cdef float f
    memcpy(&f, buf, sizeof(f));
    return f

cdef int _int(bytes buffer):
    cdef char* buf = buffer
    cdef int i
    memcpy(&i, buf, sizeof(i));
    return i

cdef class MDFSFile(object):
    def __init__(self, file):
        if hasattr(file, 'read'):
            self._buf = file
        else:
            self._buf = open(file, 'rb')
        if self._buf.read(4).decode() != 'mdfs':
            raise ValueError('Not valid mdfs data')

class cStation(MDFSFile):
    def __init__(self, file, int read_break=-1):
        super().__init__(file)
        buf = self._buf
        cdef:
            short dtype, var_id, q_num, id_type
            int station_num, quantity_num, stid, var_dtype, idx, year, month, day, hour, min_, sec, tz, __
            dict x, data
            float stlon, stlat
            list id_list
            str _dtype
        dtype = _ushort(buf.read(2))
        self.data_dsc = buf.read(100).decode('gbk').replace('\x00', '')
        self.level = _float(buf.read(4))
        self.level_dsc = buf.read(50).decode('gbk').replace('\x00', '')
        year = _int(buf.read(4))
        month = _int(buf.read(4))
        day = _int(buf.read(4))
        hour = _int(buf.read(4))
        min_ = _int(buf.read(4))
        sec = _int(buf.read(4))
        tz = _int(buf.read(4))
        self.utc_time = datetime.datetime(year, month, day, hour, min_, sec) - datetime.timedelta(hours=tz)
        id_type = _ushort(buf.read(2))
        buf.seek(98, 1)#288
        # Data block 1
        station_num = _int(buf.read(4))
        # Data block 2
        quantity_num = _ushort(buf.read(2))
        x = dict([(_ushort(buf.read(2)), _ushort(buf.read(2))) for i in range(quantity_num)])
        # Data block 3
        data = {}
        for i in ['ID', 'Lon', 'Lat']:
            create_dict(data, i, station_num)
        for i in x.keys():
            if i % 2 != 0:
                create_dict(data, i, station_num)
        for idx in range(station_num):
            if id_type != 1:
                stid = _int(buf.read(4))
                stlon = _float(buf.read(4))
                stlat = _float(buf.read(4))
                data['ID'][idx] = stid
                data['Lon'][idx] = stlon
                data['Lat'][idx] = stlat
            else:
                id_length = _ushort(buf.read(2))
                data['ID'][idx] = buf.read(id_length).decode()
                stlon = _float(buf.read(4))
                stlat = _float(buf.read(4))
                data['Lon'][idx] = stlon
                data['Lat'][idx] = stlat
            q_num = _ushort(buf.read(2))
            id_list = list()
            # iterate over q_num
            for __ in range(q_num):
                var_id = _ushort(buf.read(2))
                if var_id % 2 == 0 and var_id >= 22:
                    # Quality control code
                    var_dtype = 1
                else:
                    var_dtype = id_dtype[var_id]
                    id_list.append(var_id)
                _dtype = corr_dtype[var_dtype]
                if _dtype == 'f':
                    var_value = _float(buf.read(4))
                elif _dtype == 'i':
                    var_value = _int(buf.read(4))
                else:
                    var_value = struct.unpack(_dtype, buf.read(corr_size[var_dtype]))
                if var_value and var_id % 2 != 0:
                    var_value = var_value[0] if not isinstance(var_value, float) else var_value
                    data[var_id][idx] = var_value
            if stid == read_break:
                break
        self.data = data
        buf.close()

    def to_dataframe(self):
        import pandas as pd
        df = pd.DataFrame(self.data)
        cols = df.columns
        cdef list new_cols = list()
        for col in cols:
            new_cols.append(id_name.get(col, col))
        df.columns = new_cols
        return df
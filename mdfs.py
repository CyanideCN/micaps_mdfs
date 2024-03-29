# -*- coding: utf-8 -*-
# Author: Puyuan Du

import struct
import datetime
import pickle
import warnings
import bz2
import gzip

import numpy as np
import xarray as xr

from table import id_dtype, id_name

def create_dict(_dict, index, size):
    if index not in _dict.keys():
        _dict[index] = [None] * size

corr_dtype = {1:'x', 2:'h', 3:'i', 4:'q', 5:'f', 6:'d', 7:'s'}
corr_size = {1:1, 2:2, 3:4, 4:8, 5:4, 6:8, 7:1}

def prepare_file(file):
    if hasattr(file, 'read'):
        return file
    f = open(file, 'rb')
    magic = f.read(3)
    f.close()
    if magic.startswith(b'\x1f\x8b'):
        return gzip.GzipFile(file, 'rb')
    if magic.startswith(b'BZh'):
        return bz2.BZ2File(file, 'rb')
    return open(file, 'rb')

class MDFSFile(object):
    def __init__(self, file):
        self._buf = prepare_file(file)
        if self._buf.read(4).decode() != 'mdfs':
            raise ValueError('Not valid mdfs data')

class Station(MDFSFile):
    def __init__(self, file):
        super().__init__(file)
        # Header
        dtype = struct.unpack('h', self._buf.read(2))[0]
        self.data_dsc = self._buf.read(100).decode('gbk').replace('\x00', '')
        self.level = struct.unpack('f', self._buf.read(4))[0]
        self.level_dsc = self._buf.read(50).decode('gbk').replace('\x00', '')
        year, month, day, hour, min_, sec, tz = struct.unpack('7i', self._buf.read(28))
        self.utc_time = datetime.datetime(year, month, day, hour, min_, sec) - datetime.timedelta(hours=tz)
        id_type = struct.unpack('h', self._buf.read(2))[0]
        self._buf.seek(98, 1)#288
        # Data block 1
        station_num = struct.unpack('i', self._buf.read(4))[0] #292
        # Data block 2
        quantity_num = struct.unpack('h', self._buf.read(2))[0] #294
        x = dict([(struct.unpack('h', self._buf.read(2))[0], struct.unpack('h', self._buf.read(2))[0])
                  for i in range(quantity_num)])
        # Data block 3
        data = {}
        for i in ['ID', 'Lon', 'Lat']:
            create_dict(data, i, station_num)
        for i in x.keys():
            if i % 2 != 0:
                create_dict(data, i, station_num)
        for idx in range(station_num):
            if id_type != 1:
                stid, stlon, stlat = struct.unpack('iff', self._buf.read(12))
                data['ID'][idx] = stid
                data['Lon'][idx] = stlon
                data['Lat'][idx] = stlat
            else:
                id_length = struct.unpack('h', self._buf.read(2))[0]
                data['ID'][idx] = self._buf.read(id_length).decode()
                stlon, stlat = struct.unpack('ff', self._buf.read(8))
                data['Lon'][idx] = stlon
                data['Lat'][idx] = stlat
            q_num = struct.unpack('h', self._buf.read(2))[0]
            id_list = list()
            # iterate over q_num
            for __ in range(q_num):
                var_id = struct.unpack('h', self._buf.read(2))[0]
                if var_id % 2 == 0 and var_id not in range(22):
                    # Quality control code
                    var_dtype = 1
                else:
                    var_dtype = id_dtype[var_id]
                    id_list.append(var_id)
                var_value = struct.unpack(corr_dtype[var_dtype], self._buf.read(corr_size[var_dtype]))
                if var_value and var_id % 2 != 0:
                    var_value = var_value[0]
                    data[var_id][idx] = var_value
        self.data = data
        self._buf.close()

    def repr_station(self, station):
        sta_arr = np.array(self.data['ID'])
        pos = np.nonzero(sta_arr == station)[0]
        reprs = list()
        if pos.size != 0:
            var = self.data.keys()
            for v in var:
                if isinstance(v, int) and v not in range(22) and v % 2 != 0:
                    # Variables that are not geographic information
                    vname = id_name[v]
                    _v = self.data[v][pos[0]]
                    reprs.append('{}: {:.1f}'.format(vname, _v))
        else:
            warnings.warn('Station {} not found'.format(station), RuntimeWarning)
        return '\n'.join(reprs)

class Grid(MDFSFile):
    def __init__(self, file):
        super().__init__(file)
        self.datatype = struct.unpack('h', self._buf.read(2))[0]
        self.model_name = self._buf.read(20).decode('gbk').replace('\x00', '')
        self.element = self._buf.read(50).decode('gbk').replace('\x00', '')
        self.data_dsc = self._buf.read(30).decode('gbk').replace('\x00', '')
        self.level = struct.unpack('f', self._buf.read(4))[0]
        year, month, day, hour, tz = struct.unpack('5i', self._buf.read(20))
        self.utc_time = datetime.datetime(year, month, day, hour) - datetime.timedelta(hours=tz)
        self.period = struct.unpack('i', self._buf.read(4))[0]
        start_lon, end_lon, lon_spacing, lon_number = struct.unpack('3fi', self._buf.read(16))
        start_lat, end_lat, lat_spacing, lat_number = struct.unpack('3fi', self._buf.read(16))
        lon_array = np.arange(start_lon, end_lon + lon_spacing, lon_spacing)
        lat_array = np.arange(start_lat, end_lat + lat_spacing, lat_spacing)
        isoline_start_value, isoline_end_value, isoline_space = struct.unpack('3f', self._buf.read(12))
        self._buf.seek(100, 1)
        block_num = lat_number * lon_number
        data = {}
        data['Lon'] = lon_array
        data['Lat'] = lat_array
        if self.datatype == 4:
            # Grid form
            grid = struct.unpack('{}f'.format(block_num), self._buf.read(block_num * 4))
            grid_array = np.array(grid).reshape(lat_number, lon_number)
            data['Grid'] = grid_array
        elif self.datatype == 11:
            # Vector form
            norm = struct.unpack('{}f'.format(block_num), self._buf.read(block_num * 4))
            angle = struct.unpack('{}f'.format(block_num), self._buf.read(block_num * 4))
            norm_array = np.array(norm).reshape(lat_number, lon_number)
            angle_array = np.array(angle).reshape(lat_number, lon_number)
            # Convert stupid self-defined angle into correct direction angle
            corr_angle_array = 270 - angle_array
            corr_angle_array[corr_angle_array < 0] += 360
            data['Norm'] = norm_array
            data['Direction'] = corr_angle_array
        self.data = data
        self.time = self.utc_time + datetime.timedelta(hours=self.period)
        self._buf.close()

    def to_xarray(self):
        # TODO: Add 'z' dimension
        return xr.DataArray(self.data['Grid'], coords={'longitude':self.data['Lon'], 'latitude':self.data['Lat'], 'time':self.time},
                            dims=['latitude', 'longitude'],
                            attrs={'units':self.data_dsc, 'levels':self.level, 'name':self.element,
                                   'model_name':self.model_name, 'time_bounds':self.period, 'initial_time':self.utc_time},
                            name='{}_{:.0f}'.format(self.element, self.level))

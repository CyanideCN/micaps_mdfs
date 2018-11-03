# -*- coding: utf-8 -*-
# Author: Puyuan Du

import struct
import datetime
import pickle

def create_dict(_dict, index):
    if index not in _dict.keys():
        _dict[index] = list()

corr_dtype = {1:'x', 2:'h', 3:'i', 4:'l', 5:'f', 6:'d', 7:'s'}
corr_size = {1:1, 2:2, 3:4, 4:4, 5:4, 6:8, 7:1}
buf = open(r'data_table.pickle', 'rb')
var_table = pickle.load(buf)
buf.close()

class MDFS_Station:
    def __init__(self, filepath):
        f = open(filepath, 'rb')
        if f.read(4).decode() != 'mdfs':
            raise ValueError('Not valid mdfs data')
        # Header
        dtype = struct.unpack('h', f.read(2))[0]
        self.data_dsc = f.read(100).decode('gbk').replace('\x00', '')
        self.level = struct.unpack('f', f.read(4))[0]
        self.level_dsc = f.read(50).decode('gbk').replace('\x00', '')
        year, month, day, hour, min, sec, tz = struct.unpack('7i', f.read(28))
        self.utc_time = datetime.datetime(year, month, day, hour, min, sec) - datetime.timedelta(hours=tz)
        f.seek(100, 1)#288
        # Data block 1
        station_num = struct.unpack('i', f.read(4))[0] #292
        # Data block 2
        quantity_num = struct.unpack('h', f.read(2))[0] #294
        x = dict([(struct.unpack('h', f.read(2))[0], struct.unpack('h', f.read(2))[0]) for i in range(quantity_num)])
        # Data block 3
        data = {}
        for i in ['ID', 'Lon', 'Lat']:
            create_dict(data, i)
        for _ in range(station_num):
            stid, stlon, stlat = struct.unpack('iff', f.read(12))
            data['ID'].append(stid)
            data['Lon'].append(stlon)
            data['Lat'].append(stlat)
            q_num = struct.unpack('h', f.read(2))[0]
            # iterate over q_num
            for __ in range(q_num):
                var_id = struct.unpack('h', f.read(2))[0]
                if var_id % 2 == 0 and var_id not in range(22):
                    var_info = 1
                else:
                    var_info = var_table[var_id]
                var_value = struct.unpack(corr_dtype[var_info], f.read(corr_size[var_info]))
                if var_value:
                    create_dict(data, var_id)
                    var_value = var_value[0]
                    data[var_id].append(var_value)
        self.data = data
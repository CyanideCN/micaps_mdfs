# Micaps_MDFS

一个解码MICAPS4分布式数据环境中的数据文件(MDFS)的小程序，支持站点数据和网格数据的解码。

## 使用方法

站点数据：

```python
from mdfs import Station
import matplotlib.pyplot as plt
import matplotlib.colors as ccolor
import matplotlib.cm as cmx
import cartopy.crs as ccrs
import cartopy.feature as cfeature

x = Station(r'D:\20181028160000.000')
lon = x.data['Lon'] # 经度
lat = x.data['Lat'] # 纬度
var = x.data[603] # 气象要素

cm = plt.get_cmap('jet')
cNorm = ccolor.Normalize(vmin=min(var), vmax=max(var))
scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=cm)
c = scalarMap.to_rgba(var)
ax = plt.axes(projection=ccrs.PlateCarree())
ax.scatter(lon, lat, s=5, c=c)
ax.coastlines(resolution='10m')
ax.add_feature(cfeature.BORDERS)
plt.show()
```
`Station`类含有的属性：
`data_dsc`：描述信息
`level`：数据层面
`level_dsc`：层面描述信息
`utc_time`：数据时间（世界时），为`datetime.datetime`类型
`data`：主体数据，为dict类型，含有的键值有`ID`（站号），`Lon`（经度），`Lat`（纬度）以及数据里对应的物理量数据的编号（见`dtype_link.xml`）

由于站点类型数据是变长字节存储，纯Python实现的版本效率较低。`station.pyx`是cython实现的效率更高的版本，里面的`cStation`类是等效于`mdfs.py`里的`Station`类的，并且`cStation`类实现了`to_dataframe`方法，操作更为方便。

编译`station.pyx`
```bash
python compile.py build_ext --inplace
```

网格数据：

```python
from mdfs import Grid
import numpy as np
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import metpy.calc as mpcalc
from metpy.units import units
filepath = r'D:\18110408.000'
f = Grid(filepath)
lon = f.data['Lon'] # 经度
lat = f.data['Lat'] # 纬度 PS:均为一维数组，使用前需np.meshgrid
norm = f.data['Norm'] # 向量数据中的模长
dir = f.data['Direction'] # 向量数据中的角度
u, v = mpcalc.wind_components(norm * units('m/s'), dir * units.degree)
ax = plt.axes(projection=ccrs.PlateCarree())
ax.streamplot(lon, lat, u, v, density=3)
ax.coastlines(resolution='10m')
ax.add_feature(cfeature.BORDERS)
plt.show()
```

`Grid`类含有的属性：
`datatype`：文件类别
`model_name`：模式名称
`element`：物理量名称
`data_dsc`：描述信息
`level`：数据层面
`utc_time`：数据时间（世界时），为`datetime.datetime`类型
`data`：主体数据，为dict类型，具体见例子中的注释
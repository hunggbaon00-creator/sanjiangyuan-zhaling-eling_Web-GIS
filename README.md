# 基于 GEE 与 WebGIS 的三江源植被水体可视化原型

本项目存放 SRT 申报书对应的 WebGIS 原型开发程序。申报书文件保留在原 `本院SRT` 文件夹中。

## 目录结构

```text
app/                  Streamlit WebGIS 页面
data/raw/             原始数据或边界文件
data/processed/       GEE 导出的 CSV、GeoJSON、图层文件
scripts/gee/          Google Earth Engine Python 脚本
scripts/powershell/   Windows 运行脚本
environment/          依赖清单
.venv/                本地 Python 虚拟环境
```

## 启动 WebGIS 页面

```powershell (cd )
.\.venv\Scripts\python.exe -m streamlit run app\streamlit_app.py --server.port 8501
```

浏览器打开：

```text
http://127.0.0.1:8501
```

## GEE 授权

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\run_gee_auth.ps1
```

授权完成后检查：

```powershell
.\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py
```

## 导出年度统计

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\powershell\run_gee_export_stats.ps1
```

导出任务完成后，从 Google Drive 下载 CSV，并保存为：

```text
data\processed\zhaling_eling_yearly_stats.csv
```

Streamlit 页面会自动读取真实数据。

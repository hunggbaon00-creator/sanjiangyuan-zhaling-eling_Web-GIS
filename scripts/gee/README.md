# GEE 本地 Python 工作流

本目录用于第二种路线：在本地 Python 环境中调用 Google Earth Engine API。

## 1. 完成授权

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m ee.cli.eecli authenticate --auth_mode=localhost:0
```

浏览器会打开 Google 授权页面。请使用已经开通 Earth Engine 的 Google 账号登录，并按页面提示授权。

授权完成后检查：

```powershell
.\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py
```

如果提示需要 Google Cloud project，使用：

```powershell
.\.venv\Scripts\python.exe scripts\gee\gee_auth_check.py --project YOUR_GCP_PROJECT_ID
```

## 2. 导出扎陵湖-鄂陵湖年度统计

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py
```

如果需要指定 Cloud project：

```powershell
.\.venv\Scripts\python.exe scripts\gee\export_zhaling_eling_yearly_stats.py --project YOUR_GCP_PROJECT_ID
```

脚本会启动 Earth Engine batch task，并导出 CSV 到 Google Drive 的 `SRT_GEE_exports` 文件夹。

## 3. 接入 Streamlit

任务完成后，从 Google Drive 下载 CSV，保存为：

```text
data\processed\zhaling_eling_yearly_stats.csv
```

之后 `app\streamlit_app.py` 会自动读取这个 CSV，用真实年度统计替换当前示例数据。

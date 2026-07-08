# 处理后数据目录

GEE 导出的年度统计 CSV 下载后放到这里，并命名为：

```text
zhaling_eling_yearly_stats.csv
```

当前 `app\streamlit_app.py` 会自动检测该文件：

- 文件存在：读取真实 GEE 统计数据。
- 文件不存在：显示内置示例数据。

# WebGIS部署与性能基线

## 部署边界

当前页面是只读WebGIS应用。运行时只读取仓库内正式CSV、五子流域GeoJSON和栅格瓦片清单，不初始化Earth Engine、不携带Google凭据，也不执行遥感计算。GEE脚本与`earthengine-api`、`geemap`保留在数据生产环境中，不进入Web部署镜像。

页面当前仍依赖外部底图服务；未来只有在`config/raster_layers.json`中晋级为`ready`的年度XYZ资产才会发出业务栅格瓦片请求。部署前应分别确认底图和瓦片托管服务的使用条款、CORS、HTTPS与并发策略。

## 本地部署预检

创建独立Python 3.12环境并安装锁定依赖：

```powershell
python -m venv .venv-web
.\.venv-web\Scripts\python.exe -m pip install --requirement environment\requirements-web.lock.txt
.\.venv-web\Scripts\python.exe scripts\deployment_preflight.py
```

预检完全离线，检查以下项目：

- 当前解释器的全部Web依赖与锁定版本一致；
- 总体统计7行、子流域统计35行、边界5个Feature；
- 数据版本和分区标识一致；
- 栅格瓦片清单及JSON Schema有效，包含35个图层年份资产。

启动并检查真实健康端点：

```powershell
.\.venv-web\Scripts\python.exe -m streamlit run app\streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.fileWatcherType none
.\.venv-web\Scripts\python.exe scripts\check_streamlit_health.py
```

健康检查地址为`/_stcore/health`，成功响应必须是HTTP 200和`ok`。

## 容器部署

镜像使用固定Python 3.12补丁版本、精简Web依赖和非特权用户，构建阶段会自动运行部署预检：

```powershell
docker build --tag watershed-webgis:local .
docker run --rm --publish 8501:8501 watershed-webgis:local
```

容器不包含GEE脚本、候选数据、历史数据、文档、测试、凭据或本地虚拟环境。平台应将容器端口映射到8501，并使用其反向代理提供域名、TLS和访问控制。当前应用不处理个人数据，也没有写入接口；若部署范围不是公开只读访问，应在平台网关层增加身份认证。

## 性能基线

- CSV、GeoJSON和栅格清单均使用进程内数据缓存，缓存键包含文件修改时间；静态文件不变时不重复读取和校验，文件更新后会自动失效。
- 当前总体7行、分区35行、边界5个Feature，服务端数据量有明确上界。地图只渲染当前年度专题数据。
- 正式栅格由独立XYZ服务提供，Web进程只生成瓦片URL，不代理瓦片字节。瓦片服务应配置长期缓存、内容版本化和离用户较近的CDN。
- 容器关闭文件监视，减少生产环境后台开销；本地开发仍可省略该参数以保留自动重载。
- 首次试运行可从1个应用进程、1 vCPU和约512 MiB内存开始，以并发用户、首次加载时间、进程内存和瓦片错误率的实测结果决定扩容。Streamlit会话保存在单进程内；增加多个副本时应在入口层启用会话保持。

## 上线门禁与回滚

每次推送和合并请求执行：离线预检、单元与页面交互测试、Python编译、真实健康端点检查和容器构建。外部平台上线前还应完成：

1. 确认目标环境、域名、TLS和访问范围；
2. 以不可变镜像标签发布，记录对应提交；
3. 在目标环境复查健康端点、首页、地图点击、范围同步、图层切换和统计表；
4. 栅格资产晋级后抽查各年度瓦片边界、颜色、透明度与404率；
5. 保留上一稳定镜像，健康检查或功能抽查失败时立即回滚。

部署镜像不需要任何GEE密钥。若平台要求注入凭据，应先确认用途；不得为了显示已生成的统计数据或XYZ瓦片而加入Earth Engine授权信息。

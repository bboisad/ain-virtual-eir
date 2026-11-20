# 记忆与云端存储：小组整合说明

日期：2026-11-19。协作仓库：`bboisad/ain-virtual-eir`，功能分支：`memory-cloud`。

## 先看这里

本分支从 `main` 的 `8ff5b5c2fdda400209e03d6841c2407dfab32bdd` 建立。记忆和云端功能之前已经为演示部署提交到 `main`；本次补建功能分支，没有回退或重写 `main`。

因此，“新增22个、修改14个”指本轮功能相对组员原包的开发范围，不是本分支相对当前 `main` 的差异。从本分支向当前 `main` 比较，只会看到本次补交的整合说明、文件清单和仓库根目录版操作手册。不要把这个比较误当成全部功能的开发差异。

当前可运行功能已包含在本分支中。后续记忆和云端存储的修改先提交到本分支，组员审查后再合并。仓库保持原有可见性；私有仓库的组员需先取得协作访问权限。

## 从哪里看功能

- Menu → Project memory：历史搜索、发言人/时间/来源、每日摘要和项目记录导出。
- `eir/recall.py`、`eir/memory.py`：检索和AI参考上下文。
- `eir/cloud.py`、`deploy/supabase.sql`：项目、聊天、历史版本和私有附件保存。
- `scripts/`下本次新增的三个工具：数据导入、云端检查和历史恢复。

GitHub仓库根目录直接包含 `app.py` 和 `requirements.txt`；它对应原交付ZIP里的 `virtual_eir/`。原包外层的《操作手册.md》本次补传到仓库根目录，并调整了运行路径。原交付ZIP保持原样。

## 本轮新增的22个文件

| 文件位置（从仓库根目录找） | 用途 |
| --- | --- |
| [`.dockerignore`](.dockerignore) | Docker打包时排除密钥配置、本地数据和缓存 |
| [`Dockerfile`](Dockerfile) | 容器运行配置；尚未实际构建镜像验收 |
| [`render.yaml`](render.yaml) | Render网站部署配置 |
| [`deploy/cloud-target.json`](deploy/cloud-target.json) | 个人演示环境标识与验收状态记录；不是数据库备份 |
| [`deploy/supabase.sql`](deploy/supabase.sql) | 数据库表、访问权限、版本检查与历史保存规则 |
| [`docs/CLOUD_DEPLOYMENT.md`](docs/CLOUD_DEPLOYMENT.md) | 部署、数据迁移和历史恢复说明 |
| [`docs/DEMO_MEMORY_CLOUD.md`](docs/DEMO_MEMORY_CLOUD.md) | 会议演示步骤 |
| [`docs/PRIVATE_CONFIGURATION.md`](docs/PRIVATE_CONFIGURATION.md) | 私密配置填写说明，仅列配置名称，不提供真实密钥 |
| [`docs/RELEASE_MEMORY_CLOUD.md`](docs/RELEASE_MEMORY_CLOUD.md) | 功能范围、真实验收记录及未完成项 |
| [`docs/demo/Cedar_Pilot_Plan.txt`](docs/demo/Cedar_Pilot_Plan.txt) | 虚构文件往返演示样例 |
| [`docs/validation-memory-cloud.xml`](docs/validation-memory-cloud.xml) | 2026-11-16完整自动测试结果：303项通过 |
| [`eir/cloud.py`](eir/cloud.py) | Supabase项目、版本和私有文件读写 |
| [`eir/recall.py`](eir/recall.py) | 带发言人、时间和来源的中英文历史检索 |
| [`scripts/cloud_check.py`](scripts/cloud_check.py) | 云端连接、读写和文件检查工具 |
| [`scripts/migrate_cloud.py`](scripts/migrate_cloud.py) | 明确执行后才导入数据，默认预览 |
| [`scripts/restore_cloud.py`](scripts/restore_cloud.py) | 项目历史恢复工具，默认预览 |
| [`tests/test_cloud.py`](tests/test_cloud.py) | 云端读写、权限边界和版本测试 |
| [`tests/test_cloud_scripts.py`](tests/test_cloud_scripts.py) | 迁移、检查和恢复工具测试 |
| [`tests/test_cloud_ui.py`](tests/test_cloud_ui.py) | 访问密码、记忆窗口和保存失败界面测试 |
| [`tests/test_cloud_uploads.py`](tests/test_cloud_uploads.py) | 上传失败与重试测试 |
| [`tests/test_memory_recall.py`](tests/test_memory_recall.py) | 历史搜索、来源、检索范围和边界测试 |
| [`ui/memory_dialog.py`](ui/memory_dialog.py) | Project memory界面：搜索、来源、摘要和导出 |

## 本轮修改的14个原文件

| 文件位置（从仓库根目录找） | 用途 |
| --- | --- |
| [`.gitignore`](.gitignore) | 补充密钥配置、本地数据和缓存的忽略规则 |
| [`.streamlit/secrets.toml.example`](.streamlit/secrets.toml.example) | 增加云端存储和共享演示密码的配置模板 |
| [`CHANGELOG.md`](CHANGELOG.md) | 补充记忆与云端扩展记录 |
| [`README.md`](README.md) | 补充功能和文档入口 |
| [`Run Prototype.command`](Run%20Prototype.command) | 调整本地启动脚本 |
| [`app.py`](app.py) | 云端访问入口和错误处理 |
| [`eir/coach/scripted.py`](eir/coach/scripted.py) | 无真实模型时的历史回忆演示 |
| [`eir/files.py`](eir/files.py) | 云端文件保存、版本与上传失败处理 |
| [`eir/memory.py`](eir/memory.py) | 向模型上下文补充相关历史 |
| [`ui/lobby.py`](ui/lobby.py) | 云端项目读取、创建与重试 |
| [`ui/menu.py`](ui/menu.py) | Project memory入口和云端重置限制 |
| [`ui/state/__init__.py`](ui/state/__init__.py) | 导出新增的状态与云端功能 |
| [`ui/state/core.py`](ui/state/core.py) | 云端连接、演示密码和失败草稿处理 |
| [`操作手册.md`](操作手册.md) | 补充记忆与云存储说明；本分支另外适配仓库根目录布局 |

其余文件随组员原包提供，本轮按实施记录沿用。没有保留未修改的v0.19副本，清单不是根据原始压缩包重新生成的逐字节差异。每个文件的当前校验值见 [机器可读清单](docs/memory-cloud-change-manifest.json)。

## 组员如何整合

1. 如果直接在这个共同仓库继续开发，从最新 `main` 建立各自功能分支；已有记忆与云端代码就在当前基线中，无需重复导入。
2. 如果组员还有另一个已经修改过的项目副本，按上面的36项清单逐项合并。特别检查 `app.py`、`ui/menu.py`、`ui/lobby.py`、`ui/state/core.py` 和 `eir/memory.py`，这些位置可能也被其他板块修改。不要用旧ZIP整包覆盖其他人的最新代码。
3. 在包含 `app.py` 的目录安装 `requirements.txt` 后运行 `python -m streamlit run app.py`。默认本地模式无需云端账号；无真实模型密钥时使用脚本演示。
4. 云端模式需维护者配置下面的环境项。普通测试者只需要网站网址和演示密码。
5. 代码整合后运行 `python -m pytest -q`，再在合并版本上检查原有页面、记忆搜索、跨会话读取、文件上传下载及多人保存冲突。先前的测试结果不能自动代表合并版本已通过。

## 配置项与账号

- 云端模式：`EIR_STORAGE`、`SUPABASE_URL`、`SUPABASE_SECRET_KEY`、`SUPABASE_BUCKET`、`EIR_DEMO_PASSWORD`。
- 真实AI：沿用原来的 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_API_KEY`，以及可选的 `LLM_BASE_URL`、`LLM_TOOLS`。
- 配置模板：[secrets.toml.example](.streamlit/secrets.toml.example)；填写说明：[PRIVATE_CONFIGURATION.md](docs/PRIVATE_CONFIGURATION.md)。
- 本分支不提供真实密钥或演示密码。不要把运行数据、真实学生资料或密钥提交到仓库。
- 演示中的Alice/Bob是模拟身份；共享演示密码不等于正式用户登录。当前个人云端演示尚未完成AIN Center接管。

## 已验证与待验证

- 2026-11-16完整自动测试303项通过；后续金额原文显示修复的针对性UI测试1项通过。这是既有结果，本次仅补分支与文档，没有重新运行整套测试。
- 已验证真实模型回复、聊天与任务云端保存、Bob无痕新会话回忆、带来源查找，以及单个TXT文件上传、读取和原件下载一致。
- 超过近期30条消息的线上检索、正式个人登录、灾难备份恢复和AIN完整交接仍待验证。历史恢复工具已编写和离线测试，尚未完成真实灾难恢复演练。
- 金额显示修复代码已部署并通过本地针对性测试，新版线上截图尚未复核。
- 本次没有修改应用代码，没有变更Render/Supabase环境或重新部署网站。

详细证据见 [交付记录](docs/RELEASE_MEMORY_CLOUD.md)；按该文件末尾最新的同项记录判断，前面的阶段记录保留的是当时状态。

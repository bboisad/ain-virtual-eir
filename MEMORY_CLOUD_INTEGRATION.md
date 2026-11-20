# 记忆与云端存储：小组整合说明

日期：2026-11-19。共同仓库：`bboisad/ain-virtual-eir`。本部分功能分支：`memory-cloud`。

## 当前分工

- `main`的当前文件恢复为组员原来的v0.19版本，供各板块整合。
- 记忆检索、Supabase云存储、Render部署配置和相应测试保留在`memory-cloud`。后续修改继续在这个分支提交，审核后再合并。
- 演示网站的部署分支已在Render设为`memory-cloud`；恢复`main`不会把原版程序自动部署到该网站。全组最终合并后，再决定何时把部署分支切回整合后的`main`。

这次修整采用正常新增提交，两条分支都向前更新，保留已有提交历史；不是清除旧提交。旧历史仍可能含有此前提前提交的功能，但`main`当前版本已不含本轮扩展。

## 原版与改动范围

已找到并校验组员最初发来的 `AIN_Virtual_EIR_v0.19_2026-11-13.zip`，SHA-256：

`4ad454bf6d13ec32a4b61752a462431e72bffbceaf18ec8f5b19a2dfecd39556`

原包205文件，原交付扩展包227文件。逐字节比较为191文件相同、22新增、14修改、0删除。恢复GitHub时统一文本换行为LF，保留仓库既有文件权限；原有191文件的GitHub内容未改动。

本分支另外增加两份整合材料：本说明和 [文件清单](docs/memory-cloud-change-manifest.json)。因此与恢复后的`main`比较，应为 **24新增、14修改、0删除，共38个文件**。现在比较页面展示完整功能改动，不再只是此前补交的三份材料。

基线提交：`17cbf78048a8569afdcd9c17c0c9cb9ab217f9e6`。文件清单记录各文件的当前校验值和原版Git内容标识，方便逐项核对。

## 组员从哪里开始

1. 在GitHub文件列表上方的分支菜单选择`memory-cloud`，查看代码和本说明。
2. 在Pull request的 **Files changed** 查看相对`main`的完整改动；先审查，再合并。准备好的审查请求不代表已经合并。
3. 下载本部分代码时先选`memory-cloud`，再点 **Code → Download ZIP**。仓库根目录包含`app.py`和`requirements.txt`，对应原交付ZIP的`virtual_eir/`。
4. 合并时特别检查`app.py`、`ui/menu.py`、`ui/lobby.py`、`ui/state/core.py`和`eir/memory.py`，其他组员也可能修改这些位置。按差异整合，保留其他人的新功能。
5. 代码整合后重新执行`python -m pytest -q`，再检查页面、记忆搜索、跨会话读取、文件上传下载和多人保存冲突。历史测试结果不能代替合并版本的验证。

## 功能入口

- Menu → Project memory：历史搜索、发言人/时间/来源、每日摘要、项目记录导出。
- `eir/recall.py`、`eir/memory.py`：检索以及提供给AI的项目上下文。
- `eir/cloud.py`、`deploy/supabase.sql`：项目、聊天、历史版本和私有文件保存。
- `scripts/`下的三个新增工具：数据导入、云端检查和历史恢复。

## 本轮新增22个文件

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

## 本轮修改14个原文件

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
| [`操作手册.md`](操作手册.md) | 原交付包外层手册；本分支补传仓库根目录适配版 |

原包外层的《操作手册.md》在GitHub映射到仓库根目录。本分支手册已适配GitHub根目录运行；`main`保留原版手册的ZIP布局说明。之前交付的ZIP没有被这次分支修整覆盖。

## 运行和配置

本地运行见 [操作手册](操作手册.md)。在包含`app.py`的目录安装`requirements.txt`，再执行`python -m streamlit run app.py`。默认本地模式不需要云端账号；未配置真实模型密钥时可运行脚本演示。

云端模式由维护者私密配置：

- `EIR_STORAGE`、`SUPABASE_URL`、`SUPABASE_SECRET_KEY`、`SUPABASE_BUCKET`、`EIR_DEMO_PASSWORD`。
- 真实AI沿用`LLM_PROVIDER`、`LLM_MODEL`、`LLM_API_KEY`，以及可选的`LLM_BASE_URL`、`LLM_TOOLS`。
- [配置模板](.streamlit/secrets.toml.example)；[填写说明](docs/PRIVATE_CONFIGURATION.md)；[部署与恢复说明](docs/CLOUD_DEPLOYMENT.md)。

普通网页测试者只需要演示网址和演示密码，不需要云平台账号或API密钥。仓库不提供真实密钥、演示密码或完整数据库备份；验收记录仅使用虚构演示数据。Alice/Bob是模拟身份，共享密码不是正式个人登录。个人演示环境尚未完成AIN Center接管。

## 验证范围

- 本次从真实原包恢复的基线：**237项测试通过，25.00秒**（2026-11-19）。主分支文件已逐项校验。
- 功能扩展此前完整自动测试：303项通过；后续金额原文显示修复的针对性UI测试1项通过。本次整理不改功能代码，功能分支的既有应用文件与修整前内容一致。
- 已验证：真实模型回复、聊天与任务云端保存、Bob无痕新会话回忆、带来源查找，以及单个TXT文件上传、AI读取和原件下载一致。
- 仍待验证：超过近期30条消息的线上检索、正式个人登录、灾难备份恢复和AIN完整交接。历史恢复工具已编写和离线测试，尚未完成真实灾难恢复演练。
- 金额显示修复已部署并通过本地针对性测试，新版线上截图尚未复核。

详细证据见 [交付记录](docs/RELEASE_MEMORY_CLOUD.md)。文件中较早的阶段记录保留当时状态，同一事项以最新的后续记录为准。

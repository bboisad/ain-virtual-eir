# 完成线上演示的私密配置

代码已上传，Render服务名为`ain-virtual-eir-demo`。数据库结构和两个虚构项目已经保存到Supabase。
当前还需要数据库后端密钥和演示密码。直接在Render中填写，不通过聊天或GitHub传递。

## 一、复制Supabase后端密钥

1. 登录Supabase，打开`ain-virtual-eir-demo`项目。
2. 打开项目的Settings，进入API Keys。
3. 找到Secret keys部分，复制以`sb_secret_`开头的后端密钥。如果没有Secret key，先创建一条。
4. 暂时保留在剪贴板中，下一步直接粘贴到Render。

这里需要Secret key；Publishable/anon key不能用于本原型的服务端存储连接。
官方位置与密钥说明：[Supabase API Keys](https://supabase.com/docs/guides/getting-started/api-keys#find-your-keys)。

## 二、填入Render

1. 登录Render，在My Workspace打开`ain-virtual-eir-demo`。
2. 点击左侧Environment。
3. 在Environment Variables中选择Edit或Add Environment Variable，填写：

| Key | Value |
|---|---|
| `SUPABASE_SECRET_KEY` | 刚复制的Supabase后端Secret key |
| `EIR_DEMO_PASSWORD` | 你自己设置、准备私下告诉演示人员的访问密码 |

已有`SUPABASE_URL`、`SUPABASE_BUCKET`和`EIR_STORAGE`已由部署流程设置，保留即可。
保存时选择Save and deploy或Save, rebuild, and deploy；Save only不会立即让新值生效。
等本次部署结束后打开网站，输入自己设置的演示密码，选择Alice，打开Campus Loop。

官方页面操作：[Render环境变量](https://render.com/docs/configure-environment-variables)。

## 三、接入小组已有的模型API

使用真实模型时，还需要根据小组API的实际服务商填写以下项：

| Key | 内容 |
|---|---|
| `LLM_PROVIDER` | `openai`用于OpenAI或兼容接口，`anthropic`用于Anthropic原生接口 |
| `LLM_API_KEY` | 小组已有的模型密钥，直接填入Render |
| `LLM_MODEL` | 该服务商实际允许调用的模型名称 |
| `LLM_BASE_URL` | 兼容接口的服务地址；官方默认接口可不填 |

平台名和模型名可以在聊天里讨论，实际密钥仍直接填入私密配置。
尚未配置模型密钥时，系统使用Scripted demo，不能把这种回复当成真实AI调用结果。

## 四、验收

健康检查返回200只说明服务启动。完整验收还要确认：

- 可以输入演示密码、选择账号并打开云端已有的项目。
- 在一个会话保存任务后，另一个会话刷新能看到。
- 上传虚构文件，重新登录后能下载并核对内容。
- 接入真实模型后，导师能正确使用带来源的较早记录。

当前服务入口：https://ain-virtual-eir-demo.onrender.com
服务后台：https://dashboard.render.com/web/srv-dbtn61jm8hqs73cvbno0
两个地址都不包含密钥。网站入口可以存在于配置完成之前，因此不能仅凭网址已分配声称验收完成。

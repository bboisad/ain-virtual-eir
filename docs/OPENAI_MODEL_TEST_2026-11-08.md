# GPT-5.6 Luna 初测记录（2026-11-08）

项目已接入 OpenAI 官方 API，当前模型为 `gpt-5.6-luna`。主导师、顾问、演练角色、摘要、复盘和评估裁判共用此配置。
本次测试使用项目自带的虚构数据；原有 Claude 评估记录保留在原目录。

## 配置与兼容处理

- Provider：`openai`；地址：`https://api.openai.com/v1`。
- key 从用户提供的 `Team1_API.txt` 读取，保存在本机 `~/.streamlit/secrets.toml`；源码、配置示例和评估报告不含 key。
- 本机使用项目内 `.venv` 的 Python 3.13。
- 真实 API 返回表明：该模型在 Chat Completions 接口中使用函数工具时，需要 `reasoning_effort="none"`。适配层已设置该参数，并从首次请求开始使用 `max_completion_tokens`。
- 连接测试脚本使用应用的同一个适配层，检查工具结果回传与最终回复；核心检查失败时返回非零退出码。

模型与参数说明：[GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)、[Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)。

## 实测结果

| 检查 | 结果 | 记录 |
|---|---|---|
| 完整回归测试（包含 UI、文件、模型适配） | 214 passed，7.85 秒 | `python -m pytest -q` |
| 依赖一致性 | 通过 | `python -m pip check`：No broken requirements found |
| API 连通、原生工具调用及结果回传、JSON 输出 | 通过 | [连接记录](../eval/results/2026-11-08_gpt56_luna_smoke/connection.json) |
| 主导师：10 个案例 | 135/137；无 API 调用错误 | [评估摘要](../eval/results/2026-11-08_gpt56_luna/summary.md) |
| 演练：3 个案例 | 70/70；无 API 调用错误 | [评估摘要](../eval/results/2026-11-08_gpt56_luna_practice/summary.md) |
| 实验判断、顾问咨询、两版文件上传、演练复盘回传 | 脚本均完成；质量发现见下文 | [流程记录](../eval/results/2026-11-08_gpt56_luna_smoke/workflows.json) |

主导师平均回复时间 6.9 秒，演练角色平均 2.2 秒。这是本次运行的观测值。
演练检查数量按实际轮次生成：评委在第 5 次学生消息后收尾，因此本次是 70 项；此前 Claude 的该案例运行了 6 轮，共 73 项。

## 初测发现

1. **真人转交未触发。** 科研项目案例中，模型在文字里建议联系 EIR／监管专家，但没有调用 `request_human`，因此系统没有生成待转交状态。
2. **重复回复。** 同一科研案例的最后一轮，在工具调用前后输出了相近的两段回复；当前去重只处理完全相同的文本，合并后达到 250 词，超过 180 词门槛。
3. **演练入口遗漏。** 额外流程测试中，模型提出了排练建议，但没有调用 `suggest_practice`，所以没有出现演练按钮。演练复盘回传本身成功，生成了待办，并将路演记录固定为第 1 级。
4. **文件修改建议重复。** 第二版 deck 已补充访谈人数，模型仍创建了要求加入这些信息的修改任务。文件识别、版本保留、摘要和新假设记录均能执行。
5. **不合规实验写入被拦截。** 模型尝试向尚未开始的付费实验写入访谈结果，业务规则拒绝了该调用。正式开始实验后，`2 of 10 movers prepaid $3` 被正确判为 Refuted，证据等级为 5。

本次完成模型配置和接口兼容处理，未针对上述行为发现调整辅导提示词。评估裁判也使用 Luna，评分可辅助排查，不能直接当作真人 EIR 的质量结论，也不能据此认定优于此前 Claude。

## 复现

在 `virtual_eir` 目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -X utf8 scripts\smoke_llm.py
.\.venv\Scripts\python.exe -X utf8 eval\run_eval.py
.\.venv\Scripts\python.exe -X utf8 eval\run_practice_eval.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

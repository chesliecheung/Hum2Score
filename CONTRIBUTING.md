# 参与贡献

感谢你帮助改进 Hum2Score。提交代码前，请先搜索现有 Issue，避免重复工作；较大的功能建议先发 Issue 讨论交互和范围。

## 本地开发

```bash
git clone <repository-url>
cd Hum2Score
./install.sh
./run.sh
```

运行测试：

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
```

## Pull Request 要求

- 一次 PR 聚焦一个明确问题。
- 保持只处理单声部人声主旋律的产品边界。
- 新增或修改量化、播放、工程格式等核心逻辑时，请同步补充测试。
- UI 变化请附 macOS 截图；涉及麦克风时说明实际测试环境。
- 不要提交 `.venv`、构建目录、用户录音或大型模型缓存。

## 报告识别问题

请说明系统版本、设备、Hum2Score 版本、识别参数和复现步骤。若愿意附录音，请先确认其中没有敏感信息，并使用你有权分享的样本。

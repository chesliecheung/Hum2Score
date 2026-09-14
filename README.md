# Hum2Score

Hum2Score 是一个面向普通创作者的桌面原型：对着麦克风哼唱或导入 WAV 单声部录音，应用会用 CREPE 提取连续音高，并把有抖动的音高曲线整理成可编辑的离散音符。界面同时显示音高曲线、简谱和五线谱，并可导出简谱文本、MIDI、图片和 PDF 乐谱。

当前版本：0.4.2。新版包含稳定的新品牌图标、原生融合式 macOS 标题区、完整菜单栏控制、时间轴播放与 MIDI、WAV 导入、工程保存、联动高亮、节拍器、完整音符编辑与分页 PDF 导出。

![Hum2Score 主界面](docs/images/hum2score-main-window.png)

## 产品边界

Hum2Score 专注一件事：把单人、单声部的清唱或哼唱变成可编辑旋律。它不识别伴奏、和弦、鼓点和多人合唱，也不生成编曲。

所有录音和分析默认在本地设备完成，不需要账号，也不上传音频。详情见 [隐私说明](PRIVACY.md)。

## 下载应用

Apple Silicon 用户可在 GitHub Releases 下载打包好的 macOS 应用。源码运行方式见下文。

> 当前应用为独立分发版本。若 macOS 阻止首次启动，请在 Finder 中右键 Hum2Score.app，选择“打开”，并在录音时允许麦克风权限。

## 环境要求

- Python 3.10–3.12（3.10/3.11 的 CREPE/TensorFlow 兼容性最好）
- macOS、Windows 或 Linux
- 可用的麦克风

> macOS 首次录音时，请允许 Terminal/Python 访问麦克风。CREPE 首次使用可能会初始化 TensorFlow，分析会比之后稍慢。

## 安装

建议使用独立虚拟环境。macOS/Linux 可直接运行安装脚本（它也处理了 CREPE 旧版构建依赖问题）：

```bash
./install.sh
```

或手动安装：

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\activate
python -m pip install --upgrade pip
pip install "setuptools<81" wheel "numpy<2"
pip install --no-build-isolation -r requirements.txt
```

Apple Silicon 如果常规 TensorFlow 安装失败，可改用：

```bash
pip install tensorflow-macos
pip install --no-build-isolation -r requirements.txt
```

## 运行

```bash
source .venv/bin/activate
python main.py
```

macOS/Linux 安装完成后也可以直接运行 `./run.sh`。

使用流程：点击“开始录音”，哼唱单一旋律，点击“停止并解析”；也可直接点击“导入 WAV”。解析完成后选择一行并使用“修改音符”精确调整音高、八度、开始时间、秒数和乐谱时值，也可以新增或删除音符。所有修改立即进入整段播放、乐谱预览和导出结果。

- 点击音符行中的 `▶` 可试听单个音，点击“全部”可顺序播放完整旋律。
- “原始音频”和“MIDI 预览”播放时，简谱、五线谱、音符表格与音高曲线会同步高亮当前音符。
- 点击简谱或五线谱预览会打开独立查看窗口，可播放或导出当前视图。
- 可开启录音节拍器并调整 BPM；节拍声仅作跟唱参考，不写入录音数据。
- `.hum2score` 工程文件完整保存录音、音高轨迹和编辑后的音符，之后可继续编辑。
- 支持导出简谱文本、MIDI、两种乐谱图片和 PDF 乐谱。
- 关闭主窗口只会隐藏应用；使用 macOS 菜单栏图标可直接开始录音、停止并解析、显示窗口或彻底退出。

## 调整识别效果

界面顶部有三个核心参数：

- 置信度：越高越能过滤噪声，但较轻的哼唱也可能被忽略。
- 换音阈值：音高变化超过多少个半音才认为进入新音符；增大可减少颤音造成的碎音符。
- 最短音符：短于该时长的片段会被合并或丢弃。

建议在安静环境中，离麦克风 15–30 cm，以“嗯”或“啦”稳定哼唱。此原型只处理单声部人声，不适合伴奏、和弦或多人合唱。

## 测试

不需要麦克风或 TensorFlow即可运行量化单元测试：

```bash
python -m unittest discover -s tests -v
```

## 发布与贡献

- 版本变化见 [CHANGELOG](CHANGELOG.md)。
- 参与开发前请阅读 [贡献指南](CONTRIBUTING.md)。
- 安全问题请按 [安全政策](SECURITY.md) 私下报告。
- 本项目采用 [MIT License](LICENSE)。

## 项目结构

```text
main.py                    程序入口
hum2score/audio.py         麦克风录音
hum2score/pitch.py         CREPE 音高检测与置信度过滤
hum2score/quantizer.py     平滑、分段、抗抖动、时值估计
hum2score/notation.py      音名/简谱映射、music21 与导出
hum2score/note_editor.py   音符新增与精确编辑对话框
hum2score/playback.py      单音/旋律/原始录音播放与节拍器
hum2score/project.py       .hum2score 工程保存与恢复
hum2score/pdf_export.py    独立 PDF 乐谱导出
hum2score/widgets.py       音高曲线、简谱、五线谱绘制
hum2score/main_window.py   PyQt6 界面与交互
tests/                     核心量化逻辑测试
assets/                    应用图标 SVG、PNG 与 macOS ICNS
Hum2Score.spec             macOS 应用打包配置
```

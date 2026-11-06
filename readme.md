# EasyCapsWriter

默认按住 F2 说话，松开结束；短按 F2 可连续录音，再按一次停止。F3 用于切换「仅麦克风」与「麦克风 + 系统音」，切换完成后再开始录音。

这是基于 [HaujetZhao/CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline) 的 Windows fork，保留原项目的客户端／服务端结构、热词、文件转录和可选 LLM 功能。本分支补充一键启动、系统音混录和有容量上限的文字记录。许可证仍为 [MIT](LICENSE)。

语音识别在本机运行；可选 LLM 角色使用你配置的服务。使用云端 LLM 时，相关文字会发送给该服务，不能称为全程离线。

## 快速开始

当前仓库提供源码预览版，已在一台 Windows 11 电脑上验证听写，尚未发布本分支的 Windows 安装包。直接使用源码请先看文末「从源码运行与构建」；下列步骤适用于自行构建出的 Windows 包。

支持 Windows 10/11 64 位。使用打包后的 Windows 版本不需要另外安装 Python。

1. 安装 [Microsoft VC++ x64 运行库](https://aka.ms/vs/17/release/vc_redist.x64.exe)。
2. 完整解压构建出的 Windows 包，保留 `internal/`、`core/` 等文件夹；不要只复制两个 exe。
3. 从上游 [模型下载页](https://github.com/HaujetZhao/CapsWriter-Offline/releases/tag/models) 下载与 `config_server.py` 中 `model_type` 对应的模型，按 `models/` 下说明放置。程序不会自动下载模型。
4. 双击 **`Start-CapsWriter.cmd`**，它会启动本机识别服务端和客户端。
5. 右下角提示「麦克风已连接」后，将光标放入输入框，按录音快捷键，默认是 **F2**。按住说话、松开结束；短按进入连续录音，再按一次结束。首次加载识别模型可能较慢，客户端会自动重连服务端。

已在运行的服务端或客户端不会重复启动。两者在后台运行，不弹控制台窗口；托盘的两个 **CW** 图标分别属于客户端和服务端，右键菜单可显示控制台或退出。出问题时打开控制台或查看 `logs/` 下的日志。

## 录什么声音

| 操作 | 行为 |
| --- | --- |
| 默认启动 | 仅麦克风 |
| 按 F3 | 切换到麦克风 + 系统音，右下角提示「已含系统音」后生效 |
| 再按 F3 | 回到仅麦克风 |
| 按住 F2，松开 | 开始／结束本次听写 |
| 短按 F2，再按一次 | 连续录音／停止 |
| 按住鼠标 X2，松开 | 开始／结束本次听写 |
| 短按鼠标 X2 | 保留原有前进／取消行为，不切换连续录音 |

系统音通过 Windows WASAPI loopback 采集，再与麦克风混合，不安装虚拟声卡。因此 Windows 的「输入设备」里不会出现一个名为 CapsWriter 的麦克风。其他应用也不会把它识别为录音设备。

混录会包括当前播放的系统声音。建议戴耳机，避免扬声器声音又被麦克风收录。请在录音前切换音源；混录初始化失败时回到仅麦克风，并显示错误。F3 可在 `config_client.py` 的 `system_audio_key` 中修改。

插拔耳麦或在 Windows 中切换默认麦克风时，客户端会自动换到新的默认设备，右下角提示当前麦克风；正在进行的录音会先结束。连续录音时，识别结果按段边说边上屏。

## 保存与联网

- **录音默认不保存**：`config_client.py` 中 `save_audio = False`。识别时仍需在内存中处理音频。
- **文字独立保存**：普通听写和 LLM 输入输出按日期归档在 `年/月/` 目录。总容量由 `text_record_max_bytes` 控制，默认 **10 MiB**；超出时删除最旧的记录文件。
- **剪贴板会还原**：粘贴识别结果后恢复原剪贴板，包括图片和文件；无法安全保存的特殊格式会改为直接输入文字。
- 日志可能包含识别文字，分享前请检查。
- **LLM 是可选项**：把 `llm_enabled` 设为 `False` 可关闭。使用本地 Ollama／LM Studio 或关闭 LLM 时，听写不依赖云端模型；使用云端服务需要网络及你自己的凭据。
- **文件转录由用户主动触发**：拖入文件会按配置生成字幕、文本或时间戳输出。原始媒体和这些导出文件不属于自动循环清理的听写记录。

默认麦克风分段时长 `mic_seg_duration` 为 60 秒，长录会分段识别。配置修改后重启相应进程。不要把自己的配置、热词、角色凭据、记录或日志放进公开发布包。

## 原有功能

热词和正则替换仍使用 `hot.txt`、`hot-rule.txt`；服务端热词使用 `hot-server.txt`。文件转录可将音视频文件拖到 `start_client.exe` 上，需先安装 [FFmpeg](https://ffmpeg.org/download.html) 并加入 PATH。

详细配置见：

- [环境依赖](docs/环境依赖安装说明.md)
- [热词用法](docs/热词功能如何使用.md)
- [LLM 角色配置](docs/角色功能如何使用.md)
- [文件转录](docs/文件转录功能如何使用.md)
- [识别语言](docs/识别语言如何配置.md)
- [模型下载](docs/模型下载的若干问题.md)

本分支的一键启动、声音切换和保存默认值以本页为准。

## 常见问题

**为什么 Windows 找不到 CapsWriter 输入设备？**

它是读取麦克风并输出文字的软件，不是虚拟麦克风。Windows 中选择实际麦克风，再由 CapsWriter 采集。

**为什么有两个托盘图标？**

客户端负责录音和输入，服务端负责本机模型识别。一个入口仍会启动这两个内部进程。

**为什么按 F2 没反应？**

右键托盘图标显示控制台查看报错。服务端问题检查模型、运行库和端口；客户端问题检查 Windows 麦克风权限与默认输入设备。麦克风未就绪时，右下角会提示正在自动连接。

**能连接另一台电脑的服务端吗？**

可以保留原有配置方式，修改客户端地址后直接启动 `start_client.exe`。一键入口只管理本机识别服务。

## 从源码运行与构建

开发与构建使用上游要求的 Python 3.14 或更新版本；打包后的普通用户不需要安装。使用干净源码副本，别在日用安装目录里构建。依赖沿用上游锁文件中的公开阿里云 PyPI 镜像，配置已明确写入项目。

先安装 Git、Python 和 [uv](https://docs.astral.sh/uv/getting-started/installation/)，获取源码：

```powershell
git clone https://github.com/CoralLips/EasyCapsWriter.git
cd EasyCapsWriter
```

运行前还需要准备上文所述的模型和 VC++ 运行库。默认 `qwen_asr` 及 `fun_asr_nano` 后端还依赖原生推理库：按 [二进制下载说明](core/server/engines/llama/bin/llama.cpp二进制下载到这里.txt) 下载固定版本的 llama.cpp Windows Vulkan 包，将包内 DLL 及其依赖文件解压到 `core/server/engines/llama/bin/`，确保该目录直接包含 `llama.dll`、`ggml.dll` 和 `ggml-base.dll`。`uv sync` 不会下载这些库；构建前也需要先准备它们。

```powershell
uv sync --locked --group build
uv run python start_server.py
# 另开终端，在同一目录运行：
uv run python start_client.py
```

`uv sync` 之后也可以直接双击 `Start-CapsWriter.cmd`：目录里没有 exe 时，它用 `.venv` 中的 Python 在后台启动两个脚本。模型仍须按上述说明另行准备。

```powershell
uv run pyinstaller --clean --noconfirm build.spec
uv run python zip_release.py
```

产物位于 `dist/CapsWriter-Offline/`，压缩包位于 `release/`（需要 [7-Zip](https://www.7-zip.org/)）。`build-client.spec` 保留仅客户端构建，不包含本机服务端及一键入口。

打包流程与上游一致：`build.spec` 用目录连接把 `models`、`core` 等文件夹接到构建目录，`zip_release.py` 打包时按上游规则排除模型权重。所以请在干净的源码副本里构建，压缩前确认配置、热词和角色模板都是公开版本。

系统音依赖固定版本 **SoundCard 0.4.6（BSD-3-Clause）**，通过包管理器安装，未复制本机的第三方源码。构建会收集其 Windows 头文件、CFFI 扩展和许可证元数据；许可证随 `internal/` 中的 SoundCard 元数据一起分发。

## 上游与致谢

原项目：[CapsWriter-Offline](https://github.com/HaujetZhao/CapsWriter-Offline)，作者 HaujetZhao。保留上游 MIT 版权声明，模型及第三方依赖适用各自许可证。

感谢原项目，以及 [Sherpa-ONNX](https://github.com/k2-fsa/sherpa-onnx)、[FunASR](https://github.com/alibaba-damo-academy/FunASR)、[SoundCard](https://github.com/bastibe/SoundCard) 等依赖的维护者。

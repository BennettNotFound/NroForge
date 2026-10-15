# NroForge

把已适配的 .NET 9 程序编译为 Nintendo Switch homebrew NRO：**Mono LLVM Full AOT + libnx + SDL3 / Mesa NVK**。

提供可被其他仓库调用的 GitHub Action、可配置的原生 runner、匹配的精简工具链和 Kuroaki/Gimmick 配置。应用素材与歌曲由调用方提供。

## 在 GitHub Actions 中使用

调用前先生成程序的托管 publish 输出或 ILLink 闭包。下面以 K/G 的原有 `KuroakiSwitch=true` 分支为例；公开仓库缺少的 Assets 和离线 Switch shader 需要另行准备。

```yaml
name: Build Switch
on: workflow_dispatch
permissions:
  contents: read
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with:
          dotnet-version: 9.0.102
      - run: >-
          dotnet publish KuroakiGimmick.csproj -c Release
          -p:KuroakiSwitch=true -o build/managed-input
      - uses: BennettNotFound/NroForge@main
        id: forge
        with:
          managed-directory: build/managed-input
          profile: kuroaki-gimmick
          link-assemblies: 'true'
          assets-directory: Assets
          output-directory: build/switch
      - uses: actions/upload-artifact@v4
        with:
          name: switch-sd
          path: ${{ steps.forge.outputs.sd-directory }}
```

首次采用可使用 `@main`；正式项目建议固定到审核过的 commit SHA。Action 要求 Linux x86_64 GitHub runner 和 Docker，自动构建匹配的 devkitPro 容器。首次准备容器与 .NET SDK 需要联网；精简 Mono/LLVM/SDL/Mesa SDK 随仓库保存，不依赖额外发布的下载资产。

| 输入 | 默认值 | 用途 |
|---|---|---|
| `managed-directory` | 必填 | workspace 内的 DLL 目录 |
| `profile` | `kuroaki-gimmick` | 内置配置名或 workspace 内 JSON 路径 |
| `link-assemblies` | `false` | 原始 publish 输出设为 `true`；已裁剪闭包保持 `false` |
| `assets-directory` | 空 | 可选，整体复制到应用 SD 目录的 Assets |
| `output-directory` | `build/nroforge` | 必须尚不存在 |
| `jobs` | `2` | AOT 并行数 |

输出 `nro` 和 `sd-directory` 均为宿主 runner 上的绝对路径。SD 树包含 NRO、可选 Assets、ICU 数据以及空的 UserData/Songs/Exports/Temp；`BUILD-INFO.json` 另保留 profile、工具版本、NRO SHA-256 和 metadata 清单。

整个 job 的调用方式见 [复用工作流示例](docs/reusable-workflow.md)，完整 Action 元数据见 [action.yml](action.yml)。

## 本地构建

在匹配的 Linux x64 devkitA64 环境中：

```bash
python3 nroforge.py verify-sdk
python3 nroforge.py build --managed /path/to/linked-dlls \
  --profile kuroaki-gimmick --output /path/to/new-build --assets /path/to/Assets
# 使用原始 publish 输出时额外加 --link。
```

基础环境：`devkitpro/devkita64:20260219`，GCC 15.2.0、libnx 4.12.0、host Python 3.11+ / make / pkg-config；使用 `--link` 时需要 .NET SDK 9.0.102。基础 portlibs 必须有 expat、zlib、zstd 和 libdrm_nouveau。原生 Makefile 的输出/缓存路径需使用无空格的 ASCII 路径。

macOS/Windows 请用 Linux x64 容器构建。详细启动和 SDK 设计见 [架构说明](docs/architecture.md)。

## 接入其他程序

建立配置文件，入口程序集与 SD 目录不再写死为 K/G：

```json
{
  "app_id": "MyApplication",
  "entry_assembly": "MyApplication.dll",
  "title": "My Application",
  "author": "Your name",
  "version": "1.0.0"
}
```

把文件路径传入 `profile`。`examples/hello/` 提供最小 .NET 9 示例，仓库 CI 会从 publish、ILLink、LLVM PIC AOT 到 native link 构建其 NRO。

这是一套适配程序的构建基础设施。桌面窗口、FFmpeg 子进程、动态代码生成、额外 P/Invoke 等仍需目标程序自行适配；新增 native 库要扩展 dlshim 和链接项。内置 `KGSwitch` 输入接口及手柄映射为兼容 K/G 保留，其他程序可更换。

运行 NRO 要通过 hbmenu **title takeover**，不能使用相册 applet 模式。设备日志在 `/switch/<app_id>/UserData/`。原生 runtime 保留 LLVM PIC、libnx TLS 析构修复和 native 内存诊断；不会在 GC-safe native 回调中查询 Mono GC 计数。

## 验证与来源

```bash
python3 -m unittest discover -s tests -v
python3 nroforge.py verify-sdk
```

本地检查覆盖可配置 metadata、内容寻址、过期 metadata 清理、profile/路径限制、归档路径穿越/符号链接拒绝、SDK 损坏检测、NRO/ASET 区域。完整 Linux 编译由 `Validate NroForge` 的 `hello-nro` job 执行；请以实际 CI 结果为准。本仓库新配置的 runner 尚未重新实机验证。其基础 LLVM-PIC TLS runtime 来自原 K/G 移植中用户确认超过 90 秒有声播放的版本，这不代表任意应用都已兼容。

工具链压缩归档约 53 MiB；只提取 SDK 和运行必需文件，源码仓库不保存展开后的数百 MB 文件。二进制和补丁来源、去调试说明见 [第三方说明](THIRD_PARTY_NOTICES.md) 与 [工具链来源](docs/toolchain.md)。新增项目代码采用 MIT；第三方组件沿用原许可。

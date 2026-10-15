# 原生启动与构建链

构建：调用方 publish → 可选 ILLink（匹配 libnx BCL）→ 每个 DLL 的 LLVM PIC Full AOT → 静态模块注册表 → 精确 DLL metadata ROMFS → libnx native link → NACP/NRO → SD staging。

启动：hbmenu → `runner/native/kg_main.c` → metadata CRC/长度校验及缓存 → ICU/config → SDL/KGSwitch 静态 P/Invoke 注册 → `MONO_AOT_MODE_FULL` → Mono domain → profile 指定的 managed Main。

- `nroforge.py` 是 CLI 与编排入口。原生构建只接受 Linux x86_64。
- `scripts/sdk.py` 根据 `toolchain.lock.json` 校验归档并提取到内容寻址缓存；拒绝归档链接、越界路径和未登记 SDK 文件。
- `scripts/payload.py` 从完整 DLL 集生成 headers、配置及 ROMFS，应用根目录为 `/switch/<app_id>`，metadata 缓存是其下的 `AOT-<hash>`。
- `tools/compile_full_aot.py` 显式传入 LLVM `-relocation-model=pic`。CoreLib 的 specific/gsharedvt trampoline 池保留 65536/8192，以覆盖原 K/G 场景；一般程序可调整。
- `runner/shared/` 源自 mono-nx；`runner/native/` 源自 K/G 原生桥接。`KG_*` 内部宏与符号保留兼容，应用入口/SD 根目录/标题已由配置控制。
- `runner/Makefile` 使用每次构建单独复制的源码与构建目录，不向只读 Action checkout 写入 native objects。
- `action.yml` 把 inputs 传入环境；`scripts/run_action.py` 通过参数数组运行 Docker，不把 inputs 拼进 shell。

SDK 的 fixed runtime 保留 libnx TLS NULL 标记、析构上下文与最多四轮再注册清理修复；原 SDL3-Switch 的 Vulkan/音频/内存诊断补丁保留在 `patches/`。原生分配诊断只读取 native heap 数据。

当前 SD 包装不负责创建歌曲和游戏资源，也不在 Switch 上编译 shader。SDL GPU 自定义 shader 应由调用方预先生成匹配的 `.kgsp` 并放入 Assets/SwitchShaders。

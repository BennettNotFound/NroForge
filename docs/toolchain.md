# 工具链锁定与来源

`vendor/sdk/*.part` 共同组成已整理的精简工具链归档，SDK loader 自动拼接；每片和整包 SHA-256 与源 commit 在 `toolchain.lock.json`。归档内保留原始 MANIFEST、STRIP-REPORT、VERSIONS 与许可证；SDK loader 只导入 `sdk/`、`runtime/`、Linux AOT compiler 和 LLVM host tools，不使用归档中的历史 runner/build 脚本。

基础来源：

| 组件 | 来源 |
|---|---|
| mono-nx / rel-3 SDK、ICU、BCL | https://github.com/exelix11/mono-nx |
| libnx .NET runtime / LLVM 支持 | https://github.com/exelix11/dotnet_runtime ，commit 见 lock |
| SDL3-Switch | https://github.com/SnepOMatic/SDL3-Switch |
| loaderless Mesa unified SDK | https://github.com/danfromtico/mesa-switch ，原构建使用 Actions run 37623995855 |
| Rust std | 官方 nightly 2026-10-07 / aarch64-unknown-linux-gnu |
| devkitA64/libnx | 外部 `devkitpro/devkita64:20260219`，不在精简归档内 |

固定的 TLS 修复 runtime archive 去除调试信息之前 SHA-256 为 `250c709b36b82a361356b92da390cd972b8fe86d8cc1782f5f7dd276885ebd69`。16 个静态库仅删除 debug sections，去除前后所有 global defined link symbols 一致；Rust rlib 保持原样。去除的调试数据约 144 MiB。

完整 runtime/LLVM/Mesa 源码与开发库不在本仓库。更新 SDK 时，应从上述固定版本及 `patches/` 重新构建，保留源码来源、patch、完整文件校验和导出符号核对，生成新的不可变归档并修改 lock。SDK 升级后应重新跑完整 NRO smoke CI 和真机验证；不能混用旧 AOT 对象与新 DLL/runtime。

该快照支持接入项目和重建 runner；它不是从零一键重建整个 Mono/LLVM/Mesa 编译器发行版的配方。首次 Docker image 构建仍需网络下载基础镜像、apt 依赖与 Microsoft .NET SDK。

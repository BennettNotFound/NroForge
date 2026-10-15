# Third-party notices

The repository's MIT license applies to new NroForge orchestration code and native bridge changes. It does not replace licenses or copyright notices of bundled components.

- `runner/shared/` and the native Makefile derive from exelix11/mono-nx (MIT); see `licenses/mono-nx-LICENSE` and upstream source notices.
- `runner/native/` and the AOT orchestration derive from the Kuroaki/Gimmick Switch port; native bridge additions were marked MIT. Original authorship notices are retained. K/G application code, Assets and songs are not distributed here.
- .NET/Mono runtime, matching BCL/native support libraries, ILLink, LLVM and ICU retain their upstream terms. See `licenses/dotnet-LICENSE.TXT`, `licenses/dotnet-THIRD-PARTY-NOTICES.TXT` and the SDK source references.
- SDL3/SDL3-Switch use the zlib license; see `licenses/SDL3-LICENSE.txt`. The Switch Vulkan/audio/diagnostics changes are provided as altered-source patches.
- Mesa NVK/EGL/glapi and the matching Rust runtime retain their upstream licenses; upstream Mesa license texts are in `licenses/mesa/`, and Rust MIT/Apache notices and copyright details are in `licenses/`. Mesa's individual source-file notices are available at the fixed upstream revision recorded in `toolchain.lock.json`.

The SDK archive preserves the original packaging receipts and licenses. See `docs/toolchain.md` for sources and revisions. devkitPro, its container image and Microsoft .NET SDK are external dependencies installed from their official distributions.

# 复用整个构建 job

先在调用方的 `publish` job 上传 DLL，然后调用：

```yaml
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-dotnet@v4
        with:
          dotnet-version: 9.0.102
      - run: dotnet publish KuroakiGimmick.csproj -c Release -p:KuroakiSwitch=true -o build/managed
      - uses: actions/upload-artifact@v4
        with:
          name: kg-managed
          path: build/managed/
  switch:
    needs: publish
    uses: BennettNotFound/NroForge/.github/workflows/build-nro.yml@main
    with:
      managed-artifact: kg-managed
      profile: kuroaki-gimmick
      link-assemblies: true
      artifact-name: kg-switch-nro
```

该工作流只取 managed artifact，不复制调用方仓库的 Assets。需要附带完整 Assets 时，使用 README 中的 composite Action，它提供 `assets-directory`。自定义 profile 文件可放入上传的 artifact 根目录，然后把 `profile` 设为 `managed/nroforge.json`。

调用方同一 workflow run 内的 artifacts 由 `actions/download-artifact` 获取。工作流只需 `contents: read`。源码 checkout 默认使用 NroForge `main`；需要冻结构建行为时，应同时固定被调用 workflow 的 commit 和 `nroforge-ref` 输入。

参考：[GitHub composite actions](https://docs.github.com/en/actions/tutorials/create-actions/create-a-composite-action)、[Action metadata](https://docs.github.com/en/actions/reference/workflows-and-actions/metadata-syntax)。

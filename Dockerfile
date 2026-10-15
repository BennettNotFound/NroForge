FROM devkitpro/devkita64:20260219
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 make pkg-config ca-certificates curl xz-utils libicu-dev libssl-dev \
    && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --version 9.0.102 --install-dir /opt/dotnet \
    && rm /tmp/dotnet-install.sh
ENV DOTNET_ROOT=/opt/dotnet
ENV PATH=/opt/dotnet:/opt/devkitpro/devkitA64/bin:/opt/devkitpro/tools/bin:$PATH
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
WORKDIR /workspace
ENTRYPOINT []

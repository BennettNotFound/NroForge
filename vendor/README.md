This directory contains one compressed SDK snapshot (~53 MiB), split into small binary parts for transport. It lets the first Action run work without a separately provisioned release asset. Parts are assembled automatically; each part and the complete archive are SHA-256 checked.

The archive is immutable and verified with `toolchain.lock.json`. Its historical runner/scripts are ignored; maintained runner sources live at the repository root. `scripts/sdk.py` selects and validates only the actual SDK/runtime/compiler inputs.

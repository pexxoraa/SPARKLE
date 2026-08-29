# Build environment

Inspected on 2026-08-29 UTC. These are observed values, not target
requirements.

| Area | Observed state |
|---|---|
| OS | Linux kernel 6.18.35, x86_64, KVM virtual machine |
| CPU | 9 vCPUs, AMD EPYC 9V74 |
| RAM | 15 GiB available, no swap |
| Storage | 63 GiB filesystem; 54 GiB free at inspection |
| Python | 3.12.13; pip 26.2.1; uv 0.11.33 |
| Node.js | 24.19.0; npm/npx 11.9.0 |
| Java | OpenJDK 17.0.20 |
| C compiler | GCC 13.3.0 |
| Git | 2.51.1 |
| Missing toolchains | Clang, Go, Rust |
| Containers | Docker unavailable |
| GPU | No NVIDIA tooling or GPU exposed |
| Audio | No ALSA/PulseAudio devices or utilities exposed |
| Browser in container | No Chromium/Chrome/Firefox executable exposed |
| Editor | VS Code CLI shim exists; editor runtime is not installed |
| Internet | Controlled internet access available to the build environment |
| Connected GitHub | Account `pexxoraa`; existing repositories are accessible with write permission |
| Existing SPARKLE GitHub repo | Private `pexxoraa/SPARKLE`; v0.10 local/remote tree parity and CI were verified before v0.11 work |
| Isolation runtime | Bubblewrap 0.9.0 is installed; actual preflight fails closed because this executor denies nested namespaces |
| Existing workspace files | Current SPARKLE repository resumed; no new project was created |

The build environment also exposed a controlled cloud browser to the build
agent. That is not a runtime dependency or automatically available to SPARKLE.

Installed Python packages relevant to optional document/data features included
Pydantic 2.13.4, PyPDF 6.10.0, python-docx 1.2.0, NumPy 2.3.5, pandas 2.2.3,
scikit-learn 1.8.0, SciPy 1.17.0, Matplotlib 3.10.8, and openpyxl 3.1.5.
Core SPARKLE deliberately has no third-party runtime dependency.

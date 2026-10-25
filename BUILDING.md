# Building

Run from the repository root:

```powershell
uv run --script build.py all
uv run --script build.py cpp --debug
uv run --script build.py python --python-version 3.14
uv run --script build.py all --clean
uv run --script build.py clean
```

You can also use `py build.py ...`; it installs uv and Typer when needed.
Use the uv invocation for cleanup so a project virtual environment's Python
does not keep its own executable locked on Windows.
Rust and the platform's native linker must already be installed.

## Reusing the script

Copy `build.py` into another project's root and edit its **PROJECT
CONFIGURATION** section. No changes to the build logic should be needed:

| Setting | Purpose |
| --- | --- |
| `CARGO_MANIFEST` | Rust workspace or package manifest |
| `RUST_LIBRARIES` | Rust package names and library target names |
| `CPP_LIBRARIES` | Rust FFI packages, library target names, generated header filenames |
| `PYTHON_MANIFESTS` | Cargo manifests for PyO3 extensions built by maturin |
| `OUTPUT_DIRECTORY` | Central artifact directory |
| `DEFAULT_PYTHON_VERSION` | Default wheel interpreter version |
| `DEFAULT_RELEASE` | Default optimization mode |
| `MATURIN_REQUIREMENT` | Automatically installed maturin version requirement |
| `VIRTUAL_ENVIRONMENTS` | Project environments removed by cleanup |
| `EXTRA_CLEAN_DIRECTORIES` | Additional generated folders removed by cleanup |

Paths are relative to the script, and must resolve inside the project. Header
filenames refer to files generated beside the native library by its build script.
Use empty tuples to disable build groups. The `all` target builds every configured
group; an explicitly requested disabled group reports an error.

Multiple libraries are supported. Deliverables are collected under:

```text
dist/release/               # dist/debug/ with --debug
  rust/<package>/
  cpp/<package>/
  python/*.whl
```

Cargo retains intermediates in its own target directory. Cleanup removes Cargo
outputs, the configured artifact directories, and project virtual environments;
shared toolchain and dependency caches remain installed.

The Windows GitHub Actions workflow builds and tests the project, then uploads
`dist/release/`. When copying that workflow to another project, update its
project-specific test commands, artifact name, and any changed output paths.

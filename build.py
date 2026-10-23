# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.16,<1"]
# ///
"""Reusable Rust/C++/PyO3 build driver; edit PROJECT CONFIGURATION below.

Python tools are installed automatically through uv. Rust and the platform's
native linker must already be installed. `cpp` builds Rust FFI libraries.
Cleaning removes Cargo outputs, wheels, and project virtual environments.
"""

import shutil
import json
import subprocess
import sys
import stat
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class NativeLibrary:
    package: str  # Cargo package name (used by -p).
    library: str  # Cargo library target name; may differ from the package name.
    headers: tuple[str, ...] = ()  # Generated headers beside the native library.


# PROJECT CONFIGURATION -- all paths are relative to this script's directory.
# Use empty tuples to disable a language group; multiple libraries are supported.
CARGO_MANIFEST = Path("Cargo.toml")
RUST_LIBRARIES = (NativeLibrary("dice_core", "dice_core"),)
CPP_LIBRARIES = (NativeLibrary("dice_ffi", "dice_ffi", ("dice_ffi.h",)),)
PYTHON_MANIFESTS = (Path("dice_py/Cargo.toml"),)
OUTPUT_DIRECTORY = Path("dist")
DEFAULT_PYTHON_VERSION = "3.14"
DEFAULT_RELEASE = True
MATURIN_REQUIREMENT = "maturin>=1.9,<2"
VIRTUAL_ENVIRONMENTS = (Path(".venv"), Path("dice_py/.venv"), Path(".ci-venv"))
EXTRA_CLEAN_DIRECTORIES = (Path("dice_py/dist"),)
# END PROJECT CONFIGURATION


def project_path(path: Path) -> Path:
    """Keep configured paths inside the project, including resolved links."""
    resolved = (ROOT / path).resolve()
    if resolved == ROOT or not resolved.is_relative_to(ROOT):
        raise RuntimeError(f"Configured path must be inside the project: {path}")
    return resolved


def uv_command() -> list[str]:
    executable = shutil.which("uv")
    if executable:
        return [executable]
    # Installing the Python uv package also works when Scripts is not on PATH.
    import importlib.util

    if importlib.util.find_spec("uv") is None:
        subprocess.run([sys.executable, "-m", "pip", "install", "uv"], check=True)
    return [sys.executable, "-m", "uv"]


def main() -> None:
    # Check before bootstrapping: the parent Python process remains alive while
    # uv runs the script, and can itself lock the venv that cleanup will delete.
    if "--help" not in sys.argv and any(arg in ("clean", "--clean") for arg in sys.argv[1:]):
        environments = tuple(project_path(path) for path in VIRTUAL_ENVIRONMENTS)
        if any(Path(sys.prefix).resolve() == path.resolve() for path in environments):
            raise RuntimeError(
                "Cleanup was started with a project virtual environment's Python. "
                "That process locks python.exe on Windows. Run "
                "`uv run --script build.py clean` (or `uv run --script build.py all --clean`) instead."
            )
    try:
        import typer
    except ImportError:
        # uv reads the inline dependencies above and installs them in isolation.
        command = uv_command() + ["run", "--script", str(Path(__file__).resolve())]
        subprocess.run(command + sys.argv[1:], cwd=ROOT, check=True)
        return

    class Target(str, Enum):
        rust = "rust"
        cpp = "cpp"
        python = "python"
        all = "all"
        clean = "clean"

    def run(command: list[str], *, capture: bool = False) -> str:
        typer.echo(subprocess.list2cmdline(command))
        result = subprocess.run(
            command, cwd=ROOT, text=True,
            stdout=subprocess.PIPE if capture else None,
        )
        if result.returncode and capture and result.stdout:
            typer.echo(result.stdout, err=True)
        result.check_returncode()
        return result.stdout.strip() if capture else ""

    def clean_outputs() -> None:
        directories = tuple(project_path(path) for path in (
            OUTPUT_DIRECTORY, *EXTRA_CLEAN_DIRECTORIES, *VIRTUAL_ENVIRONMENTS
        ))
        # Validate every target before deleting anything. Do not delete the
        # interpreter running this script (Windows locks its executable).
        for directory in directories:
            if directory.resolve() == Path(sys.prefix).resolve():
                raise RuntimeError(
                    "Cannot clean the environment running this script. "
                    "Run `uv run --script build.py clean` from outside the project .venv."
                )
        run(["cargo", "clean", "--manifest-path", str(project_path(CARGO_MANIFEST))])
        def remove_readonly(function, path, exc_info):
            if not isinstance(exc_info[1], PermissionError):
                raise exc_info[1]
            Path(path).chmod(stat.S_IWRITE | stat.S_IREAD)
            function(path)

        for directory in directories:
            if directory.exists():
                typer.echo(f"Removing {directory}")
                try:
                    shutil.rmtree(directory, onerror=remove_readonly)
                except PermissionError as error:
                    raise RuntimeError(
                        f"Cleanup incomplete: cannot remove {error.filename or directory}. "
                        "Close Python processes, REPLs, debuggers, or IDE sessions using this "
                        "environment, then rerun `uv run --script build.py clean`."
                    ) from error

    def build(
        target: Annotated[Target, typer.Argument(help="Artifact to build, or clean.")],
        python_version: Annotated[
            str, typer.Option("--python-version", "--python", help="Python wheel interpreter version.")
        ] = DEFAULT_PYTHON_VERSION,
        release: Annotated[
            bool, typer.Option("--release/--debug", help="Build optimized or debug artifacts.")
        ] = DEFAULT_RELEASE,
        clean: Annotated[
            bool, typer.Option("--clean", help="Remove build outputs and project virtual environments before building.")
        ] = False,
    ) -> None:
        """Build Rust, the C/C++ library and header, Python wheels, or all three."""
        if not shutil.which("cargo"):
            raise typer.BadParameter("cargo is required; install the Rust toolchain first.")
        if target == Target.rust and not RUST_LIBRARIES:
            raise typer.BadParameter("No Rust libraries configured.")
        if target == Target.cpp and not CPP_LIBRARIES:
            raise typer.BadParameter("No C/C++ libraries configured.")
        if target == Target.python and not PYTHON_MANIFESTS:
            raise typer.BadParameter("No Python manifests configured.")
        if target == Target.clean:
            clean_outputs()
            return
        if clean:
            clean_outputs()
        profile = "release" if release else "debug"
        output = project_path(OUTPUT_DIRECTORY) / profile
        libraries = []
        if target in (Target.rust, Target.all):
            libraries.extend((library, "rust") for library in RUST_LIBRARIES)
        if target in (Target.cpp, Target.all):
            libraries.extend((library, "cpp") for library in CPP_LIBRARIES)
        if libraries:
            command = ["cargo", "build", "--manifest-path", str(project_path(CARGO_MANIFEST)),
                       "--message-format=json-render-diagnostics"]
            for package in dict.fromkeys(library.package for library, _ in libraries):
                command.extend(["-p", package])
            if release:
                command.append("--release")
            artifacts = run(command, capture=True)
            for line in artifacts.splitlines():
                message = json.loads(line)
                if message.get("reason") != "compiler-artifact":
                    continue
                name = message["target"]["name"]
                for library, group in libraries:
                    if name != library.library or not set(message["target"]["kind"]) & {
                        "lib", "rlib", "dylib", "cdylib", "staticlib"
                    }:
                        continue
                    destination = output / group / library.package
                    destination.mkdir(parents=True, exist_ok=True)
                    for filename in message["filenames"]:
                        source = Path(filename)
                        shutil.copy2(source, destination / source.name)
                        if source.suffix in (".dll", ".so", ".dylib", ".a", ".lib", ".rlib"):
                            for header_name in library.headers:
                                header = source.parent / header_name
                                shutil.copy2(header, destination / header.name)
        if target in (Target.python, Target.all) and PYTHON_MANIFESTS:
            uv = uv_command()
            run(uv + ["python", "install", python_version])
            interpreter = run(uv + ["python", "find", python_version], capture=True)
            for manifest in PYTHON_MANIFESTS:
                command = uv + [
                    "tool", "run", "--python", interpreter, "--from", MATURIN_REQUIREMENT,
                    "maturin", "build", "--manifest-path", str(project_path(manifest)),
                    "--interpreter", interpreter, "--out", str(output / "python"),
                ]
                if release:
                    command.append("--release")
                run(command)
        typer.echo(f"Build complete. Deliverables: {output}")

    typer.run(build)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        print(f"Command failed (exit {error.returncode}).", file=sys.stderr)
        sys.exit(error.returncode if error.returncode > 0 else 1)
    except (OSError, RuntimeError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        sys.exit(1)

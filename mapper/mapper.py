#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import amulet
from amulet.api.errors import LoaderNoneMatched
from amulet.level.formats.anvil_world import AnvilFormat


@dataclass(frozen=True)
class Config:
    bedrock_world_dir: Path
    java_world_dir: Path  # Converted world location
    output_path: Path
    config_dir: Path
    bluemap_jar: Path = Path("/opt/bluemap/BlueMap-cli.jar")
    render_threads: int = 2
    render_interval: int = 3600
    skip_conversion: bool = False  # Skip if already converted

    # Map configuration
    map_id: str = "bedrock"
    map_name: str = "Bedrock World"
    min_y: int = -64
    max_y: int = 320
    hires_view_distance: int = 5
    lowres_view_distance: int = 7
    ambient_light: float = 1.0


def log(message: str) -> None:
    """Log with timestamp."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def ensure_directories(cfg: Config) -> None:
    """Create necessary directories."""
    cfg.output_path.mkdir(parents=True, exist_ok=True)
    cfg.config_dir.mkdir(parents=True, exist_ok=True)
    (cfg.config_dir / "maps").mkdir(parents=True, exist_ok=True)


def normalize_output_path(path: Path) -> Path:
    """Normalize mapper output path and ensure it ends with 'webroot'."""
    normalized = path.expanduser()
    if not normalized.is_absolute():
        normalized = (Path.cwd() / normalized).resolve()
    if normalized.name != "webroot":
        normalized = normalized / "webroot"
    return normalized


def validate_environment(cfg: Config) -> None:
    """Validate required files and directories exist."""
    if not cfg.bluemap_jar.exists():
        raise FileNotFoundError(
            f"BlueMap JAR not found at {cfg.bluemap_jar}"
        )

    if not cfg.bedrock_world_dir.exists():
        log("ERROR: Bedrock world directory not found"
            f" at {cfg.bedrock_world_dir}")
        log("Available directories in parent:")
        parent = cfg.bedrock_world_dir.parent
        if parent.exists():
            for item in parent.iterdir():
                log(f"  - {item}")
        raise FileNotFoundError(
            f"Bedrock world not found: {cfg.bedrock_world_dir}")


def prepare_bedrock_world_source(bedrock_world_dir: Path) -> tuple[Path, Path | None]:
    """Return a writable world path for Amulet and optional temp dir for cleanup."""
    if os.access(bedrock_world_dir, os.W_OK):
        return bedrock_world_dir, None

    temp_root = Path(tempfile.mkdtemp(prefix="bedrock-world-snapshot-"))
    snapshot_dir = temp_root / bedrock_world_dir.name

    log("Bedrock world is read-only; creating writable snapshot for conversion...")
    shutil.copytree(bedrock_world_dir, snapshot_dir)
    log(f"Snapshot created at: {snapshot_dir}")

    return snapshot_dir, temp_root


def convert_bedrock_to_java(cfg: Config) -> Path:
    """Convert Bedrock world to Java Edition format using Amulet."""

    # Check if conversion already exists and is recent
    if cfg.java_world_dir.exists() and cfg.skip_conversion:
        log(f"Java world already exists at {cfg.java_world_dir}, skipping conversion")
        return cfg.java_world_dir

    log("=" * 60)
    log("Converting Bedrock world to Java Edition format...")
    log(f"Source (Bedrock): {cfg.bedrock_world_dir}")
    log(f"Target (Java): {cfg.java_world_dir}")
    log("=" * 60)

    bedrock_world = None
    java_wrapper = None
    snapshot_root = None
    progress_started = False
    emitted_percent = -1
    try:
        load_world_path, snapshot_root = prepare_bedrock_world_source(
            cfg.bedrock_world_dir
        )

        # Load Bedrock world
        log("Loading Bedrock world...")
        bedrock_world = amulet.load_level(str(load_world_path))
        log(f"Bedrock world loaded: {cfg.bedrock_world_dir.name}")

        log(f"Platform detected: {bedrock_world.level_wrapper.platform}")
        dimension = bedrock_world.dimensions[0]  # Bedrock overworld
        log(f"World bounds: {bedrock_world.bounds(dimension)}")
        log(f"Game version: {bedrock_world.level_wrapper.game_version_string}")

        # Create output directory
        if cfg.java_world_dir.exists():
            log(f"Removing existing Java world at {cfg.java_world_dir}")
            shutil.rmtree(cfg.java_world_dir)

        # Save as Java Edition
        log("Converting and saving as Java Edition format...")
        log("This may take a while depending on world size...")

        # Create Java output wrapper, then save Bedrock world into it.
        java_wrapper = AnvilFormat(str(cfg.java_world_dir))
        java_wrapper.create_and_open(
            platform="java",
            version=bedrock_world.level_wrapper.version,
            overwrite=True,
        )

        # save(wrapper, progress_callback) is the correct Amulet API.
        sys.stdout.write("Progress: ")
        sys.stdout.flush()
        progress_started = True

        def progress_callback(chunk_index: int, chunk_count: int) -> None:
            nonlocal emitted_percent
            if chunk_count <= 0:
                return
            percent = (chunk_index * 100) // chunk_count
            while emitted_percent < percent:
                emitted_percent += 1
                sys.stdout.write(".")
            sys.stdout.flush()

        bedrock_world.save(wrapper=java_wrapper,
                           progress_callback=progress_callback)
        if progress_started:
            sys.stdout.write("\n")
            sys.stdout.flush()
            progress_started = False

        log("Closing worlds...")
        java_wrapper.close()
        java_wrapper = None
        bedrock_world.close()
        bedrock_world = None

        log("Conversion complete!")
        log(f"Java world created at: {cfg.java_world_dir}")
        return cfg.java_world_dir

    except LoaderNoneMatched as e:
        log(f"ERROR: Could not load Bedrock world: {e}")
        log("Make sure the world path points to a valid Bedrock world directory")
        raise
    except Exception as e:
        log(f"ERROR during conversion: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        if progress_started:
            sys.stdout.write("\n")
            sys.stdout.flush()
        if java_wrapper is not None:
            try:
                java_wrapper.close()
            except Exception:
                pass
        if bedrock_world is not None:
            try:
                bedrock_world.close()
            except Exception:
                pass
        if snapshot_root is not None:
            try:
                shutil.rmtree(snapshot_root)
            except Exception:
                pass


def generate_bluemap_config(cfg: Config) -> None:
    """Generate BlueMap configuration files if they don't exist."""
    core_conf = cfg.config_dir / "core.conf"
    webserver_conf = cfg.config_dir / "webserver.conf"
    webapp_conf = cfg.config_dir / "webapp.conf"
    file_storage_conf = cfg.config_dir / "storages" / "file.conf"

    # First time setup - let BlueMap generate default configs
    if not core_conf.exists():
        log("Generating default BlueMap configuration...")
        try:
            subprocess.run(
                [
                    "java", "-jar", str(cfg.bluemap_jar),
                    "-c", str(cfg.config_dir)
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            log("Default configuration generated")
        except subprocess.TimeoutExpired:
            log("Config generation timed out (this is expected if webserver started)")
        except subprocess.CalledProcessError as e:
            log(
                f"Config generation returned exit code {e.returncode} (may be OK)")

    # Update core.conf settings
    if core_conf.exists():
        log("Updating core.conf settings...")
        content = core_conf.read_text(encoding="utf-8")

        # Update accept-download to true
        content = content.replace(
            "accept-download: false",
            "accept-download: true"
        )

        # Update render thread count if specified
        import re
        content = re.sub(
            r'render-thread-count:\s*\d+',
            f'render-thread-count: {cfg.render_threads}',
            content
        )

        core_conf.write_text(content, encoding="utf-8")
        log("core.conf updated")

    # Update webserver.conf
    if webserver_conf.exists():
        log("Updating webserver.conf...")
        content = webserver_conf.read_text(encoding="utf-8")

        # Update webroot path (supports quoted or unquoted existing values)
        webroot_line = f'webroot: "{cfg.output_path}"'
        updated, count = re.subn(
            r'(?m)^\s*webroot:\s*(?:"[^"]*"|\S+)\s*$',
            webroot_line,
            content,
        )
        if count == 0:
            if not updated.endswith("\n"):
                updated += "\n"
            updated += webroot_line + "\n"
        content = updated

        webserver_conf.write_text(content, encoding="utf-8")
        log(f"webserver.conf updated with webroot: {cfg.output_path}")

    # Update webapp.conf
    if webapp_conf.exists():
        log("Updating webapp.conf...")
        content = webapp_conf.read_text(encoding="utf-8")

        webroot_line = f'webroot: "{cfg.output_path}"'
        updated, count = re.subn(
            r'(?m)^\s*webroot:\s*(?:"[^"]*"|\S+)\s*$',
            webroot_line,
            content,
        )
        if count == 0:
            if not updated.endswith("\n"):
                updated += "\n"
            updated += webroot_line + "\n"
        content = updated

        webapp_conf.write_text(content, encoding="utf-8")
        log(f"webapp.conf updated with webroot: {cfg.output_path}")

    # Update storages/file.conf
    if file_storage_conf.exists():
        log("Updating storages/file.conf...")
        content = file_storage_conf.read_text(encoding="utf-8")

        storage_root = cfg.output_path / "maps"
        root_line = f'root: "{storage_root}"'
        updated, count = re.subn(
            r'(?m)^\s*root:\s*(?:"[^"]*"|\S+)\s*$',
            root_line,
            content,
        )
        if count == 0:
            if not updated.endswith("\n"):
                updated += "\n"
            updated += root_line + "\n"
        content = updated

        file_storage_conf.write_text(content, encoding="utf-8")
        log(f"storages/file.conf updated with root: {storage_root}")


def write_map_config(cfg: Config) -> None:
    """Write/update map-specific configuration for converted Java world."""
    map_conf_path = cfg.config_dir / "maps" / f"{cfg.map_id}.conf"

    # Check if a sample map config exists that we can use as template
    maps_dir = cfg.config_dir / "maps"
    sample_configs = list(maps_dir.glob("*.conf")) if maps_dir.exists() else []

    if sample_configs and not map_conf_path.exists():
        # Use existing sample as template
        log(f"Using {sample_configs[0].name} as template for map config")
        sample_content = sample_configs[0].read_text(encoding="utf-8")

        # Update key fields - use Java world path
        import re
        sample_content = re.sub(
            r'id:\s*"[^"]*"', f'id: "{cfg.map_id}"', sample_content)
        sample_content = re.sub(
            r'name:\s*"[^"]*"', f'name: "{cfg.map_name}"', sample_content)
        sample_content = re.sub(
            r'world:\s*"[^"]*"', f'world: "{cfg.java_world_dir}"', sample_content)
        sample_content, count = re.subn(
            r'(?m)^\s*ambient-light:\s*[0-9]*\.?[0-9]+\s*$',
            f'ambient-light: {cfg.ambient_light}',
            sample_content,
        )
        if count == 0:
            if not sample_content.endswith("\n"):
                sample_content += "\n"
            sample_content += f"ambient-light: {cfg.ambient_light}\n"

        map_conf_path.write_text(sample_content, encoding="utf-8")
        log(f"Map configuration written to {map_conf_path} (from template)")
        return

    config_content = f'''##                          ##
##         BlueMap          ##
##        Map-Config        ##
##                          ##

# The id of this map
id: "{cfg.map_id}"

# The display name of this map  
name: "{cfg.map_name}"

# The world/save-folder of this map (converted from Bedrock)
world: "{cfg.java_world_dir}"

# The dimension of the world
dimension: "minecraft:overworld"

# The position of this map in the web-application
sorting: 0

# The start position for this map
# (the position where the players camera is when opening the map)
start-pos: {{x: 0, z: 0}}

# The color of the sky
sky-color: "#7dabff"

# Defines the ambient light
ambient-light: {cfg.ambient_light}

# Defines the view-distance for hires tiles
hires-view-distance: {cfg.hires_view_distance}

# Defines the view-distance for lowres tiles
lowres-view-distance: {cfg.lowres_view_distance}

# Whether edges should be rendered
render-edges: true

# Whether the highres layer should be saved
save-hires-layer: true

# Remove caves below this Y-level (Bedrock typically uses -64)
remove-caves-below-y: {cfg.min_y}
'''

    map_conf_path.write_text(config_content, encoding="utf-8")
    log(f"Map configuration written to {map_conf_path}")


def render_map(cfg: Config) -> None:
    """Run BlueMap rendering."""
    log("Starting BlueMap render...")

    cmd = [
        "java", "-jar", str(cfg.bluemap_jar),
        "-c", str(cfg.config_dir),
        "-r",  # render
        "-f",  # force render
    ]

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )

        # Log output
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                log(f"  {line}")

        log("Render complete!")

    except subprocess.CalledProcessError as e:
        log(f"ERROR: BlueMap render failed with exit code {e.returncode}")
        if e.stdout:
            log("STDOUT:")
            for line in e.stdout.strip().split('\n'):
                log(f"  {line}")
        if e.stderr:
            log("STDERR:")
            for line in e.stderr.strip().split('\n'):
                log(f"  {line}")
        raise


def start_bluemap(cfg: Config) -> None:
    """Start BlueMap with rendering and built-in webserver."""
    log("Starting BlueMap with integrated webserver...")

    cmd = [
        "java", "-jar", str(cfg.bluemap_jar),
        "-c", str(cfg.config_dir),
        "-r",  # render once
        "-w",  # start webserver
    ]

    log(f"Command: {' '.join(str(c) for c in cmd)}")
    log("BlueMap will render the map and then start the webserver")
    log("Press Ctrl+C to stop")

    try:
        # Run in foreground - this will block until interrupted
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        log("Received interrupt, shutting down...")
    except subprocess.CalledProcessError as e:
        log(f"ERROR: BlueMap failed with exit code {e.returncode}")
        raise


def periodic_render_loop(cfg: Config) -> None:
    """Keep running and re-render periodically."""
    log(f"Entering periodic render loop (interval: {cfg.render_interval}s)")
    log("Web interface available at http://localhost:8100")

    while True:
        time.sleep(cfg.render_interval)
        log("Starting periodic re-render...")
        try:
            render_map(cfg)
        except Exception as e:
            log(f"ERROR during periodic render: {e}")
            log("Will retry at next interval")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert Bedrock worlds to Java format and render with BlueMap's built-in web server."
    )
    parser.add_argument(
        "--bedrock-world-dir",
        default=os.getenv("BEDROCK_WORLD_DIR",
                          "/bedrock/worlds/world"),
        help="Path to Bedrock world directory",
    )
    parser.add_argument(
        "--java-world-dir",
        default=os.getenv("JAVA_WORLD_DIR", None),
        help="Path where converted Java world will be stored (default: output-path + '/java_' + bedrock-world-dir name)",
    )
    parser.add_argument(
        "--output-path",
        default=os.getenv("OUTPUT_PATH", "mapper-output/webroot"),
        help="Directory where rendered map files are written",
    )
    parser.add_argument(
        "--config-dir",
        default=os.getenv("CONFIG_DIR", "/opt/bluemap/config"),
        help="BlueMap configuration directory",
    )
    parser.add_argument(
        "--render-threads",
        type=int,
        default=int(os.getenv("BLUEMAP_RENDER_THREADS", "2")),
        help="Number of threads for rendering (0 = all cores)",
    )
    parser.add_argument(
        "--render-interval",
        type=int,
        default=int(os.getenv("RENDER_INTERVAL", "3600")),
        help="Seconds between automatic re-renders",
    )
    parser.add_argument(
        "--ambient-light",
        type=float,
        default=float(os.getenv("BLUEMAP_AMBIENT_LIGHT", "1.0")),
        help="Ambient light for generated BlueMap map config",
    )
    parser.add_argument(
        "--bluemap-jar",
        default=os.getenv("BLUEMAP_JAR", "/opt/bluemap/BlueMap-cli.jar"),
        help="Path to BlueMap CLI JAR file",
    )
    parser.add_argument(
        "--skip-conversion",
        action="store_true",
        default=os.getenv("SKIP_CONVERSION", "false").lower() == "true",
        help="Skip Bedrock to Java conversion if already done",
    )

    args = parser.parse_args(argv)

    bedrock_world_dir = Path(args.bedrock_world_dir)
    output_path = normalize_output_path(Path(args.output_path))
    java_world_dir = Path(args.java_world_dir) if args.java_world_dir else (
        output_path.parent / f"java_{bedrock_world_dir.name}")

    cfg = Config(
        bedrock_world_dir=bedrock_world_dir,
        java_world_dir=java_world_dir,
        output_path=output_path,
        config_dir=Path(args.config_dir),
        bluemap_jar=Path(args.bluemap_jar),
        render_threads=args.render_threads,
        render_interval=args.render_interval,
        skip_conversion=args.skip_conversion,
        ambient_light=args.ambient_light,
    )

    log("=" * 60)
    log("BlueMap Mapper for Minecraft Bedrock")
    log("=" * 60)
    log(f"Bedrock world: {cfg.bedrock_world_dir}")
    log(f"Java world (converted): {cfg.java_world_dir}")
    log(f"Output path: {cfg.output_path}")
    log(f"Config dir: {cfg.config_dir}")
    log(f"BlueMap JAR: {cfg.bluemap_jar}")
    log(f"Render threads: {cfg.render_threads}")
    log(f"Ambient light: {cfg.ambient_light}")
    log(f"Skip conversion: {cfg.skip_conversion}")
    log("=" * 60)

    # Setup
    ensure_directories(cfg)
    validate_environment(cfg)

    # Convert Bedrock to Java format
    convert_bedrock_to_java(cfg)

    # Configure BlueMap with converted world
    generate_bluemap_config(cfg)
    write_map_config(cfg)

    # Start BlueMap with rendering and webserver
    log("Starting BlueMap render and webserver...")
    start_bluemap(cfg)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        log("Received interrupt signal, shutting down...")
        raise SystemExit(0)
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise SystemExit(1)

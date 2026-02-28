#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import amulet
from amulet.api.errors import LoaderNoneMatched


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


def log(message: str) -> None:
    """Log with timestamp."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def ensure_directories(cfg: Config) -> None:
    """Create necessary directories."""
    cfg.output_path.mkdir(parents=True, exist_ok=True)
    cfg.config_dir.mkdir(parents=True, exist_ok=True)
    (cfg.config_dir / "maps").mkdir(parents=True, exist_ok=True)


def validate_environment(cfg: Config) -> None:
    """Validate required files and directories exist."""
    if not cfg.bluemap_jar.exists():
        raise FileNotFoundError(
            f"BlueMap JAR not found at {cfg.bluemap_jar}"
        )

    if not cfg.bedrock_world_dir.exists():
        log(
            f"ERROR: Bedrock world directory not found at {cfg.bedrock_world_dir}")
        log("Available directories in parent:")
        parent = cfg.bedrock_world_dir.parent
        if parent.exists():
            for item in parent.iterdir():
                log(f"  - {item}")
        raise FileNotFoundError(
            f"Bedrock world not found: {cfg.bedrock_world_dir}")


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

    try:
        # Load Bedrock world
        log("Loading Bedrock world...")
        bedrock_world = amulet.load_level(str(cfg.bedrock_world_dir))
        log(f"Bedrock world loaded: {bedrock_world.level_name}")

        # Get the overworld dimension
        dimension = bedrock_world.dimensions[0]  # Bedrock overworld
        log(f"World bounds: {bedrock_world.bounds(dimension)}")

        # Create output directory
        if cfg.java_world_dir.exists():
            log(f"Removing existing Java world at {cfg.java_world_dir}")
            shutil.rmtree(cfg.java_world_dir)

        cfg.java_world_dir.mkdir(parents=True, exist_ok=True)

        # Save as Java Edition
        log("Converting and saving as Java Edition format...")
        log("This may take a while depending on world size...")

        # Use Amulet's save_as method to convert
        bedrock_world.save_as(
            str(cfg.java_world_dir),
            "java",  # Target format
            bedrock_world.game_version_string,  # Keep same game version
        )

        log("Closing worlds...")
        bedrock_world.close()

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


def generate_bluemap_config(cfg: Config) -> None:
    """Generate BlueMap configuration files if they don't exist."""
    core_conf = cfg.config_dir / "core.conf"
    webserver_conf = cfg.config_dir / "webserver.conf"

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
            "accept-download: false", "accept-download: true")

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

        # Update webroot path
        content = re.sub(
            r'webroot:\s*"[^"]*"',
            f'webroot: "{cfg.output_path}"',
            content
        )

        webserver_conf.write_text(content, encoding="utf-8")
        log(f"webserver.conf updated with webroot: {cfg.output_path}")


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
ambient-light: 0.1

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
                          "/bedrock/worlds/Bedrock level"),
        help="Path to Bedrock world directory",
    )
    parser.add_argument(
        "--java-world-dir",
        default=os.getenv("JAVA_WORLD_DIR", None),
        help="Path where converted Java world will be stored (default: output-path + '/java_' + bedrock-world-dir name)",
    )
    parser.add_argument(
        "--output-path",
        default=os.getenv("OUTPUT_PATH", "/webroot"),
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
    java_world_dir = Path(args.java_world_dir) if args.java_world_dir else (
        Path(args.output_path).parent / f"java_{bedrock_world_dir.name}")

    cfg = Config(
        bedrock_world_dir=bedrock_world_dir,
        java_world_dir=java_world_dir,
        output_path=Path(args.output_path),
        config_dir=Path(args.config_dir),
        bluemap_jar=Path(args.bluemap_jar),
        render_threads=args.render_threads,
        render_interval=args.render_interval,
        skip_conversion=args.skip_conversion,
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

# mc-bedrock

This is a solution for running a Minecraft Bedrock server in Docker with optional web-based 3D map rendering via BlueMap.

## Architecture

The system consists of two Docker services orchestrated via docker-compose:

```
┌─────────────────┐
│ Bedrock Server  │
│  (mc-bedrock)   │
│  Port: 19132    │
└────────┬────────┘
         │ (shared volume, read-only)
         ▼
┌─────────────────┐
│ BlueMap Mapper  │
│   (mc-map)      │
│  Port: 8080     │
│                 │
│ 1. Reads world  │
│ 2. Renders map  │
│ 3. Serves via   │
│    nginx        │
└────────┬────────┘
         │
         ▼
    Web Browser
    (3D Interactive Map)
```

## Quick Start

### Starting the Server

```bash
# Start both Bedrock server and mapper
./manage.sh start
```

### Accessing Services

- **Minecraft Server:** Connect to `<server-ip>:19132` from Bedrock client
- **Web Map:** Open `http://<server-ip>:8080` in your browser

## Installation

### Docker Compose (Recommended)

The server runs via Docker Compose and can be managed with the included scripts:

```bash
# Start
./manage.sh start

# Stop (with safe world save)
./manage.sh stop

# Restart
./manage.sh restart

# Check status
./manage.sh status
```

### Systemd Service (Optional)

For production deployments, you can install as a systemd service:

#### 1. Install the systemd service

```bash
sudo cp mc-bedrock.service /etc/systemd/system/
sudo systemctl daemon-reload
```

#### 2. Enable and start

```bash
# Enable auto-start on boot
sudo systemctl enable mc-bedrock.service

# Start the service
sudo systemctl start mc-bedrock
```

#### 3. Manage via systemctl

```bash
# Start
sudo systemctl start mc-bedrock

# Stop (with safe world save)
sudo systemctl stop mc-bedrock

# Restart
sudo systemctl restart mc-bedrock

# Check status
sudo systemctl status mc-bedrock

# View logs
sudo journalctl -u mc-bedrock -f
```

## Configuration

### Bedrock Server Configuration

Edit server properties:
```bash
vi data/server.properties
```

Common settings in `docker-compose.yml`:
- `SERVER_NAME` - Server name visible to players
- `GAMEMODE` - survival, creative, adventure
- `DIFFICULTY` - peaceful, easy, normal, hard
- `MAX_PLAYERS` - Maximum number of players
- `ONLINE_MODE` - Enable Xbox Live authentication
- `ALLOW_CHEATS` - Enable command usage

After changing configuration, restart:
```bash
./manage.sh restart
```

### Management Script Configuration

The `manage.sh` script supports environment variables for shutdown timeouts:

- `SAVE_HOLD_WAIT` - Time (in seconds) to wait after save hold command (default: 2)
- `SHUTDOWN_GRACE_PERIOD` - Time (in seconds) to wait before forcing shutdown (default: 3)

Example with custom timeouts:
```bash
SAVE_HOLD_WAIT=5 SHUTDOWN_GRACE_PERIOD=10 ./manage.sh stop
```

The stop/restart commands perform a safe shutdown:
1. Send `save hold` command to freeze and save the world
2. Wait for save to complete
3. Send `save resume` command
4. Wait for graceful shutdown
5. Stop the Docker container

## Utilities

### Management Scripts

- `./manage.sh` - Unified service management (start/stop/restart/status)
- `./console.sh` - Attach to the server console (Ctrl+P, Ctrl+Q to detach)
- `./tail.sh` - View server logs
- `./check_port.sh` - Check if the server port is accessible
- `./firewall.sh` - Manage UFW firewall rules

### Firewall Management

The unified firewall script manages UFW rules for the Minecraft server:

```bash
# Open the Minecraft port
./firewall.sh on

# Close the Minecraft port
./firewall.sh off

# Check firewall status for Minecraft port
./firewall.sh status

# Use custom port
MINECRAFT_PORT=25565 ./firewall.sh on
```

Available commands: `on` (or `allow`, `enable`), `off` (or `deny`, `disable`), `status`

---

## BlueMap Web Mapper

The optional BlueMap service renders interactive 3D web maps of your Bedrock world.

### Features

- ✅ **Native Bedrock support** - Renders Bedrock worlds directly
- ✅ **Interactive 3D visualization** - WebGL-based map viewer
- ✅ **Automatic updates** - Periodic re-rendering
- ✅ **Actively maintained** - Regular updates and bug fixes

### Enabling the Mapper

The mapper service is defined in `docker-compose.yml`. Start both services:

```bash
./manage.sh start
```

Access the web map at: `http://localhost:8080`

The initial render may take several minutes depending on world size.

### Mapper Configuration

Edit `docker-compose.yml` mapper service environment variables:

#### `BEDROCK_WORLD_DIR`
Path to the Bedrock world directory (inside the container).
- **Default:** `/bedrock/worlds/Bedrock level`
- Common values:
  - `/bedrock/worlds/Bedrock level` (default world name)
  - `/bedrock/worlds/world` (if you renamed it)

#### `BLUEMAP_RENDER_THREADS`
Number of CPU threads to use for rendering.
- **Default:** `2`
- Set to `0` to use all available cores
- Higher = faster renders, but more CPU usage

#### `RENDER_INTERVAL`
How often to automatically re-render the map (in seconds).
- **Default:** `3600` (1 hour)
- Set to `86400` for daily renders
- Set to `300` for 5-minute updates (CPU intensive!)

#### `OUTPUT_PATH`
Where rendered map files are written.
- **Default:** `/webroot`
- Usually don't need to change this

#### `CONFIG_DIR`
BlueMap configuration directory.
- **Default:** `/opt/bluemap/config`
- Persisted in `./mapper-config` volume

### Advanced Mapper Configuration

BlueMap configuration is persisted in `./mapper-config/`. You can customize:

```bash
# Edit core settings
vi mapper-config/core.conf

# Edit map-specific settings
vi mapper-config/maps/bedrock.conf
```

After editing, restart the services:
```bash
./manage.sh restart
```

### Manual Render Trigger

To manually trigger a map render without waiting for the interval:

```bash
# Restart just the mapper service
docker compose restart mapper

# Or exec into the container and run BlueMap manually
docker exec -it mc-map bash
java -jar /opt/bluemap/BlueMap-cli.jar -c /opt/bluemap/config -w /webroot -r
```

### Mapper Troubleshooting

#### Map shows "No world found"

Check the world path:
```bash
# List available worlds
docker exec mc-map ls -la /bedrock/worlds/

# Update BEDROCK_WORLD_DIR in docker-compose.yml to match
```

#### Render is very slow

- Reduce `BLUEMAP_RENDER_THREADS` to avoid overloading CPU
- Increase `RENDER_INTERVAL` to render less frequently
- Adjust render distance in `mapper-config/maps/bedrock.conf`:
  ```
  hires-view-distance: 3
  lowres-view-distance: 5
  ```

#### Map tiles not updating

- Check logs: `docker logs mc-map -f`
- Verify the mapper can read the world: `docker exec mc-map ls -la "$BEDROCK_WORLD_DIR"`
- Ensure the Bedrock server volume is mounted correctly

#### High memory usage

BlueMap needs adequate RAM for rendering. Minimum 2GB recommended, 4GB+ for large worlds.

Add memory limits to docker-compose.yml:
```yaml
mapper:
  # ... existing config ...
  mem_limit: 4g
  mem_reservation: 2g
```

#### Python debugging

The mapper uses Python for better error reporting. To debug:

```bash
# View full logs with tracebacks
docker logs mc-map -f

# Exec into container for interactive debugging
docker exec -it mc-map bash
python /usr/local/bin/entrypoint.py --help
```

### Mapper Logs

```bash
# Follow mapper logs
docker logs mc-map -f

# View last 50 lines
docker logs mc-map --tail 50
```

### Stopping the Mapper

```bash
# Stop everything (including Bedrock server)
./manage.sh stop

# Or stop just the mapper (keep Bedrock server running)
docker compose stop mapper
```

### Upgrading BlueMap

To use a newer version of BlueMap:

1. Edit `mapper/Dockerfile` and update `BLUEMAP_VERSION`
2. Stop services: `./manage.sh stop`
3. Rebuild: `docker compose build mapper`
4. Start services: `./manage.sh start`

### BlueMap Resources

- [BlueMap Documentation](https://bluemap.bluecolored.de/wiki/)
- [BlueMap GitHub](https://github.com/BlueMap-Minecraft/BlueMap)
- [BlueMap Discord](https://bluecolo.red/map-discord)

---

## Uninstalling the Service

1. Stop and disable the service:
```bash
sudo systemctl stop mc-bedrock
sudo systemctl disable mc-bedrock
```

2. Remove the service file:
```bash
sudo rm /etc/systemd/system/mc-bedrock.service
```

3. Reload systemd:
```bash
sudo systemctl daemon-reload
```

## Troubleshooting

### Bedrock Server Issues

#### Service won't start
- Check Docker is running: `sudo systemctl status docker`
- Check service logs: `sudo journalctl -u mc-bedrock -n 50` (systemd) or `docker logs mc-bedrock`
- Verify permissions on manage.sh: `ls -l manage.sh`

#### Server keeps restarting
- Check container logs: `docker logs mc-bedrock`
- Verify docker-compose.yml configuration
- Check disk space: `df -h`

#### Can't connect to server
- Verify port is open: `./check_port.sh`
- Check firewall: `./firewall.sh status` or `sudo ufw status`
- Verify server is running: `docker ps` or `./manage.sh status`
- Ensure port 19132/udp is accessible from client network

### View Server Logs

```bash
# Docker logs
docker logs -f mc-bedrock

# Systemd logs (if using systemd service)
sudo journalctl -u mc-bedrock -f

# Using utility script
./tail.sh
```

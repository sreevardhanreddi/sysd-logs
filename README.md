# Systemd Services Monitor

A modern web application for monitoring and viewing systemd services and journal logs. Built with FastAPI, HTMX, and Tailwind CSS, featuring a beautiful dark mode interface.

## Features

### 🔧 Services Dashboard

- **Real-time Service Monitoring**: View all systemd services with their current status

### 📋 Journal Logs Viewer

- **Service-specific Logs**: View logs for individual services or all services

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: HTMX + Tailwind CSS
- **Systemd Integration**: pystemd, systemd-python
- **Containerization**: Docker & Docker Compose
- **Logging**: Loguru

## Prerequisites

- Docker
- Docker Compose
- Linux system with systemd

## Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd sysd-srv
   ```

2. **Build and run with Docker Compose:**

   For development:

   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

   For production:

   ```bash
   docker-compose -f docker-compose.prod.yml up --build
   ```

3. **Access the application:**
   - Development: http://localhost:8011/ui
   - Production: http://localhost:8000/ui

## API Endpoints

### Services

- `GET /` - API root
- `GET /ui` - Services dashboard UI
- `GET /services/` - JSON API endpoint for all systemd services

### Logs

- `GET /ui/logs` - Logs viewer UI
- `GET /logs/` - JSON API endpoint for journal logs
  - Query Parameters:
    - `limit` (optional, default: 100): Number of log entries to return
    - `service` (optional): Filter logs by specific service unit

## Usage Examples

### View Services Dashboard

Navigate to `http://localhost:8011/ui` to see the services dashboard.

### View System Logs

Navigate to `http://localhost:8011/ui/logs` to view systemd journal logs.

### API Usage

**Get all services:**

```bash
curl http://localhost:8011/services/
```

**Get all logs (last 100 entries):**

```bash
curl http://localhost:8011/logs/
```

**Get logs for a specific service:**

```bash
curl http://localhost:8011/logs/?service=nginx.service&limit=50
```

**Get more log entries:**

```bash
curl http://localhost:8011/logs/?limit=500
```

## Docker Configuration

### Required Mounts

The application requires access to systemd on the host system:

- `/run/systemd` - Systemd runtime directory
- `/var/run/dbus/system_bus_socket` - D-Bus system socket
- `/sys/fs/cgroup` - Cgroup filesystem

### Required Permissions

- `privileged: true` - Required for systemd access
- `pid: "host"` - Access to host PID namespace

### Environment Variables

- `DBUS_SYSTEM_BUS_ADDRESS` - D-Bus socket path (automatically configured)

## Development

### Project Structure

```
sysd-srv/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── templates/             # HTML templates
│   ├── base.html         # Base template
│   ├── index.html        # Services dashboard
│   └── logs.html         # Logs viewer
├── Dockerfile.dev        # Development Dockerfile
├── Dockerfile.prod       # Production Dockerfile
├── docker-compose.dev.yml
├── docker-compose.prod.yml
└── README.md
```

### Running Locally (without Docker)

**Note**: This requires systemd and proper permissions to access the system D-Bus.

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**

   ```bash
   python main.py
   ```

3. **Access at:** http://localhost:8000

## Features in Detail

### Services Dashboard

- Lists all systemd service units
- Displays: unit name, description, load state, active state, and sub-state
- Statistics cards showing total, active, inactive, and failed services
- Real-time search and filtering
- One-click refresh

### Logs Viewer

- Fetches logs from systemd journal using D-Bus API
- Fallback to `journalctl` command if D-Bus fails
- Displays timestamp, priority, unit name, PID, and message
- Color-coded priority levels for quick issue identification
- Service-specific filtering via dropdown
- Statistical breakdown by priority level
- Auto-scroll to latest entries

## Troubleshooting

### Cannot access systemd services

Ensure the container has:

- Privileged mode enabled
- Correct volume mounts for systemd and D-Bus
- Host PID namespace access

### Logs not showing

Check that:

- Journal is accessible: `journalctl --no-pager | head`
- D-Bus socket is mounted correctly
- Container has proper permissions

## Security Considerations

⚠️ **Important**: This application requires privileged access to the host system's systemd. Only deploy in trusted environments and secure the application appropriately.

- Use authentication/authorization for production deployments
- Restrict network access to the application
- Run behind a reverse proxy (nginx, Traefik, etc.)
- Use HTTPS for production
- Consider implementing rate limiting

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

[Add your license here]

## Author

[Add your information here]

# Systemd Services Monitor

A modern web application for monitoring and viewing systemd services and journal logs. Built with FastAPI, HTMX, and Tailwind CSS, featuring a beautiful dark mode interface.

## Features

### 🔒 Security

- **HTTP Basic Authentication**: Secure access with username/password protection
- **Environment-based Configuration**: Credentials stored in `.env` file

### 🔧 Services Dashboard

- **Real-time Service Monitoring**: View all systemd services with their current status
- **Service Control**: Start, stop, and restart services directly from the dashboard
- **Search and Filter**: Find services quickly with real-time filtering

### 📋 Journal Logs Viewer

- **Service-specific Logs**: View logs for individual services
- **Live Log Streaming**: Real-time log updates using Server-Sent Events
- **Advanced Filtering**: Filter by priority level and search text

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

2. **Configure authentication:**

   Create a `.env` file with your credentials (or copy from `.env.example`):

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set your username and password:

   ```env
   AUTH_USERNAME=admin
   AUTH_PASSWORD=your_secure_password_here
   ```

   ⚠️ **Security**: Make sure to change the default credentials before deploying!

3. **Build and run with Docker Compose:**

   For development:

   ```bash
   docker-compose -f docker-compose.dev.yml up --build
   ```

   For production:

   ```bash
   docker-compose -f docker-compose.prod.yml up --build
   ```

4. **Access the application:**
   - Development: http://localhost:8011/
   - Production: http://localhost:8000/
   
   You will be prompted for HTTP Basic Authentication credentials.

## API Endpoints

🔒 **Note**: All endpoints except `/health` require HTTP Basic Authentication.

### Services

- `GET /` - Services dashboard UI
- `GET /api/services/` - List all systemd services (JSON)
- `POST /api/services/{service_name}/start` - Start a service
- `POST /api/services/{service_name}/stop` - Stop a service
- `POST /api/services/{service_name}/restart` - Restart a service

### Logs

- `GET /logs` - Logs viewer UI
- `GET /api/logs/` - Get journal logs (JSON)
  - Query Parameters:
    - `service` (required): Service unit name
    - `limit` (optional, default: 100): Number of log entries to return
- `GET /api/logs/stream` - Stream logs in real-time (SSE)
  - Query Parameters:
    - `service` (required): Service unit name

### Health

- `GET /health` - Health check endpoint (no authentication required)

## Usage Examples

### View Services Dashboard

Navigate to `http://localhost:8011/` and authenticate with your credentials to see the services dashboard.

### View System Logs

Navigate to `http://localhost:8011/logs` to view systemd journal logs.

### API Usage

All API requests (except `/health`) require HTTP Basic Authentication.

**Get all services:**

```bash
curl -u admin:your_password http://localhost:8011/api/services/
```

**Start a service:**

```bash
curl -X POST -u admin:your_password http://localhost:8011/api/services/nginx.service/start
```

**Stop a service:**

```bash
curl -X POST -u admin:your_password http://localhost:8011/api/services/nginx.service/stop
```

**Restart a service:**

```bash
curl -X POST -u admin:your_password http://localhost:8011/api/services/nginx.service/restart
```

**Get logs for a specific service:**

```bash
curl -u admin:your_password "http://localhost:8011/api/logs/?service=nginx.service&limit=50"
```

**Stream logs in real-time:**

```bash
curl -u admin:your_password "http://localhost:8011/api/logs/stream?service=nginx.service"
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

- `AUTH_USERNAME` - HTTP Basic Auth username (required, set in `.env`)
- `AUTH_PASSWORD` - HTTP Basic Auth password (required, set in `.env`)
- `DBUS_SYSTEM_BUS_ADDRESS` - D-Bus socket path (automatically configured)

## Development

### Project Structure

```
sysd-srv/
├── main.py                     # FastAPI application
├── requirements.txt            # Python dependencies
├── middlewares/               # Middleware modules
│   ├── __init__.py           # Package initialization
│   └── auth.py               # Authentication middleware
├── templates/                 # HTML templates
│   ├── base.html             # Base template
│   ├── index.html            # Services dashboard
│   └── logs.html             # Logs viewer
├── .env                       # Environment variables (not in git)
├── .env.example              # Environment template
├── Dockerfile.dev            # Development Dockerfile
├── Dockerfile.prod           # Production Dockerfile
├── docker-compose.dev.yml    # Dev compose config
├── docker-compose.prod.yml   # Prod compose config
└── README.md                 # Documentation
```

### Running Locally (without Docker)

**Note**: This requires systemd and proper permissions to access the system D-Bus.

1. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

2. **Create `.env` file:**

   ```bash
   cp .env.example .env
   # Edit .env and set your credentials
   ```

3. **Run the application:**

   ```bash
   python main.py
   ```

4. **Access at:** http://localhost:8000 (use the credentials from your `.env` file)

## Features in Detail

### Services Dashboard

- Lists all systemd service units
- Displays: unit name, description, load state, active state, and sub-state
- Statistics cards showing total, active, inactive, and failed services
- Real-time search and filtering
- Service control buttons (start, stop, restart)
- One-click refresh
- Success/error notifications for service operations

### Logs Viewer

- Fetches logs from systemd journal using D-Bus API
- Fallback to `journalctl` command if D-Bus fails
- Real-time log streaming with Server-Sent Events
- Displays timestamp, priority, unit name, PID, and message
- Color-coded priority levels for quick issue identification
- Service-specific filtering via dropdown
- Text search and priority filtering
- Statistical breakdown by priority level
- Auto-scroll to latest entries
- Configurable log limit (50, 100, 200, 500, 1000)

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

### Built-in Security Features

- ✅ HTTP Basic Authentication enabled by default
- ✅ Credentials stored in environment variables
- ✅ Timing-attack resistant password comparison
- ✅ Authentication logging for audit trails

### Additional Recommendations

- **Change default credentials** in `.env` file before deployment
- **Use strong passwords** (20+ characters, mixed case, numbers, symbols)
- **Restrict network access** to the application
- **Run behind a reverse proxy** (nginx, Traefik, etc.) with HTTPS
- **Use HTTPS for production** deployments
- **Keep `.env` file secure** and never commit it to version control
- **Consider implementing rate limiting** at the reverse proxy level
- **Regular security audits** and updates
- **Monitor authentication logs** for suspicious activity

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License


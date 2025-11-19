import uvicorn
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from systemd import journal
from pystemd.systemd1 import Manager
from pystemd import daemon
import subprocess
import json
from loguru import logger
import sys


app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}


@app.get("/ui", response_class=HTMLResponse)
async def services_ui(request: Request):
    """
    Render the HTMX + Tailwind UI for systemd services
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/ui/logs", response_class=HTMLResponse)
async def logs_ui(request: Request):
    """
    Render the HTMX + Tailwind UI for systemd journal logs
    """
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/logs/")
def get_journal_logs(limit: int = 100, service: str = None):
    """
    Get the last N entries from systemd journal
    Optionally filter by a specific service unit
    """
    logger.info(
        f"Fetching last {limit} journal entries"
        + (f" for service {service}" if service else "")
    )
    try:
        # Use systemd-python journal reader
        j = journal.Reader()
        j.log_level(journal.LOG_DEBUG)

        # Filter by service if specified
        if service:
            j.add_match(_SYSTEMD_UNIT=service)

        # Seek to the end and go backwards
        j.seek_tail()
        j.get_previous()

        # Collect entries
        logs = []
        count = 0

        for entry in j:
            if count >= limit:
                break

            # Extract relevant fields
            log_entry = {
                "timestamp": (
                    entry.get("__REALTIME_TIMESTAMP", "").isoformat()
                    if hasattr(entry.get("__REALTIME_TIMESTAMP", ""), "isoformat")
                    else str(entry.get("__REALTIME_TIMESTAMP", ""))
                ),
                "priority": entry.get("PRIORITY", ""),
                "unit": entry.get(
                    "_SYSTEMD_UNIT", entry.get("SYSLOG_IDENTIFIER", "system")
                ),
                "message": entry.get("MESSAGE", ""),
                "pid": entry.get("_PID", ""),
                "hostname": entry.get("_HOSTNAME", ""),
            }
            logs.append(log_entry)
            count += 1

        # Reverse to show oldest first
        logs.reverse()

        logger.success(
            f"Successfully retrieved {len(logs)} journal entries"
            + (f" for {service}" if service else "")
        )
        return {"count": len(logs), "logs": logs, "service": service}

    except Exception as e:
        logger.exception(f"Failed to read journal: {str(e)}")
        logger.info("Falling back to journalctl command")

        # Fallback to journalctl command
        try:
            cmd = ["journalctl", "-n", str(limit), "-o", "json", "--no-pager"]
            if service:
                cmd.extend(["-u", service])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )

            logs = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        log_entry = {
                            "timestamp": entry.get("__REALTIME_TIMESTAMP", ""),
                            "priority": entry.get("PRIORITY", ""),
                            "unit": entry.get(
                                "_SYSTEMD_UNIT",
                                entry.get("SYSLOG_IDENTIFIER", "system"),
                            ),
                            "message": entry.get("MESSAGE", ""),
                            "pid": entry.get("_PID", ""),
                            "hostname": entry.get("_HOSTNAME", ""),
                        }
                        logs.append(log_entry)
                    except json.JSONDecodeError:
                        continue

            logger.success(
                f"Successfully retrieved {len(logs)} journal entries using fallback"
                + (f" for {service}" if service else "")
            )
            return {"count": len(logs), "logs": logs, "service": service}

        except Exception as fallback_error:
            logger.exception(f"Fallback method also failed: {str(fallback_error)}")
            return {
                "error": f"Failed to read journal: {str(fallback_error)}",
                "logs": [],
                "service": service,
            }


@app.get("/services/")
def list_systemd_services():
    """
    List all systemd services with their status using D-Bus API
    """
    logger.info("Fetching systemd services list via D-Bus")
    try:
        # Use pystemd to communicate with systemd via D-Bus
        with Manager() as manager:
            # List all units
            units = manager.Manager.ListUnits()
            logger.info(f"Units: {units}")

            logger.info(f"Retrieved {len(units)} units from systemd")

            # Filter for service units
            services = []
            for unit in units:
                # unit is a tuple: (name, description, load_state, active_state, sub_state, ...)
                # D-Bus returns bytes, so we need to decode them
                unit_name = (
                    unit[0].decode("utf-8") if isinstance(unit[0], bytes) else unit[0]
                )
                if unit_name.endswith(".service"):
                    services.append(
                        {
                            "unit": unit_name,
                            "description": (
                                unit[1].decode("utf-8")
                                if isinstance(unit[1], bytes)
                                else unit[1]
                            ),
                            "load": (
                                unit[2].decode("utf-8")
                                if isinstance(unit[2], bytes)
                                else unit[2]
                            ),
                            "active": (
                                unit[3].decode("utf-8")
                                if isinstance(unit[3], bytes)
                                else unit[3]
                            ),
                            "sub": (
                                unit[4].decode("utf-8")
                                if isinstance(unit[4], bytes)
                                else unit[4]
                            ),
                            "follower": (
                                unit[5].decode("utf-8")
                                if isinstance(unit[5], bytes)
                                else unit[5]
                            ),
                            "path": str(unit[6]),
                        }
                    )

            logger.success(f"Successfully retrieved {len(services)} services")
            return {"count": len(services), "services": services}

    except Exception as e:
        logger.exception(f"Failed to list services via D-Bus: {str(e)}")
        logger.info("Falling back to systemctl command")

        # Fallback to systemctl command
        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "list-units",
                    "--type=service",
                    "--all",
                    "--no-pager",
                    "--plain",
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            logger.info(f"systemctl output length: {len(result.stdout)}")

            services = []
            lines = result.stdout.strip().split("\n")
            logger.info(f"Got {len(lines)} lines from systemctl")

            for line in lines[1:]:  # Skip header
                if line.strip() and not line.startswith("UNIT"):
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        services.append(
                            {
                                "unit": parts[0],
                                "load": parts[1],
                                "active": parts[2],
                                "sub": parts[3],
                                "description": parts[4],
                            }
                        )

            logger.success(
                f"Successfully retrieved {len(services)} services using fallback"
            )
            return {"count": len(services), "services": services}

        except Exception as fallback_error:
            logger.exception(f"Fallback method also failed: {str(fallback_error)}")
            return {
                "error": f"Failed to list services: {str(fallback_error)}",
                "services": [],
            }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

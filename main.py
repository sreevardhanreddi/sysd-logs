import uvicorn
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from systemd import journal
from pystemd.systemd1 import Manager
from pystemd import daemon
import subprocess
import json
from loguru import logger
import sys
import asyncio
from datetime import datetime, timedelta
import select


app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def services_ui(request: Request):
    """
    Render the HTMX + Tailwind UI for systemd services
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/logs", response_class=HTMLResponse)
async def logs_ui(request: Request):
    """
    Render the HTMX + Tailwind UI for systemd journal logs
    """
    return templates.TemplateResponse("logs.html", {"request": request})


@app.get("/api/logs/")
def get_journal_logs(service: str, limit: int = 100):
    """
    Get the last N entries from systemd journal for a specific service unit
    
    Args:
        service: The systemd service unit name (e.g., nginx.service)
        limit: Maximum number of log entries to return (default: 100)
    """
    logger.info(f"Fetching last {limit} journal entries for service {service}")
    
    try:
        # Use systemd-python journal reader
        j = journal.Reader()
        j.log_level(journal.LOG_DEBUG)

        # Filter by service (mandatory)
        j.add_match(_SYSTEMD_UNIT=service)
        logger.debug(f"Added match filter for service: {service}")

        # Seek to tail and iterate BACKWARD to get recent entries
        j.seek_tail()
        logger.debug("Seeked to journal tail, iterating backward")
        
        logs = []
        for i in range(limit):
            entry = j.get_previous()
            
            # get_previous() returns empty dict when no more entries
            if not entry:
                logger.debug(f"No more entries at iteration {i}")
                break

            logger.debug(f"Processing entry {i}, has {len(entry)} fields")
            try:
                log_entry = format_log_entry(entry)
                logs.append(log_entry)
                logger.debug(f"Successfully processed entry {i}")
            except Exception as entry_error:
                logger.warning(f"Error processing journal entry: {entry_error}")
                continue

        # Reverse to show oldest first (we collected from newest to oldest)
        logs.reverse()
        logger.debug(f"Collected {len(logs)} entries from journal (oldest first)")

        logger.success(f"Successfully retrieved {len(logs)} journal entries for {service}")
        return {"count": len(logs), "logs": logs, "service": service}

    except Exception as e:
        logger.exception(f"Failed to read journal: {str(e)}")
        logger.info("Falling back to journalctl command")

        # Fallback to journalctl command
        try:
            cmd = ["journalctl", "-n", str(limit), "-o", "json", "--no-pager", "-u", service]

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
                f"Successfully retrieved {len(logs)} journal entries for {service} using fallback"
            )
            return {"count": len(logs), "logs": logs, "service": service}

        except Exception as fallback_error:
            logger.exception(f"Fallback method also failed: {str(fallback_error)}")
            return {
                "error": f"Failed to read journal for {service}: {str(fallback_error)}",
                "logs": [],
                "service": service,
            }


@app.get("/api/logs/stream")
async def stream_logs(service: str):
    """
    Stream logs in real-time using Server-Sent Events (SSE)
    
    Args:
        service: The systemd service unit name (e.g., nginx.service)
    """
    
    async def generate_log_stream():
        try:
            # Create journal reader
            j = journal.Reader()
            j.log_level(journal.LOG_DEBUG)
            
            # Filter by service
            j.add_match(_SYSTEMD_UNIT=service)
            logger.info(f"Starting log stream for service: {service}")
            
            # Seek to end for live streaming
            j.seek_tail()
            j.get_previous()  # Position at last entry
            logger.debug("Starting live stream from tail")
            
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'service': service})}\n\n"
            
            # Follow the journal in real-time
            logger.debug("Starting real-time follow loop")
            while True:
                # Wait for new entries (with timeout)
                change = j.wait(1.0)  # Wait up to 1 second for new entries
                if change == journal.APPEND:
                    # New entries available, read them using get_next()
                    while True:
                        entry = j.get_next()
                        if not entry:
                            break
                        
                        try:
                            log_entry = format_log_entry(entry)
                            yield f"data: {json.dumps({'type': 'log', 'data': log_entry})}\n\n"
                            await asyncio.sleep(0)  # Allow other tasks to run
                        except Exception as e:
                            logger.warning(f"Error formatting entry: {e}")
                            continue
                
                # Small sleep to prevent CPU spinning
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            logger.info(f"Log stream cancelled for service: {service}")
            yield f"data: {json.dumps({'type': 'disconnected'})}\n\n"
        except Exception as e:
            logger.exception(f"Error in log stream: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_log_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


def format_log_entry(entry):
    """Format a journal entry into a log dict"""
    # Handle both string and bytes for various fields
    message = entry.get("MESSAGE", "")
    if isinstance(message, bytes):
        message = message.decode('utf-8', errors='replace')
    
    unit = entry.get("_SYSTEMD_UNIT", entry.get("SYSLOG_IDENTIFIER", "system"))
    if isinstance(unit, bytes):
        unit = unit.decode('utf-8', errors='replace')
    
    hostname = entry.get("_HOSTNAME", "")
    if isinstance(hostname, bytes):
        hostname = hostname.decode('utf-8', errors='replace')
    
    return {
        "timestamp": (
            entry.get("__REALTIME_TIMESTAMP", "").isoformat()
            if hasattr(entry.get("__REALTIME_TIMESTAMP", ""), "isoformat")
            else str(entry.get("__REALTIME_TIMESTAMP", ""))
        ),
        "priority": entry.get("PRIORITY", ""),
        "unit": unit,
        "message": str(message),
        "pid": entry.get("_PID", ""),
        "hostname": hostname,
    }


@app.get("/api/services/")
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


@app.post("/api/services/{service_name}/start")
def start_service(service_name: str):
    """
    Start a systemd service
    
    Args:
        service_name: The systemd service unit name (e.g., nginx.service)
    """
    logger.info(f"Attempting to start service: {service_name}")
    
    try:
        # Use pystemd to communicate with systemd via D-Bus
        with Manager() as manager:
            # Start the service
            manager.Manager.StartUnit(service_name.encode(), b'replace')
            logger.success(f"Successfully started service: {service_name}")
            return {
                "status": "success",
                "message": f"Service {service_name} started successfully",
                "service": service_name
            }
    
    except Exception as e:
        logger.exception(f"Failed to start service {service_name} via D-Bus: {str(e)}")
        logger.info("Falling back to systemctl command")
        
        # Fallback to systemctl command
        try:
            result = subprocess.run(
                ["systemctl", "start", service_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.success(f"Successfully started service {service_name} using fallback")
            return {
                "status": "success",
                "message": f"Service {service_name} started successfully",
                "service": service_name
            }
        
        except subprocess.CalledProcessError as fallback_error:
            logger.exception(f"Fallback method also failed: {str(fallback_error)}")
            return {
                "status": "error",
                "message": f"Failed to start service {service_name}: {fallback_error.stderr or str(fallback_error)}",
                "service": service_name
            }


@app.post("/api/services/{service_name}/stop")
def stop_service(service_name: str):
    """
    Stop a systemd service
    
    Args:
        service_name: The systemd service unit name (e.g., nginx.service)
    """
    logger.info(f"Attempting to stop service: {service_name}")
    
    try:
        # Use pystemd to communicate with systemd via D-Bus
        with Manager() as manager:
            # Stop the service
            manager.Manager.StopUnit(service_name.encode(), b'replace')
            logger.success(f"Successfully stopped service: {service_name}")
            return {
                "status": "success",
                "message": f"Service {service_name} stopped successfully",
                "service": service_name
            }
    
    except Exception as e:
        logger.exception(f"Failed to stop service {service_name} via D-Bus: {str(e)}")
        logger.info("Falling back to systemctl command")
        
        # Fallback to systemctl command
        try:
            result = subprocess.run(
                ["systemctl", "stop", service_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.success(f"Successfully stopped service {service_name} using fallback")
            return {
                "status": "success",
                "message": f"Service {service_name} stopped successfully",
                "service": service_name
            }
        
        except subprocess.CalledProcessError as fallback_error:
            logger.exception(f"Fallback method also failed: {str(fallback_error)}")
            return {
                "status": "error",
                "message": f"Failed to stop service {service_name}: {fallback_error.stderr or str(fallback_error)}",
                "service": service_name
            }


@app.post("/api/services/{service_name}/restart")
def restart_service(service_name: str):
    """
    Restart a systemd service
    
    Args:
        service_name: The systemd service unit name (e.g., nginx.service)
    """
    logger.info(f"Attempting to restart service: {service_name}")
    
    try:
        # Use pystemd to communicate with systemd via D-Bus
        with Manager() as manager:
            # Restart the service
            manager.Manager.RestartUnit(service_name.encode(), b'replace')
            logger.success(f"Successfully restarted service: {service_name}")
            return {
                "status": "success",
                "message": f"Service {service_name} restarted successfully",
                "service": service_name
            }
    
    except Exception as e:
        logger.exception(f"Failed to restart service {service_name} via D-Bus: {str(e)}")
        logger.info("Falling back to systemctl command")
        
        # Fallback to systemctl command
        try:
            result = subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.success(f"Successfully restarted service {service_name} using fallback")
            return {
                "status": "success",
                "message": f"Service {service_name} restarted successfully",
                "service": service_name
            }
        
        except subprocess.CalledProcessError as fallback_error:
            logger.exception(f"Fallback method also failed: {str(fallback_error)}")
            return {
                "status": "error",
                "message": f"Failed to restart service {service_name}: {fallback_error.stderr or str(fallback_error)}",
                "service": service_name
            }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

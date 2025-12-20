# 🌐 SOA1 Web UI - Tailscale Edition

A dedicated web interface for SOA1 with Tailscale integration for secure remote access.

## 🚀 Quick Start

### 1. Start the Web UI Server

```bash
cd /home/ryzen/projects/soa-webui
python3 main.py
```

The web UI will be available at: `http://localhost:8080`

### 2. Access via Tailscale

Since you're using Tailscale, you can access the web UI securely from any Tailscale-connected device:

```
http://<your-tailscale-ip>:8080
```

## 📁 Directory Structure

```
soa-webui/
├── main.py                # Main web application
├── services/              # Service management
│   ├── monitor.py         # Service monitoring
│   └── control.py         # Service control
├── templates/             # HTML templates
│   ├── index.html         # Main dashboard
│   ├── services.html      # Services page
│   └── status.html        # Status page
├── static/                # Static assets
│   ├── css/               # Stylesheets
│   └── js/                # JavaScript
├── config.yaml            # Configuration
└── README.md              # This file
```

## 🔧 Configuration

Edit `config.yaml` to customize:

```yaml
# Server settings
server:
  host: "0.0.0.0"  # Listen on all interfaces for Tailscale
  port: 8080       # Port for web UI
  
# SOA1 Services
services:
  api: "http://localhost:8001"
  web_interface: "http://localhost:8002"
  service_monitor: "http://localhost:8003"
  memlayer: "http://localhost:8000"
  
# Tailscale settings
tailscale:
  enabled: true
  # Allow only specific Tailscale IPs (optional)
  allowed_ips:
    - "100.64.0.0/10"  # Tailscale IP range
  
# Security
security:
  # IP-based access control (Tailscale IPs only)
  ip_whitelist:
    - "100.64.0.0/10"
  
# Features
features:
  service_control: true
  monitoring: true
  logging: true
```

## 🎯 Features

### 🌐 Service Dashboard
- Real-time status of all SOA1 services
- CPU/Memory usage monitoring
- Service health indicators
- Quick access links

### 🔧 Service Control
- Start/Stop SOA1 services
- Restart individual components
- View service logs
- Manage service configurations

### 📊 System Monitoring
- System resource usage
- Service performance metrics
- Uptime monitoring
- Error tracking

### 🔒 Tailscale Integration
- Automatic IP-based access control
- Secure remote access without port forwarding
- Encrypted connections
- No public internet exposure

## 🚀 Service Management

### Start All Services

```bash
cd /home/ryzen/projects/soa-webui
python3 services/control.py start-all
```

### Stop All Services

```bash
python3 services/control.py stop-all
```

### Check Service Status

```bash
python3 services/control.py status
```

## 🌐 Access URLs

- **Main Dashboard**: `http://<tailscale-ip>:8080/`
- **Services Page**: `http://<tailscale-ip>:8080/services`
- **Status Page**: `http://<tailscale-ip>:8080/status`
- **API Endpoint**: `http://<tailscale-ip>:8080/api`

## 🔐 Security

### Tailscale Security Benefits

1. **No Public Ports**: Services are not exposed to the internet
2. **Encrypted Connections**: All traffic is encrypted end-to-end
3. **IP Whitelisting**: Only Tailscale IPs can access services
4. **Authentication**: Tailscale handles authentication
5. **Network Isolation**: Services are only accessible via Tailscale

### Additional Security Measures

- IP-based access control in the web UI
- Service isolation
- No unnecessary port exposure
- Secure service-to-service communication

## 📋 Service Routes

The web UI provides access to:

| Service | Internal Port | Web UI Path | Description |
|---------|---------------|-------------|-------------|
| SOA1 API | 8001 | `/api` | Main SOA1 API endpoints |
| Web Interface | 8002 | `/web` | SOA1 chat interface |
| Service Monitor | 8003 | `/monitor` | Service status dashboard |
| Memlayer | 8000 | `/memory` | Memory service |
| Web UI | 8080 | `/` | This web interface |

## 🎨 Customization

### Add Custom CSS

Place your CSS files in `static/css/` and they'll be automatically loaded.

### Add Custom JavaScript

Place your JS files in `static/js/` for client-side functionality.

### Modify Templates

Edit the HTML templates in `templates/` to change the UI appearance.

## 🔧 Development

### Requirements

```bash
pip install fastapi uvicorn psutil requests python-multipart
```

### Run in Development Mode

```bash
cd /home/ryzen/projects/soa-webui
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

### Build for Production

```bash
# Install dependencies
pip install -r requirements.txt

# Run with gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
```

## 📦 Deployment

### Systemd Service (Optional)

Create `/etc/systemd/system/soa-webui.service`:

```ini
[Unit]
Description=SOA1 Web UI
After=network.target tailscale.service

[Service]
User=ryzen
WorkingDirectory=/home/ryzen/projects/soa-webui
ExecStart=/usr/bin/python3 /home/ryzen/projects/soa-webui/main.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Then enable and start:

```bash
sudo systemctl enable soa-webui
sudo systemctl start soa-webui
```

## 🎯 Tailscale Tips

### Check Your Tailscale IP

```bash
tailscale ip -4
```

### Share Access with Others

```bash
# Share with another Tailscale user
sudo tailscale up --advertise-routes=10.0.0.0/24

# Check connected devices
sudo tailscale status
```

### Tailscale ACLs

For advanced access control, use Tailscale ACLs in your tailnet configuration.

## 💡 Troubleshooting

### Web UI Not Accessible

1. Check if the service is running: `ps aux | grep main.py`
2. Check Tailscale status: `sudo tailscale status`
3. Verify port binding: `ss -tulnp | grep 8080`
4. Check logs: `journalctl -u soa-webui -f`

### Services Not Showing

1. Verify SOA1 services are running
2. Check service ports are correct in config.yaml
3. Test direct access to service ports locally

### Tailscale Connection Issues

1. Check Tailscale status: `sudo tailscale status`
2. Restart Tailscale: `sudo systemctl restart tailscale`
3. Check firewall: `sudo ufw status`

## 📚 License

This web UI is part of the SOA1 project and is open source.

---

**Last Updated**: December 12, 2025
**Version**: 1.0.0 (Tailscale Edition)
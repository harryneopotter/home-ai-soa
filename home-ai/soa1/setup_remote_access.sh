#!/bin/bash

# SOA1 Remote Access Setup Script
# Sets up Tailscale and web interface for remote access

echo "🚀 Setting up SOA1 Remote Access..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
apt-get update -qq
apt-get install -y -qq curl wget git python3-pip

# Install Tailscale
echo "🔗 Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh

# Start Tailscale
echo "🔑 Starting Tailscale..."
systemctl enable --now tailscaled

# Check if Tailscale is running
if ! systemctl is-active --quiet tailscaled; then
    echo "❌ Failed to start Tailscale"
    exit 1
fi

# Authenticate Tailscale
TAILSCALE_AUTH_KEY=""
if [ -z "$TAILSCALE_AUTH_KEY" ]; then
    echo "🔑 Please authenticate Tailscale:"
    tailscale up
else
    echo "🔑 Authenticating with auth key..."
    tailscale up --authkey="$TAILSCALE_AUTH_KEY"
fi

# Get Tailscale IP
TAILSCALE_IP=$(tailscale ip -4)
if [ -z "$TAILSCALE_IP" ]; then
    echo "❌ Failed to get Tailscale IP"
    exit 1
fi

echo "✅ Tailscale IP: $TAILSCALE_IP"

# Install Python dependencies
echo "🐍 Installing Python dependencies..."
pip3 install torch torchaudio transformers soundfile fastapi uvicorn jinja2 python-multipart -q

# Create systemd service for web interface
echo "📋 Creating web interface service..."
cat > /etc/systemd/system/soa1-web.service <<EOL
[Unit]
Description=SOA1 Web Interface
After=network.target

[Service]
User=ryzen
WorkingDirectory=/home/ryzen/projects/home-ai/soa1
ExecStart=/usr/bin/python3 /home/ryzen/projects/home-ai/soa1/web_interface.py
Restart=always
RestartSec=5
Environment=PYTHONPATH=/home/ryzen/projects/home-ai

[Install]
WantedBy=multi-user.target
EOL

# Reload systemd
echo "🔄 Reloading systemd..."
systemctl daemon-reload

# Enable and start services
echo "🚀 Starting services..."
systemctl enable soa1-web
systemctl start soa1-web

# Check services
if ! systemctl is-active --quiet soa1-web; then
    echo "❌ Failed to start web interface"
    journalctl -u soa1-web -n 20 --no-pager
    exit 1
fi

echo "✅ Web interface started"

# Create firewall rules (if ufw is installed)
if command -v ufw &> /dev/null; then
    echo "🔥 Configuring firewall..."
    ufw allow 8002/tcp
    ufw reload
fi

# Display access information
echo ""
echo "🎉 Setup Complete!"
echo ""
echo "Access your SOA1 interface at:"
echo "🌐 http://$TAILSCALE_IP:8002"
echo ""
echo "Services:"
echo "  - Web Interface: http://$TAILSCALE_IP:8002"
echo "  - SOA1 API: http://$TAILSCALE_IP:8001"
echo "  - MemLayer: http://$TAILSCALE_IP:8000"
echo ""
echo "Tailscale status: tailscale status"
echo "Service logs: journalctl -u soa1-web -f"
echo ""

exit 0
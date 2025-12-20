#!/bin/bash

# SOA1 Nginx Setup Script
# Configures Nginx as a reverse proxy for SOA1 services with SSL

echo "🚀 Setting up Nginx for SOA1 Remote Access..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root or with sudo"
    exit 1
fi

# Install Nginx
if ! command -v nginx &> /dev/null; then
    echo "📦 Installing Nginx..."
    apt-get update -qq
    apt-get install -y -qq nginx certbot python3-certbot-nginx
else
    echo "✅ Nginx is already installed"
fi

# Create Nginx configuration directory
NGINX_CONF="/etc/nginx/sites-available/soa1.conf"
echo "📝 Creating Nginx configuration..."

# Get the server domain/IP
read -p "Enter your domain name or server IP: " SERVER_NAME
if [ -z "$SERVER_NAME" ]; then
    SERVER_NAME="$(hostname -I | awk '{print $1}')"
    echo "📌 Using server IP: $SERVER_NAME"
fi

# Create Nginx configuration
cat > "$NGINX_CONF" << 'EOF'
# SOA1 Services Reverse Proxy Configuration
upstream soa1_api {
    server 127.0.0.1:8001;
}

upstream soa1_web {
    server 127.0.0.1:8002;
}

upstream soa1_monitor {
    server 127.0.0.1:8003;
}

upstream memlayer {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name {{SERVER_NAME}};
    
    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name {{SERVER_NAME}};
    
    # SSL Configuration (will be added by Certbot)
    ssl_certificate /etc/letsencrypt/live/{{SERVER_NAME}}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{{SERVER_NAME}}/privkey.pem;
    
    # SSL Settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384';
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    # Security Headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "no-referrer-when-downgrade" always;
    add_header Content-Security-Policy "default-src 'self' http: https: ws: wss: data: blob:;";
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    
    # Basic Authentication (optional)
    # auth_basic "SOA1 Access";
    # auth_basic_user_file /etc/nginx/.htpasswd;
    
    # Service Routes
    location /api/ {
        proxy_pass http://soa1_api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
    
    location /chat/ {
        proxy_pass http://soa1_web/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
    
    location /monitor/ {
        proxy_pass http://soa1_monitor/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
    
    location /memlayer/ {
        proxy_pass http://memlayer/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }
    
    # Static files for web interface
    location /static/ {
        alias /home/ryzen/projects/home-ai/soa1/static/;
        expires 30d;
    }
    
    # Main landing page
    location = / {
        return 302 /monitor/;
    }
    
    # WebSocket support (if needed)
    location /ws/ {
        proxy_pass http://soa1_api;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # Error pages
    error_page 404 /404.html;
    error_page 500 502 503 504 /50x.html;
    
    # Logging
    access_log /var/log/nginx/soa1_access.log;
    error_log /var/log/nginx/soa1_error.log;
    
    # Gzip compression
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
}
EOF

# Replace placeholder with actual server name
sed -i "s/{{SERVER_NAME}}/$SERVER_NAME/g" "$NGINX_CONF"

# Enable the site
echo "🔧 Enabling SOA1 Nginx configuration..."
if [ -f "/etc/nginx/sites-enabled/soa1.conf" ]; then
    rm /etc/nginx/sites-enabled/soa1.conf
fi
ln -s "$NGINX_CONF" /etc/nginx/sites-enabled/

# Test Nginx configuration
echo "🧪 Testing Nginx configuration..."
if nginx -t; then
    echo "✅ Nginx configuration is valid"
else
    echo "❌ Nginx configuration has errors"
    exit 1
fi

# Restart Nginx
echo "🔄 Restarting Nginx..."
systemctl restart nginx

# Set up SSL with Certbot (if domain is provided and not local IP)
if [[ "$SERVER_NAME" != "127.0.0.1" && "$SERVER_NAME" != "localhost" && ! "$SERVER_NAME" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "🔒 Setting up SSL certificate with Certbot..."
    certbot --nginx -d "$SERVER_NAME" --non-interactive --agree-tos --email admin@$SERVER_NAME
else
    echo "📌 Skipping SSL setup (using local IP or no domain)"
    echo "💡 For local testing, you can access services at:"
    echo "   - API: http://$SERVER_NAME/api/"
    echo "   - Web: http://$SERVER_NAME/chat/"
    echo "   - Monitor: http://$SERVER_NAME/monitor/"
fi

# Create basic authentication (optional)
read -p "Do you want to set up basic authentication? (y/n): " SETUP_AUTH
if [[ "$SETUP_AUTH" =~ ^[Yy]$ ]]; then
    echo "🔐 Setting up basic authentication..."
    apt-get install -y -qq apache2-utils
    htpasswd -c /etc/nginx/.htpasswd soa1_admin
    
    # Update Nginx config to enable auth
    sed -i '/# auth_basic/s/^# //' "$NGINX_CONF"
    sed -i '/# auth_basic_user_file/s/^# //' "$NGINX_CONF"
    
    systemctl restart nginx
    echo "✅ Basic authentication enabled"
fi

echo "🎉 Nginx setup completed!"
echo ""
echo "📋 Access URLs:"
echo "   - Service Monitor: https://$SERVER_NAME/monitor/"
echo "   - SOA1 Web Interface: https://$SERVER_NAME/chat/"
echo "   - SOA1 API: https://$SERVER_NAME/api/"
echo "   - Memlayer: https://$SERVER_NAME/memlayer/"
echo ""
echo "💡 Make sure to:"
echo "   1. Start all SOA1 services (api.py, web_interface.py, service_monitor.py)"
echo "   2. Open firewall ports (80, 443)"
echo "   3. Configure DNS if using a domain name"

exit 0
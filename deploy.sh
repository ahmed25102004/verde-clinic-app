#!/bin/bash

# Verde Beauty Clinic Deployment Script for Ubuntu/Debian
# Run this script as root or with sudo privileges!

set -e  # Exit on any error

echo "============================================="
echo "Verde Beauty Clinic - Deployment Script"
echo "============================================="
echo ""

# --------------------------
# Step 1: Update system
# --------------------------
echo "[1/7] Updating system packages..."
apt update && apt upgrade -y
echo "✓ System updated successfully!"
echo ""

# --------------------------
# Step 2: Install dependencies
# --------------------------
echo "[2/7] Installing dependencies (Python, Nginx, etc.)..."
apt install python3 python3-pip python3-venv nginx git -y
echo "✓ Dependencies installed!"
echo ""

# --------------------------
# Step 3: Clone or copy project
# --------------------------
echo "[3/7] Setting up project directory..."
APP_DIR="/opt/verde-beauty-clinic"
if [ ! -d "$APP_DIR" ]; then
    # Replace this with your Git repo URL if you're using Git!
    echo "Please clone or copy your project to $APP_DIR"
    echo "Then re-run this script!"
    exit 1
fi
cd $APP_DIR
echo "✓ Project directory set up at $APP_DIR"
echo ""

# --------------------------
# Step 4: Create virtual environment
# --------------------------
echo "[4/7] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate
echo "✓ Virtual environment created!"
echo ""

# --------------------------
# Step 5: Install requirements
# --------------------------
echo "[5/7] Installing Python packages..."
pip install --upgrade pip
pip install -r requirements.txt
echo "✓ Requirements installed!"
echo ""

# --------------------------
# Step 6: Create systemd service
# --------------------------
echo "[6/7] Creating systemd service..."
cat > /etc/systemd/system/verde-clinic.service << EOF
[Unit]
Description=Gunicorn instance to serve Verde Beauty Clinic
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 wsgi:app

[Install]
WantedBy=multi-user.target
EOF

# Set correct permissions
chown -R www-data:www-data $APP_DIR
chmod -R 755 $APP_DIR

systemctl daemon-reload
systemctl start verde-clinic
systemctl enable verde-clinic
echo "✓ Systemd service created and started!"
echo ""

# --------------------------
# Step 7: Configure Nginx
# --------------------------
echo "[7/7] Configuring Nginx..."
cat > /etc/nginx/sites-available/verde-clinic << 'EOF'
server {
    listen 80;
    server_name _;  # Replace with your domain name later!

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

# Enable the site
rm -f /etc/nginx/sites-enabled/default
ln -s /etc/nginx/sites-available/verde-clinic /etc/nginx/sites-enabled/

# Test Nginx config
nginx -t
systemctl restart nginx
echo "✓ Nginx configured successfully!"
echo ""

# --------------------------
# Done!
# --------------------------
echo "============================================="
echo "✅ DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "============================================="
echo ""
echo "Your app is now running at http://$(curl -s ifconfig.me)"
echo ""
echo "Next steps:"
echo "1. Create .env file: cp .env.example .env && nano .env"
echo "2. Initialize database: python3 -c 'from db import init_db; init_db()'"
echo "3. Set up your first admin user!"
echo "4. (Optional) Add SSL with Let's Encrypt!"
echo "============================================="

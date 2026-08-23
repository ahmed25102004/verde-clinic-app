#!/bin/bash

# SSL Setup Script for Verde Beauty Clinic
# Uses Let's Encrypt with Certbot

set -e

echo "============================================="
echo "Verde Beauty Clinic - SSL Setup"
echo "============================================="
echo ""

# Check if domain is provided
if [ -z "$1" ]; then
    echo "Usage: $0 your-domain.com"
    echo "Example: $0 clinic.example.com"
    exit 1
fi
DOMAIN=$1
EMAIL="admin@$DOMAIN"  # Change this if you want a different email!

echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Install Certbot
echo "[1/3] Installing Certbot..."
apt install certbot python3-certbot-nginx -y
echo "✓ Certbot installed!"
echo ""

# Obtain SSL certificate
echo "[2/3] Obtaining SSL certificate..."
certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m $EMAIL
echo "✓ SSL certificate obtained!"
echo ""

# Verify auto-renewal
echo "[3/3] Verifying auto-renewal..."
certbot renew --dry-run
echo "✓ Auto-renewal configured!"
echo ""

echo "============================================="
echo "✅ SSL SETUP COMPLETED!"
echo "============================================="
echo "Your site is now available at: https://$DOMAIN"
echo ""

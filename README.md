# Verde Beauty Clinic Management System

A full-featured management system for aesthetic clinics, built with Flask and SQLite!

## Features
- 👤 Customer management with medical history tracking
- 📦 Package and session management (with pulse tracking!)
- 💰 Payment tracking and financial reports
- 🔔 WhatsApp reminders (integrated with UltraMsg/Green-API)
- 📊 Daily and monthly reports with charts
- 👥 Employee management
- 💾 Automated database backups
- ✨ And much more!

## Requirements
- Python 3.8+
- Virtual environment

## Local Development Setup

### 1. Clone or download the project
```powershell
# Navigate to the project directory
cd g:\AI\VerdeBeautyClinic__Accounts
```

### 2. Create virtual environment
```powershell
python -m venv Accounts
Accounts\Scripts\activate
```

### 3. Install dependencies
```powershell
pip install -r requirements.txt
```

### 4. Set up environment variables
Copy `.env.example` to `.env` and configure:
```powershell
cp .env.example .env
# Edit .env with your settings!
```

### 5. Initialize the database
Run this in your Python environment:
```python
from db import init_db
init_db()
```

Or run:
```powershell
python -c "from db import init_db; init_db()"
```

### 6. Create an admin user
Use `set_manager.py` to create your first admin account!

### 7. Run the development server!
```powershell
python app.py
```
The app will be available at http://127.0.0.1:5007!

---

## Deployment to a VPS (Ubuntu/Debian)

### Prerequisites
- A VPS running Ubuntu 22.04 or later
- A domain name (optional but recommended)
- SSH access to your VPS

### Step 1: Upload your project to the server
Use Git, SFTP, or SCP to upload the project files to `/opt/verde-beauty-clinic` on your VPS.

### Step 2: Run the deployment script
```bash
# SSH into your server
ssh root@your-server-ip

# Navigate to the project directory
cd /opt/verde-beauty-clinic

# Make scripts executable
chmod +x deploy.sh ssl_setup.sh

# Run the deployment script!
sudo ./deploy.sh
```

### Step 3: Finish the setup
```bash
# Create your .env file from the example
cp .env.example .env
nano .env  # Edit with your secret key!

# Initialize the database
source venv/bin/activate
python -c "from db import init_db; init_db(); from db import seed_packages; seed_packages()"

# Create your first admin user!
python set_manager.py
```

### Step 4 (Optional): Set up SSL with Let's Encrypt
If you have a domain name, run:
```bash
sudo ./ssl_setup.sh your-domain.com
```

---

## Project Structure
```
VerdeBeautyClinic__Accounts/
├── app.py                 # Main Flask application
├── wsgi.py                # WSGI entry point for production
├── db.py                  # Database setup and functions
├── auth.py                # Authentication decorators
├── requirements.txt       # Python dependencies
├── Procfile              # For PaaS deployments (Render/Heroku)
├── deploy.sh             # Ubuntu/Debian deployment script
├── ssl_setup.sh          # SSL setup with Let's Encrypt
├── models/               # Database models
├── controllers/          # Controllers for handling logic
├── templates/            # HTML templates
├── static/               # CSS, JS, images
├── exports/              # Exported Excel files
└── backups/              # Database backups
```

---

## Technologies Used
- **Backend:** Flask (Python)
- **Database:** SQLite
- **Web Server:** Nginx + Gunicorn
- **Other:** openpyxl (for Excel exports), requests (for WhatsApp API)

---

## Need Help?
Check out the code or reach out! 😊

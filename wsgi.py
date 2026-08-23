from app import app
from db import init_db, seed_packages

# Initialize database and packages on application startup
init_db()
seed_packages()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5007)

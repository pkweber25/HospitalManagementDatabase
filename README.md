Setup:

Create .env file 

```ru
# ---------------- DATABASE CONNECTION ----------------
DB_HOST=127.0.0.1
DB_USER=root
DB_PASSWORD=DB_PASSWORD
DB_NAME=hospital_system

# ---------------- JWT AUTHENTICATION ----------------
# This secret is used to securely sign user login sessions
JWT_SECRET=SECRET_KEY
JWT_ALGO=HS256

# ---------------- INITIAL ADMIN SETUP ----------------
# The server will automatically create this user if the database is empty
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
ADMIN_FULL_NAME=System Administrator
```

inside 'database' directory 

```bash
docker-compose up -d
```

Then to start the server, go into /backend directory
```bash
python server.py
```

And open http://127.0.0.1:5000 or http://localhost:5000


To end session

```bash
docker-compose down -v
```


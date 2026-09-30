# Online Card Request and Tracking System — Version 1

A Flask + SQLite prototype for an academic project at Federal University of Agriculture, Zuru, Computer Science Department.

## Features
- Student registration and login
- Secure password hashing
- Student dashboard
- ATM card request submission
- Unique tracking code
- Request status tracking
- Admin dashboard
- Admin status updates and notes
- SQLite database

## Run

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. Create a virtual environment:

   Windows:
   `python -m venv venv`
   `venv\Scripts\activate`

   Linux/macOS:
   `python3 -m venv venv`
   `source venv/bin/activate`

4. Install dependencies:
   `pip install -r requirements.txt`

5. Start:
   `python app.py`

6. Open:
   `http://127.0.0.1:5000`

## Default administrator
Email: `admin@fauz.edu.ng`
Password: `admin123`

Change the default admin password before real deployment.

## Important
This prototype must NOT collect ATM card numbers, PINs, CVVs, banking passwords, or other sensitive banking credentials.


## Production deployment

For Render deployment, set the `ADMIN_PASSWORD` environment variable to a strong password. The application uses PostgreSQL when `DATABASE_URL` is provided and falls back to SQLite for local development.

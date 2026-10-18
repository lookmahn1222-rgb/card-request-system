# Online Card Request and Tracking System

Flask-based academic prototype for card requests, tracking, and manual bank-transfer payment verification.

## Features
- Student registration and login with hashed passwords
- Card request creation with card type, delivery address, and reason
- Unique tracking code and request status tracking
- Fixed card request fee of ₦2,000
- Bank-transfer instructions and transfer-reference submission
- Administrator payment verification/rejection
- Request processing is blocked until payment is verified
- SQLite locally and PostgreSQL when `DATABASE_URL` is configured
- CSRF protection on forms

## Local setup (Windows PowerShell)
1. Install Python 3.10+ and open a terminal in this folder.
2. Create and activate a virtual environment:
   `python -m venv venv`
   `venv\Scripts\Activate.ps1`
3. Install dependencies: `pip install -r requirements.txt`
4. Set a strong local secret and administrator password before first run:
   `$env:SECRET_KEY = [guid]::NewGuid().ToString() + [guid]::NewGuid().ToString()`
   `$env:ADMIN_PASSWORD = 'replace-with-a-strong-unique-password'`
5. Start: `python app.py`
6. Open `http://127.0.0.1:5000`.

On Linux/macOS, export `SECRET_KEY` and `ADMIN_PASSWORD` before running `python app.py`.

## Administrator account
The application creates `admin@fauz.edu.ng` only when `ADMIN_PASSWORD` is configured and no such account exists. If the account already exists, setting `ADMIN_PASSWORD` resets its password to that value on startup. Use a strong, unique value and do not share it. The application does not create an administrator with a hard-coded default password.

## Bank transfer details
- Fee: ₦2,000
- Bank: Access Bank
- Account name: LUKMAN UMAR
- Account number: 1673932526

Verify every transfer in the actual bank account before marking it verified. A transfer reference by itself is not proof of payment. This prototype does not connect to a bank API and does not automatically confirm transfers.

## Database compatibility and backup
The application adds the payment/address columns to an existing `card_request` table without dropping its records. **Back up your existing database before deploying this update.** Schema changes are intentionally limited to adding columns; they do not migrate or delete existing requests. Existing requests are treated as unpaid until an administrator verifies a payment.

## Production deployment
Set these environment variables in your hosting provider:
- `SECRET_KEY`: a long, random secret
- `ADMIN_PASSWORD`: a strong administrator password
- `DATABASE_URL`: PostgreSQL connection string
- `COOKIE_SECURE=1`: enable secure session cookies when serving over HTTPS

The provided Render configuration generates `SECRET_KEY` and asks for `ADMIN_PASSWORD`. Do not use the local development secret in production. Deploy behind HTTPS. Back up the database before every schema update.

## Important safety note
Never collect ATM/card numbers, PINs, CVVs, online banking passwords, or one-time passwords. This project is a prototype; manual verification does not replace a trusted payment gateway or professional security review.

# TrekManager — Trekking Management Application

A role-based web app for managing trekking activities, built with **Flask + SQLite + Bootstrap**.
Roles: **Admin**, **Trek Staff**, and **User (Trekker)**. No JavaScript is used for any core
functionality (only Bootstrap's bundle for the collapsible navbar).

## Tech stack
- **Backend:** Flask 3, Flask-Login, Flask-SQLAlchemy
- **Database:** SQLite — created *programmatically* from the SQLAlchemy models (`models.py`)
  on first run. No manual DB creation.
- **Frontend:** Jinja2 templates, HTML, CSS, Bootstrap 5

## Setup & run

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

The database (`instance/trekking.db`) and a pre-seeded admin + demo data are created
automatically on first launch.

## Demo accounts

| Role  | Email            | Password  | Notes                          |
|-------|------------------|-----------|--------------------------------|
| Admin | admin@trek.com   | admin123  | Pre-existing superuser         |
| Staff | ravi@trek.com    | staff123  | Approved, has assigned treks   |
| Staff | meera@trek.com   | staff123  | Pending admin approval         |
| User  | anil@trek.com    | user123   | Has a booking                  |
| User  | sara@trek.com    | user123   | —                              |

> To start completely fresh, delete `instance/trekking.db` and restart.

## Features

**Admin**
- Dashboard with totals (treks, users, staff, bookings) + a popular-treks bar chart
- Create / edit / delete treks
- Approve or blacklist staff; assign staff to treks
- View & search users, staff, and treks (by name or ID); view all bookings
- Blacklist / reactivate users and staff

**Trek Staff** (self-register, needs admin approval)
- Dashboard of assigned treks with participant counts
- Update available slots and open/close bookings
- View participant list; mark trek started / completed
- Only the *assigned* staff member can manage a given trek

**User / Trekker** (self-register)
- Browse open treks; search & filter by name, difficulty, location
- Book treks (only when status is Open; overbooking is prevented)
- View booking status, cancel bookings, view full trekking history
- Edit profile

**Core rules enforced**
- No overbooking beyond available slots
- Only assigned staff can manage a trek
- Booking allowed only when a trek's status is *Open*
- Complete booking history retained per user

## Optional extras
- JSON API: `GET /api/treks` (public), `GET /api/stats` (admin)
- Role-based access control via decorators + Flask-Login

## Project structure
```
app.py            # Flask app, routes, DB bootstrap & seeding
models.py         # SQLAlchemy models (User, Trek, Booking)
requirements.txt
templates/        # Jinja2 templates (base, auth, admin/, staff/, user/)
static/style.css  # Custom styling on top of Bootstrap
instance/         # SQLite DB is created here on first run
```

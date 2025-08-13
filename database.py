# database.py
import sqlite3
import time
from datetime import datetime

DB_FILE = "reminders.db"


def initialize_db():
    """Creates the database and the reminders table if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            contest_name TEXT NOT NULL,
            contest_url TEXT NOT NULL,
            reminder_time INTEGER NOT NULL -- Stored as Unix timestamp
        );
    """)
    conn.commit()
    conn.close()


def add_reminder(
    user_id: int,
    contest_name: str,
    contest_url: str,
    start_time_str: str,
    remind_before_minutes: int,
):
    """Adds a reminder to the database."""
    dt_object = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
    start_time_unix = int(dt_object.timestamp())
    reminder_time_unix = start_time_unix - (remind_before_minutes * 60)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Check if this exact reminder already exists to prevent duplicates
    cursor.execute(
        "SELECT id FROM reminders WHERE user_id = ? AND contest_url = ?",
        (user_id, contest_url),
    )
    if cursor.fetchone():
        conn.close()
        return False  # Reminder already exists

    cursor.execute(
        "INSERT INTO reminders (user_id, contest_name, contest_url, reminder_time) VALUES (?, ?, ?, ?)",
        (user_id, contest_name, contest_url, reminder_time_unix),
    )
    conn.commit()
    conn.close()
    return True  # Reminder was added successfully


def get_due_reminders():
    """Fetches reminders that are due to be sent."""
    current_time_unix = int(time.time())
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Using a tuple for the parameter is the correct way
    cursor.execute(
        "SELECT id, user_id, contest_name, contest_url FROM reminders WHERE reminder_time <= ?",
        (current_time_unix,),
    )
    reminders = cursor.fetchall()
    conn.close()
    return reminders


def delete_reminder(reminder_id: int):
    """Deletes a reminder from the database after it has been sent."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()

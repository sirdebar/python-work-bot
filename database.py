import sqlite3

def create_tables():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workers (
            user_id INTEGER PRIMARY KEY,
            name TEXT
        )
    ''')

    conn.commit()
    conn.close()

def load_admins():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM admins")
    admins = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return admins

def load_workers():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM workers")
    workers = {row[0]: row[1] for row in cursor.fetchall()}
    conn.close()
    return workers

def add_admin(user_id, name=None):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO admins VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_worker(user_id, name):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO workers VALUES (?, ?)", (user_id, name))
    conn.commit()
    conn.close()

def remove_worker(user_id):
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM workers WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Ensure tables are created before the script ends
create_tables()

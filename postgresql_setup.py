from psycopg2 import connect, DatabaseError
from config import config


def create_tables():
    # write queries to create tables
    queries = [
        """CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, username TEXT NOT NULL, hash TEXT NOT NULL);""",
        """CREATE TABLE projects (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, task TEXT NOT NULL, deadline DATE, FOREIGN KEY (user_id));""",
        """CREATE TABLE today (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, task TEXT NOT NULL, priority TEXT, FOREIGN KEY (user_id));""",
        """CREATE TABLE mail (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, email TEXT NOT NULL, message TEXT NOT NULL, FOREIGN KEY (user_id));""",
        """CREATE TABLE personal (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, task TEXT NOT NULL, deadline DATE, FOREIGN KEY (user_id));""",
        """CREATE TABLE work (id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, user_id INTEGER NOT NULL, task TEXT NOT NULL, deadline DATE, FOREIGN KEY (user_id));""",
    ]

    # attempt query
    try:
        params = config()

        conn = connect(**params)

        with conn:
            with conn.cursor() as cur:
                cur.executemany(queries)
                cur.commit()

    except (Exception, DatabaseError) as e:
        print(e)
    finally:
        if conn:
            conn.close()

from psycopg2 import connect, DatabaseError
from config import config


def create_tables() -> None:
    # write queries to create tables
    queries = (
        """CREATE TABLE users (
            id SERIAL PRIMARY KEY NOT NULL,
            username VARCHAR(255) NOT NULL,
            hash VARCHAR(255) NOT NULL
        );""",
        """CREATE TABLE projects (
            id SERIAL PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            task VARCHAR(255) NOT NULL,
            deadline VARCHAR(255) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE
        );""",
        """CREATE TABLE today (
            id SERIAL PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            task VARCHAR(255) NOT NULL,
            priority VARCHAR(255),
            FOREIGN KEY (user_id) REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE
        );""",
        """CREATE TABLE mail (
            id SERIAL PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            email VARCHAR(255) NOT NULL,
            message VARCHAR(255) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE
        );""",
        """CREATE TABLE personal (
            id SERIAL PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            task VARCHAR(255) NOT NULL,
            deadline VARCHAR(255) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE
        );""",
        """CREATE TABLE work (
            id SERIAL PRIMARY KEY NOT NULL,
            user_id INTEGER NOT NULL,
            task VARCHAR(255) NOT NULL,
            deadline VARCHAR(255) NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON UPDATE CASCADE ON DELETE CASCADE
        );""",
    )

    # attempt query
    try:
        # collect database params
        params = config()
        # create connection
        conn = connect(**params)
        # create cursor context manager & execute
        with conn:
            with conn.cursor() as cur:
                for query in queries:
                    cur.execute(query)
                conn.commit()
    # handle exceptions
    except (Exception, DatabaseError) as e:
        print(e)
    # close connection
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    create_tables()

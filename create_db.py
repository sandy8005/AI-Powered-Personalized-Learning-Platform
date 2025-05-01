import mysql.connector
from decouple import config

def check_and_create_database():
    # MySQL connection details from .env
    host = config('DB_HOST', default='localhost')
    user = config('DB_USER')
    password = config('DB_PASSWORD')
    db_name = config('DB_NAME')
    port = config('DB_PORT', default='3306')

    try:
        # Connect to MySQL server without specifying the database
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            port=port
        )

        cursor = connection.cursor()

        # Check if the database exists
        cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
        result = cursor.fetchone()

        if not result:
            # If the database doesn't exist, create it
            print(f"Database '{db_name}' does not exist. Creating it...")
            cursor.execute(f"CREATE DATABASE {db_name}")
            print(f"Database '{db_name}' created successfully.")
        else:
            print(f"Database '{db_name}' already exists.")
        
        # Close the cursor and connection
        cursor.close()
        connection.close()

    except mysql.connector.Error as e:
        print(f"Error: {e}")
        raise

if __name__ == "__main__":
    check_and_create_database()

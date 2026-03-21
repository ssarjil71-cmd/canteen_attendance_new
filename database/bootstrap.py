import mysql.connector

from config import Config


def _table_exists(cursor, table_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLES
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
        """,
        (Config.DB_NAME, table_name),
    )
    return cursor.fetchone()[0] > 0


def _column_exists(cursor, table_name, column_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND COLUMN_NAME = %s
        """,
        (Config.DB_NAME, table_name, column_name),
    )
    return cursor.fetchone()[0] > 0


def _index_exists(cursor, table_name, index_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.STATISTICS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND INDEX_NAME = %s
        """,
        (Config.DB_NAME, table_name, index_name),
    )
    return cursor.fetchone()[0] > 0


def _constraint_exists(cursor, table_name, constraint_name):
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM information_schema.TABLE_CONSTRAINTS
        WHERE CONSTRAINT_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s
        """,
        (Config.DB_NAME, table_name, constraint_name),
    )
    return cursor.fetchone()[0] > 0


def _foreign_key_exists_for_column(cursor, table_name, column_name):
        cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.KEY_COLUMN_USAGE
                WHERE TABLE_SCHEMA = %s
                    AND TABLE_NAME = %s
                    AND COLUMN_NAME = %s
                    AND REFERENCED_TABLE_NAME IS NOT NULL
                """,
                (Config.DB_NAME, table_name, column_name),
        )
        return cursor.fetchone()[0] > 0


def _ensure_core_tables(connection):
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            company_code VARCHAR(80) NOT NULL,
            address VARCHAR(255) NULL,
            email VARCHAR(150) NOT NULL,
            password VARCHAR(255) NOT NULL,
            attendance_module_enabled TINYINT(1) NOT NULL DEFAULT 1,
            canteen_module_enabled TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            full_name VARCHAR(150) NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS managers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            full_name VARCHAR(150) NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            company_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS canteen (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            full_name VARCHAR(150) NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            company_id INT NOT NULL UNIQUE,
            created_by_manager_id INT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS employees (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            emp_id VARCHAR(100) UNIQUE NOT NULL,
            gender ENUM('Male', 'Female', 'Other') NOT NULL,
            dob DATE NOT NULL,
            company VARCHAR(255) NOT NULL,
            role VARCHAR(255) NOT NULL,
            department VARCHAR(255) NOT NULL,
            shift ENUM('Morning', 'Afternoon', 'Night') NOT NULL,
            joining_date DATE NOT NULL,
            photo VARCHAR(500),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS contractors (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            company VARCHAR(255) NOT NULL,
            phone VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    cursor.close()


def _apply_schema_updates(connection):
    cursor = connection.cursor()

    if _column_exists(cursor, "companies", "name") and not _column_exists(cursor, "companies", "company_name"):
        cursor.execute("ALTER TABLE companies ADD COLUMN company_name VARCHAR(255) NULL")
        cursor.execute("UPDATE companies SET company_name = name WHERE company_name IS NULL OR company_name = ''")

    if not _column_exists(cursor, "companies", "company_name"):
        cursor.execute("ALTER TABLE companies ADD COLUMN company_name VARCHAR(255) NULL")
    if not _column_exists(cursor, "companies", "company_code"):
        cursor.execute("ALTER TABLE companies ADD COLUMN company_code VARCHAR(80) NULL")
    if not _column_exists(cursor, "companies", "address"):
        cursor.execute("ALTER TABLE companies ADD COLUMN address VARCHAR(255) NULL")
    if not _column_exists(cursor, "companies", "email"):
        cursor.execute("ALTER TABLE companies ADD COLUMN email VARCHAR(150) NULL")
    if not _column_exists(cursor, "companies", "password"):
        cursor.execute("ALTER TABLE companies ADD COLUMN password VARCHAR(255) NULL")
    if not _column_exists(cursor, "companies", "attendance_module_enabled"):
        cursor.execute("ALTER TABLE companies ADD COLUMN attendance_module_enabled TINYINT(1) NOT NULL DEFAULT 1")
    if not _column_exists(cursor, "companies", "canteen_module_enabled"):
        cursor.execute("ALTER TABLE companies ADD COLUMN canteen_module_enabled TINYINT(1) NOT NULL DEFAULT 1")

    cursor.execute("UPDATE companies SET company_name = CONCAT('Company ', id) WHERE company_name IS NULL OR company_name = ''")
    cursor.execute("UPDATE companies SET company_code = CONCAT('CMP-', id) WHERE company_code IS NULL OR company_code = ''")
    cursor.execute("UPDATE companies SET email = CONCAT('company', id, '@example.com') WHERE email IS NULL OR email = ''")
    cursor.execute("UPDATE companies SET password = company_code WHERE password IS NULL OR password = ''")

    cursor.execute(
        """
        ALTER TABLE companies
        MODIFY company_name VARCHAR(255) NOT NULL,
        MODIFY company_code VARCHAR(80) NOT NULL,
        MODIFY email VARCHAR(150) NOT NULL,
        MODIFY password VARCHAR(255) NOT NULL
        """
    )

    if not _index_exists(cursor, "companies", "uk_companies_company_code"):
        cursor.execute("ALTER TABLE companies ADD UNIQUE KEY uk_companies_company_code (company_code)")
    if not _index_exists(cursor, "companies", "uk_companies_email"):
        cursor.execute("ALTER TABLE companies ADD UNIQUE KEY uk_companies_email (email)")

    if _column_exists(cursor, "managers", "name") and not _column_exists(cursor, "managers", "full_name"):
        cursor.execute("ALTER TABLE managers ADD COLUMN full_name VARCHAR(150) NULL")
        cursor.execute("UPDATE managers SET full_name = name WHERE full_name IS NULL OR full_name = ''")
    if not _column_exists(cursor, "managers", "full_name"):
        cursor.execute("ALTER TABLE managers ADD COLUMN full_name VARCHAR(150) NULL")

    if _table_exists(cursor, "users"):
        if not _column_exists(cursor, "users", "full_name"):
            cursor.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(150) NULL")
        if not _column_exists(cursor, "users", "email"):
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(150) NULL")

        cursor.execute("UPDATE users SET email = CONCAT(username, '@example.com') WHERE email IS NULL OR email = ''")
        cursor.execute("UPDATE users SET full_name = 'System Admin' WHERE role = 'admin' AND (full_name IS NULL OR full_name = '')")

        cursor.execute(
            """
            INSERT IGNORE INTO admins (username, full_name, email, password, created_at)
            SELECT username, full_name, email, password, created_at
            FROM users
            WHERE role = 'admin'
            """
        )

        cursor.execute(
            """
            UPDATE admins a
            JOIN users u ON u.username = a.username AND u.role = 'admin'
            SET a.full_name = u.full_name, a.email = u.email, a.password = u.password
            """
        )

        cursor.execute(
            """
            INSERT IGNORE INTO managers (username, full_name, email, password, company_id, created_at)
            SELECT username, full_name, email, password, company_id, created_at
            FROM users
            WHERE role = 'manager' AND company_id IS NOT NULL
            """
        )

        cursor.execute(
            """
            UPDATE managers m
            JOIN users u ON u.username = m.username AND u.role = 'manager'
            SET m.full_name = u.full_name, m.email = u.email, m.password = u.password, m.company_id = u.company_id
            """
        )

        cursor.execute("DROP TABLE users")

    if not _foreign_key_exists_for_column(cursor, "managers", "company_id"):
        cursor.execute(
            """
            ALTER TABLE managers
            ADD CONSTRAINT fk_managers_company
            FOREIGN KEY (company_id) REFERENCES companies(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
            """
        )

    if not _foreign_key_exists_for_column(cursor, "canteen", "company_id"):
        cursor.execute(
            """
            ALTER TABLE canteen
            ADD CONSTRAINT fk_canteen_company
            FOREIGN KEY (company_id) REFERENCES companies(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
            """
        )

    if not _foreign_key_exists_for_column(cursor, "canteen", "created_by_manager_id"):
        cursor.execute(
            """
            ALTER TABLE canteen
            ADD CONSTRAINT fk_canteen_created_by_manager
            FOREIGN KEY (created_by_manager_id) REFERENCES managers(id)
            ON DELETE SET NULL
            ON UPDATE CASCADE
            """
        )

    cursor.execute(
        """
        INSERT INTO admins (username, full_name, email, password)
        VALUES ('admin', 'System Admin', 'admin@system.local', 'admin123')
        ON DUPLICATE KEY UPDATE full_name = VALUES(full_name)
        """
    )

    connection.commit()
    cursor.close()


def ensure_database_ready():
    if not Config.AUTO_DB_SETUP:
        return True

    try:
        server_connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
        )
        server_cursor = server_connection.cursor()
        server_cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME}")
        server_connection.commit()
        server_cursor.close()
        server_connection.close()

        db_connection = mysql.connector.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
        )
        _ensure_core_tables(db_connection)
        _apply_schema_updates(db_connection)
        db_connection.close()
        return True

    except mysql.connector.Error as err:
        print(f"❌ Database bootstrap failed: {err}")
        return False

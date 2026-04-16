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
        CREATE TABLE IF NOT EXISTS company_types (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type_name VARCHAR(120) NOT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_company_types_type_name (type_name)
        )
        """
    )

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
        CREATE TABLE IF NOT EXISTS canteen (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(80) NOT NULL UNIQUE,
            full_name VARCHAR(150) NULL,
            phone VARCHAR(20) NULL,
            email VARCHAR(150) NOT NULL UNIQUE,
            password VARCHAR(255) NOT NULL,
            company_id INT NOT NULL UNIQUE,
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
            gender ENUM('Male', 'Female', 'Other') NULL,
            dob DATE NULL,
            company VARCHAR(255) NOT NULL,
            role VARCHAR(255) NOT NULL,
            department VARCHAR(100) NOT NULL DEFAULT 'General',
            shift VARCHAR(100) NOT NULL DEFAULT 'General',
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            company_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_departments_name_company (name, company_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS shifts (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            start_time TIME NOT NULL,
            end_time TIME NOT NULL,
            company_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_shifts_name_company (name, company_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS roles (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            description TEXT NULL,
            permissions TEXT NULL,
            company_id INT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_roles_name_company (name, company_id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS canteen_menus (
            id INT AUTO_INCREMENT PRIMARY KEY,
            canteen_id INT NOT NULL,
            menu_date DATE NOT NULL,
            morning_item VARCHAR(255) NOT NULL,
            afternoon_item VARCHAR(255) NOT NULL,
            evening_item VARCHAR(255) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_canteen_menu_date (canteen_id, menu_date),
            CONSTRAINT fk_canteen_menu_canteen FOREIGN KEY (canteen_id) REFERENCES canteen(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS meal_responses (
            id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id VARCHAR(100) NOT NULL,
            canteen_id INT NOT NULL,
            response_date DATE NOT NULL,
            status ENUM('Coming', 'Not Coming') NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_meal_response_daily (employee_id, canteen_id, response_date),
            INDEX idx_meal_response_canteen_date (canteen_id, response_date),
            CONSTRAINT fk_meal_response_canteen FOREIGN KEY (canteen_id) REFERENCES canteen(id) ON DELETE CASCADE
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
    if not _column_exists(cursor, "companies", "salary_slip_module_enabled"):
        cursor.execute("ALTER TABLE companies ADD COLUMN salary_slip_module_enabled TINYINT(1) NOT NULL DEFAULT 0")

    # Add additional profile fields
    if not _column_exists(cursor, "companies", "phone"):
        cursor.execute("ALTER TABLE companies ADD COLUMN phone VARCHAR(20) NULL")
    if not _column_exists(cursor, "companies", "city"):
        cursor.execute("ALTER TABLE companies ADD COLUMN city VARCHAR(100) NULL")
    if not _column_exists(cursor, "companies", "state"):
        cursor.execute("ALTER TABLE companies ADD COLUMN state VARCHAR(100) NULL")
    if not _column_exists(cursor, "companies", "pincode"):
        cursor.execute("ALTER TABLE companies ADD COLUMN pincode VARCHAR(10) NULL")
    if not _column_exists(cursor, "companies", "logo"):
        cursor.execute("ALTER TABLE companies ADD COLUMN logo VARCHAR(255) NULL")
    if not _column_exists(cursor, "companies", "gst_number"):
        cursor.execute("ALTER TABLE companies ADD COLUMN gst_number VARCHAR(50) NULL")
    if not _column_exists(cursor, "companies", "status"):
        cursor.execute("ALTER TABLE companies ADD COLUMN status ENUM('active', 'inactive') DEFAULT 'active'")
    if not _column_exists(cursor, "companies", "latitude"):
        cursor.execute("ALTER TABLE companies ADD COLUMN latitude DECIMAL(10, 8) NULL")
    if not _column_exists(cursor, "companies", "longitude"):
        cursor.execute("ALTER TABLE companies ADD COLUMN longitude DECIMAL(11, 8) NULL")
    if not _column_exists(cursor, "companies", "radius"):
        cursor.execute("ALTER TABLE companies ADD COLUMN radius INT DEFAULT 100")
    if not _column_exists(cursor, "companies", "company_type_id"):
        cursor.execute("ALTER TABLE companies ADD COLUMN company_type_id INT NULL")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_types (
            id INT AUTO_INCREMENT PRIMARY KEY,
            type_name VARCHAR(120) NOT NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_company_types_type_name (type_name)
        )
        """
    )

    cursor.execute("SELECT COUNT(*) FROM company_types")
    has_company_types = cursor.fetchone()[0] > 0
    if not has_company_types:
        default_company_types = ["Startup", "Partnership", "Private Limited", "Public Limited", "LLP"]
        for company_type_name in default_company_types:
            cursor.execute(
                """
                INSERT INTO company_types (type_name, is_active)
                VALUES (%s, 1)
                """,
                (company_type_name,),
            )

    if not _index_exists(cursor, "companies", "idx_companies_company_type_id"):
        cursor.execute("ALTER TABLE companies ADD INDEX idx_companies_company_type_id (company_type_id)")

    if not _foreign_key_exists_for_column(cursor, "companies", "company_type_id"):
        cursor.execute(
            """
            ALTER TABLE companies
            ADD CONSTRAINT fk_companies_company_type
            FOREIGN KEY (company_type_id) REFERENCES company_types(id)
            ON DELETE SET NULL
            ON UPDATE CASCADE
            """
        )
    # Add face capture and location fields to employees table
    if not _column_exists(cursor, "employees", "face_image"):
        cursor.execute("ALTER TABLE employees ADD COLUMN face_image VARCHAR(500) NULL")
    if not _column_exists(cursor, "employees", "image_path"):
        cursor.execute("ALTER TABLE employees ADD COLUMN image_path VARCHAR(255) NULL")
    if not _column_exists(cursor, "employees", "face_encoding"):
        cursor.execute("ALTER TABLE employees ADD COLUMN face_encoding TEXT NULL")
    if not _column_exists(cursor, "employees", "registration_latitude"):
        cursor.execute("ALTER TABLE employees ADD COLUMN registration_latitude DECIMAL(10, 8) NULL")
    if not _column_exists(cursor, "employees", "registration_longitude"):
        cursor.execute("ALTER TABLE employees ADD COLUMN registration_longitude DECIMAL(11, 8) NULL")
    if not _column_exists(cursor, "employees", "registration_location_verified"):
        cursor.execute("ALTER TABLE employees ADD COLUMN registration_location_verified TINYINT(1) DEFAULT 0")

    # Create attendance table
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id VARCHAR(100) NOT NULL,
            company_id INT NOT NULL,
            date DATE NOT NULL,
            check_in_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            check_out_time TIMESTAMP NULL,
            face_image VARCHAR(500) NULL,
            latitude DECIMAL(10, 8) NULL,
            longitude DECIMAL(11, 8) NULL,
            location_verified TINYINT(1) DEFAULT 0,
            face_verified TINYINT(1) DEFAULT 0,
            status ENUM('present', 'absent', 'late') DEFAULT 'present',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_employee_date (employee_id, date),
            INDEX idx_company_date (company_id, date),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
        """
    )

    cursor.execute("UPDATE companies SET company_name = CONCAT('Company ', id) WHERE company_name IS NULL OR company_name = ''")
    cursor.execute("UPDATE companies SET email = CONCAT('company', id, '@example.com') WHERE email IS NULL OR email = ''")
    cursor.execute("UPDATE companies SET password = COALESCE(company_code, CONCAT('CMP-', id)) WHERE password IS NULL OR password = ''")

    cursor.execute(
        """
        ALTER TABLE companies
        MODIFY company_name VARCHAR(255) NOT NULL,
        MODIFY company_code VARCHAR(80) NULL,
        MODIFY email VARCHAR(150) NOT NULL,
        MODIFY password VARCHAR(255) NOT NULL
        """
    )

    if not _index_exists(cursor, "companies", "uk_companies_company_code"):
        cursor.execute("ALTER TABLE companies ADD UNIQUE KEY uk_companies_company_code (company_code)")
    if not _index_exists(cursor, "companies", "uk_companies_email"):
        cursor.execute("ALTER TABLE companies ADD UNIQUE KEY uk_companies_email (email)")

    if _table_exists(cursor, "users"):
        if not _column_exists(cursor, "users", "full_name"):
            cursor.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(150) NULL")
        if not _column_exists(cursor, "users", "email"):
            cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(150) NULL")

        cursor.execute("UPDATE users SET email = CONCAT(username, '@example.com') WHERE email IS NULL OR email = ''")
        cursor.execute("UPDATE users SET full_name = 'System Admin' WHERE role = 'admin' AND (full_name IS NULL OR full_name = '')")

        cursor.execute(
            """
            INSERT INTO admins (username, full_name, email, password, created_at)
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

        cursor.execute("DROP TABLE users")

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

    # Add foreign key constraints for departments and shifts
    if not _foreign_key_exists_for_column(cursor, "departments", "company_id"):
        cursor.execute(
            """
            ALTER TABLE departments
            ADD CONSTRAINT fk_departments_company
            FOREIGN KEY (company_id) REFERENCES companies(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
            """
        )

    if not _foreign_key_exists_for_column(cursor, "shifts", "company_id"):
        cursor.execute(
            """
            ALTER TABLE shifts
            ADD CONSTRAINT fk_shifts_company
            FOREIGN KEY (company_id) REFERENCES companies(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
            """
        )

    # Add foreign key constraint for roles
    if not _foreign_key_exists_for_column(cursor, "roles", "company_id"):
        cursor.execute(
            """
            ALTER TABLE roles
            ADD CONSTRAINT fk_roles_company
            FOREIGN KEY (company_id) REFERENCES companies(id)
            ON DELETE CASCADE
            ON UPDATE CASCADE
            """
        )

    # Add company_id to employees table
    if not _column_exists(cursor, "employees", "company_id"):
        cursor.execute("ALTER TABLE employees ADD COLUMN company_id INT NULL")
    
    # Add employee_role column
    if not _column_exists(cursor, "employees", "employee_role"):
        cursor.execute("ALTER TABLE employees ADD COLUMN employee_role VARCHAR(50) NULL")
    
    # Update employees table to use proper department and shift references
    if not _column_exists(cursor, "employees", "email"):
        cursor.execute("ALTER TABLE employees ADD COLUMN email VARCHAR(150) NULL")
    if not _column_exists(cursor, "employees", "phone"):
        cursor.execute("ALTER TABLE employees ADD COLUMN phone VARCHAR(20) NULL")
    if not _column_exists(cursor, "employees", "address"):
        cursor.execute("ALTER TABLE employees ADD COLUMN address TEXT NULL")
    if not _column_exists(cursor, "employees", "status"):
        cursor.execute("ALTER TABLE employees ADD COLUMN status ENUM('pending', 'registered', 'active', 'inactive') DEFAULT 'pending'")
    
    # Fix shift column to allow custom shift names instead of ENUM
    cursor.execute("DESCRIBE employees")
    columns = cursor.fetchall()
    shift_column_info = None
    for column in columns:
        if column[0] == 'shift':
            shift_column_info = column
            break
    
    # If shift column exists and is ENUM, change it to VARCHAR
    if shift_column_info and 'enum' in shift_column_info[1].lower():
        cursor.execute("ALTER TABLE employees MODIFY COLUMN shift VARCHAR(100) NOT NULL DEFAULT 'General'")
    
    # If shift column doesn't exist, add it as VARCHAR
    if not _column_exists(cursor, "employees", "shift"):
        cursor.execute("ALTER TABLE employees ADD COLUMN shift VARCHAR(100) NOT NULL DEFAULT 'General'")
    
    # Also fix department column to be VARCHAR if it's not already
    cursor.execute("DESCRIBE employees")
    columns = cursor.fetchall()
    department_column_info = None
    for column in columns:
        if column[0] == 'department':
            department_column_info = column
            break
    
    if department_column_info and 'varchar' not in department_column_info[1].lower():
        cursor.execute("ALTER TABLE employees MODIFY COLUMN department VARCHAR(100) NOT NULL DEFAULT 'General'")
    
    # Fix gender and dob columns to allow NULL values
    cursor.execute("ALTER TABLE employees MODIFY COLUMN gender ENUM('Male', 'Female', 'Other') NULL")
    cursor.execute("ALTER TABLE employees MODIFY COLUMN dob DATE NULL")
    
    # Remove manager-related functionality
    # First drop foreign key constraints that reference managers table
    if _constraint_exists(cursor, "canteen", "fk_canteen_created_by_manager"):
        cursor.execute("ALTER TABLE canteen DROP FOREIGN KEY fk_canteen_created_by_manager")
    
    if _constraint_exists(cursor, "employees", "fk_employees_manager"):
        cursor.execute("ALTER TABLE employees DROP FOREIGN KEY fk_employees_manager")
    
    # Remove manager_id column from employees if it exists
    if _column_exists(cursor, "employees", "manager_id"):
        cursor.execute("ALTER TABLE employees DROP COLUMN manager_id")
    
    # Remove created_by_manager_id column from canteen if it exists
    if _column_exists(cursor, "canteen", "created_by_manager_id"):
        cursor.execute("ALTER TABLE canteen DROP COLUMN created_by_manager_id")

    if not _column_exists(cursor, "canteen", "phone"):
        cursor.execute("ALTER TABLE canteen ADD COLUMN phone VARCHAR(20) NULL AFTER full_name")
    
    # Now drop the managers table
    if _table_exists(cursor, "managers"):
        cursor.execute("DROP TABLE IF EXISTS managers")
    
    # Add foreign key constraint for employees
    if not _foreign_key_exists_for_column(cursor, "employees", "company_id"):
        cursor.execute(
            """
            ALTER TABLE employees
            ADD CONSTRAINT fk_employees_company
            FOREIGN KEY (company_id) REFERENCES companies(id)
            ON DELETE CASCADE
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


-- MySQL table for employees (with photo, gender, shift)
CREATE TABLE IF NOT EXISTS employees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    emp_id VARCHAR(50) NOT NULL UNIQUE,
    gender VARCHAR(20) NOT NULL,
    dob DATE NOT NULL,
    company VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL,
    department VARCHAR(50) NOT NULL,
    shift VARCHAR(20) NOT NULL,
    joining_date DATE NOT NULL,
    photo VARCHAR(255) NOT NULL
);

-- MySQL table for contractors
CREATE TABLE IF NOT EXISTS contractors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    company VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL
);

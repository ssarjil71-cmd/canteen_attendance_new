-- Employee Self Registration Requests Table
CREATE TABLE IF NOT EXISTS employee_requests (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    emp_id VARCHAR(100) NOT NULL,
    email VARCHAR(150) NULL,
    phone VARCHAR(20) NULL,
    gender ENUM('Male', 'Female', 'Other') NULL,
    dob DATE NULL,
    address TEXT NULL,
    company_id INT NOT NULL,
    status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending',
    rejection_reason TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    approved_at TIMESTAMP NULL,
    approved_by INT NULL,
    INDEX idx_company_status (company_id, status),
    INDEX idx_emp_id (emp_id),
    CONSTRAINT fk_employee_requests_company FOREIGN KEY (company_id) 
        REFERENCES companies(id) ON DELETE CASCADE
);

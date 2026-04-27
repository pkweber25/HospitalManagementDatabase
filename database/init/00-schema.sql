-- ============================================================
--  CareFlow — Hospital Management System
--  00-schema.sql  |  Full database schema
--
--  Key design decisions:
--   • InsuranceProvider stores a CoveragePercent (randomised in
--     sample data) so billing math is self-contained.
--   • BillingRecord is linked to Patient AND Appointment and
--     carries TotalCost, InsuranceCoverage, AmountOwed,
--     PaymentStatus, PaymentMethod, and audit timestamps.
--   • A stored procedure (generate_billing) auto-creates a
--     BillingRecord whenever treatments are added to an appt.
--   • Treatment.AppointmentID added so each treatment ties
--     directly to an appointment (not just via Diagnosis).
-- ============================================================

CREATE DATABASE IF NOT EXISTS hospital_system
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE hospital_system;

-- ── 1. Department ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Department (
    DepartmentID   INT          PRIMARY KEY,
    DepartmentName VARCHAR(50)  NOT NULL,
    Location       VARCHAR(100),
    Phone          VARCHAR(15)
) ENGINE=InnoDB;

-- ── 2. InsuranceProvider ────────────────────────────────────
--  CoveragePercent: the fraction (0.00–1.00) the provider pays.
--  Stored here so billing can look it up without hard-coding.
CREATE TABLE IF NOT EXISTS InsuranceProvider (
    ProviderID       INT           PRIMARY KEY,
    ProviderName     VARCHAR(50)   NOT NULL,
    ContactPhone     VARCHAR(15),
    ContactEmail     VARCHAR(100),
    Address          VARCHAR(100),
    CoveragePercent  DECIMAL(5,4)  NOT NULL DEFAULT 0.7000
        COMMENT 'Fraction covered by insurance, e.g. 0.8000 = 80%'
) ENGINE=InnoDB;

-- ── 3. Patient ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Patient (
    PatientID  INT          PRIMARY KEY,
    FirstName  VARCHAR(50)  NOT NULL,
    LastName   VARCHAR(50)  NOT NULL,
    DOB        DATE,
    Gender     VARCHAR(10),
    Phone      VARCHAR(15),
    Address    VARCHAR(100),
    ProviderID INT,
    FOREIGN KEY (ProviderID) REFERENCES InsuranceProvider(ProviderID)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 4. Doctor ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Doctor (
    DoctorID     INT         PRIMARY KEY,
    FirstName    VARCHAR(50) NOT NULL,
    LastName     VARCHAR(50) NOT NULL,
    Specialty    VARCHAR(50),
    Phone        VARCHAR(15),
    DepartmentID INT,
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 5. Nurse ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Nurse (
    NurseID      INT         PRIMARY KEY,
    FirstName    VARCHAR(50) NOT NULL,
    LastName     VARCHAR(50) NOT NULL,
    Certification VARCHAR(50),
    Phone        VARCHAR(15),
    DepartmentID INT,
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 6. HospitalAdmin ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS HospitalAdmin (
    AdminID   INT          PRIMARY KEY,
    FirstName VARCHAR(50)  NOT NULL,
    LastName  VARCHAR(50)  NOT NULL,
    Email     VARCHAR(100),
    Role      VARCHAR(50)
) ENGINE=InnoDB;

-- ── 7. Appointment ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Appointment (
    AppointmentID   INT         PRIMARY KEY,
    PatientID       INT,
    DoctorID        INT,
    NurseID         INT,
    AppointmentDate DATE,
    AppointmentTime TIME,
    Status          VARCHAR(30) DEFAULT 'Scheduled',
    Purpose         VARCHAR(100),
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (DoctorID)  REFERENCES Doctor(DoctorID)
        ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (NurseID)   REFERENCES Nurse(NurseID)
        ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 8. Diagnosis ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Diagnosis (
    DiagnosisID    INT          PRIMARY KEY,
    AppointmentID  INT,
    DiagnosisName  VARCHAR(100),
    Notes          TEXT,
    DiagnosisDate  DATE,
    FOREIGN KEY (AppointmentID) REFERENCES Appointment(AppointmentID)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 9. Treatment ────────────────────────────────────────────
--  Each treatment links to a Diagnosis AND directly to an
--  Appointment so billing queries don't need an extra join
--  through Diagnosis.
CREATE TABLE IF NOT EXISTS Treatment (
    TreatmentID    INT            PRIMARY KEY,
    DiagnosisID    INT,
    AppointmentID  INT            NOT NULL
        COMMENT 'Denormalised shortcut for billing — same appt as the Diagnosis',
    TreatmentName  VARCHAR(100),
    Description    TEXT,
    TreatmentCost  DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    FOREIGN KEY (DiagnosisID)   REFERENCES Diagnosis(DiagnosisID)
        ON DELETE SET NULL ON UPDATE CASCADE,
    FOREIGN KEY (AppointmentID) REFERENCES Appointment(AppointmentID)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 10. BillingRecord ───────────────────────────────────────
--  One record per appointment.  Generated automatically by the
--  stored procedure below when treatments are added.
--
--  AmountOwed is a computed column (MySQL 5.7 compatible formula
--  via the application layer; stored as a plain DECIMAL so older
--  MySQL versions work without generated columns).
--
--  PaymentStatus values:  Unpaid | Partial | Paid | Canceled
--  PaymentMethod  values:  Cash | Card | Insurance | Waived | NULL
CREATE TABLE IF NOT EXISTS BillingRecord (
    BillingID        INT            PRIMARY KEY AUTO_INCREMENT,
    PatientID        INT            NOT NULL,
    AppointmentID    INT            NOT NULL UNIQUE
        COMMENT 'One billing record per appointment',
    TotalCost        DECIMAL(10,2)  NOT NULL DEFAULT 0.00,
    InsuranceCoverage DECIMAL(10,2) NOT NULL DEFAULT 0.00
        COMMENT 'Amount paid by insurance',
    AmountOwed       DECIMAL(10,2)  NOT NULL DEFAULT 0.00
        COMMENT 'TotalCost - InsuranceCoverage; kept in sync by the app/procedure',
    AmountPaid       DECIMAL(10,2)  NOT NULL DEFAULT 0.00
        COMMENT 'Cumulative patient cash payments',
    PaymentStatus    VARCHAR(20)    NOT NULL DEFAULT 'Unpaid'
        COMMENT 'Unpaid | Partial | Paid | Canceled',
    PaymentMethod    VARCHAR(30)             DEFAULT NULL
        COMMENT 'Cash | Card | Insurance | Waived',
    BillingDate      DATE           NOT NULL,
    UpdatedAt        TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (PatientID)     REFERENCES Patient(PatientID)
        ON DELETE CASCADE ON UPDATE CASCADE,
    FOREIGN KEY (AppointmentID) REFERENCES Appointment(AppointmentID)
        ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB;

-- ── 11. Users (auth) ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS Users (
    id            INT          AUTO_INCREMENT PRIMARY KEY,
    username      VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role          VARCHAR(50)  NOT NULL,
    full_name     VARCHAR(255)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- ============================================================
--  STORED PROCEDURE: generate_billing(p_appointment_id)
--
--  Call this after inserting treatments for an appointment.
--  Logic:
--    1. Sum all TreatmentCosts for the appointment.
--    2. Look up the patient's insurance CoveragePercent.
--    3. INSERT or UPDATE a BillingRecord.
--    4. PaymentStatus = 'Canceled' if appointment is Canceled,
--       'Paid' if AmountOwed <= 0, else 'Unpaid'.
-- ============================================================
DROP PROCEDURE IF EXISTS generate_billing;
DELIMITER $$

CREATE PROCEDURE generate_billing(IN p_appt_id INT)
BEGIN
    DECLARE v_patient_id        INT;
    DECLARE v_appt_status       VARCHAR(30);
    DECLARE v_appt_date         DATE;
    DECLARE v_coverage_pct      DECIMAL(5,4);
    DECLARE v_total_cost        DECIMAL(10,2);
    DECLARE v_insurance_amt     DECIMAL(10,2);
    DECLARE v_amount_owed       DECIMAL(10,2);
    DECLARE v_pay_status        VARCHAR(20);
    DECLARE v_existing_paid     DECIMAL(10,2);

    -- Gather appointment details and patient insurance
    SELECT a.PatientID, a.Status, a.AppointmentDate,
           COALESCE(ip.CoveragePercent, 0.70)
      INTO v_patient_id, v_appt_status, v_appt_date, v_coverage_pct
      FROM Appointment a
      JOIN Patient      p  ON p.PatientID  = a.PatientID
      LEFT JOIN InsuranceProvider ip ON ip.ProviderID = p.ProviderID
     WHERE a.AppointmentID = p_appt_id;

    -- Sum treatment costs for this appointment
    SELECT COALESCE(SUM(TreatmentCost), 0.00)
      INTO v_total_cost
      FROM Treatment
     WHERE AppointmentID = p_appt_id;

    -- Calculate coverage
    SET v_insurance_amt = ROUND(v_total_cost * v_coverage_pct, 2);
    SET v_amount_owed   = v_total_cost - v_insurance_amt;

    -- Determine status
    IF v_appt_status = 'Canceled' THEN
        SET v_pay_status = 'Canceled';
    ELSEIF v_amount_owed <= 0 THEN
        SET v_pay_status = 'Paid';
    ELSE
        SET v_pay_status = 'Unpaid';
    END IF;

    -- Preserve any existing patient payment
    SELECT COALESCE(AmountPaid, 0.00)
      INTO v_existing_paid
      FROM BillingRecord
     WHERE AppointmentID = p_appt_id;

    -- Adjust status if partial payment already made
    IF v_existing_paid > 0 AND v_existing_paid < v_amount_owed THEN
        SET v_pay_status = 'Partial';
    ELSEIF v_existing_paid >= v_amount_owed AND v_amount_owed > 0 THEN
        SET v_pay_status = 'Paid';
    END IF;

    -- Upsert the billing record
    INSERT INTO BillingRecord
        (PatientID, AppointmentID, TotalCost, InsuranceCoverage,
         AmountOwed, AmountPaid, PaymentStatus, BillingDate)
    VALUES
        (v_patient_id, p_appt_id, v_total_cost, v_insurance_amt,
         v_amount_owed, COALESCE(v_existing_paid, 0.00), v_pay_status, v_appt_date)
    ON DUPLICATE KEY UPDATE
        TotalCost         = v_total_cost,
        InsuranceCoverage = v_insurance_amt,
        AmountOwed        = v_amount_owed,
        PaymentStatus     = v_pay_status,
        BillingDate       = v_appt_date;
END$$

DELIMITER ;
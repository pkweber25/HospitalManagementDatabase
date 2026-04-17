CREATE DATABASE IF NOT EXISTS hospital_system;
USE hospital_system;

CREATE TABLE IF NOT EXISTS Department (
    DepartmentID INT PRIMARY KEY,
    DepartmentName VARCHAR(50),
    Location VARCHAR(100),
    Phone VARCHAR(15)
);

CREATE TABLE IF NOT EXISTS InsuranceProvider (
    ProviderID INT PRIMARY KEY,
    ProviderName VARCHAR(50),
    ContactPhone VARCHAR(15),
    ContactEmail VARCHAR(100),
    Address VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Patient (
    PatientID INT PRIMARY KEY,
    FirstName VARCHAR(50),
    LastName VARCHAR(50),
    DOB DATE,
    Gender VARCHAR(10),
    Phone VARCHAR(15),
    Address VARCHAR(100),
    ProviderID INT,
    FOREIGN KEY (ProviderID) REFERENCES InsuranceProvider(ProviderID)
);

CREATE TABLE IF NOT EXISTS Doctor (
    DoctorID INT PRIMARY KEY,
    FirstName VARCHAR(50),
    LastName VARCHAR(50),
    Specialty VARCHAR(50),
    Phone VARCHAR(15),
    DepartmentID INT,
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID)
);

CREATE TABLE IF NOT EXISTS Nurse (
    NurseID INT PRIMARY KEY,
    FirstName VARCHAR(50),
    LastName VARCHAR(50),
    Certification VARCHAR(50),
    Phone VARCHAR(15),
    DepartmentID INT,
    FOREIGN KEY (DepartmentID) REFERENCES Department(DepartmentID)
);

CREATE TABLE IF NOT EXISTS HospitalAdmin (
    AdminID INT PRIMARY KEY,
    FirstName VARCHAR(50),
    LastName VARCHAR(50),
    Email VARCHAR(100),
    Role VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS Appointment (
    AppointmentID INT PRIMARY KEY,
    PatientID INT,
    DoctorID INT,
    NurseID INT,
    AppointmentDate DATE,
    AppointmentTime TIME,
    Status VARCHAR(30),
    Purpose VARCHAR(100),
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID),
    FOREIGN KEY (DoctorID) REFERENCES Doctor(DoctorID),
    FOREIGN KEY (NurseID) REFERENCES Nurse(NurseID)
);

CREATE TABLE IF NOT EXISTS Diagnosis (
    DiagnosisID INT PRIMARY KEY,
    AppointmentID INT,
    DiagnosisName VARCHAR(100),
    Notes TEXT,
    DiagnosisDate DATE,
    FOREIGN KEY (AppointmentID) REFERENCES Appointment(AppointmentID)
);

CREATE TABLE IF NOT EXISTS Treatment (
    TreatmentID INT PRIMARY KEY,
    DiagnosisID INT,
    TreatmentName VARCHAR(100),
    Description TEXT,
    TreatmentCost DECIMAL(10,2),
    FOREIGN KEY (DiagnosisID) REFERENCES Diagnosis(DiagnosisID)
);

CREATE TABLE IF NOT EXISTS BillingRecord (
    BillingID INT PRIMARY KEY,
    PatientID INT,
    AppointmentID INT,
    TotalCost DECIMAL(10,2),
    InsuranceCoverage DECIMAL(10,2),
    PaymentStatus VARCHAR(30),
    BillingDate DATE,
    FOREIGN KEY (PatientID) REFERENCES Patient(PatientID),
    FOREIGN KEY (AppointmentID) REFERENCES Appointment(AppointmentID)
);
-- ============================================================
--  CareFlow — Hospital Management System
--  01-sample.sql  |  Seed data
--
--  Run AFTER 00-schema.sql.
--  Order matters because of FK constraints:
--    Department → InsuranceProvider → Patient / Doctor / Nurse
--    → Appointment → Diagnosis → Treatment → BillingRecord
--
--  Insurance CoveragePercent values are realistic but varied:
--    BlueCross 80 %, Aetna 75 %, Medicare 85 %,
--    Cigna 70 %, UnitedHealth 78 %
-- ============================================================

USE hospital_system;

-- ── 1. Departments ──────────────────────────────────────────
INSERT INTO Department (DepartmentID, DepartmentName, Location, Phone) VALUES
(1, 'Cardiology',  'Building A, 2nd Floor',    '555-0101'),
(2, 'Pediatrics',  'Building B, 1st Floor',    '555-0102'),
(3, 'Emergency',   'Main Floor, West Wing',    '555-0103'),
(4, 'Oncology',    'Building A, 3rd Floor',    '555-0104'),
(5, 'Neurology',   'Building C, 1st Floor',    '555-0105');

-- ── 2. Insurance Providers ──────────────────────────────────
--  CoveragePercent: randomised but realistic (0.70 – 0.85)
INSERT INTO InsuranceProvider
    (ProviderID, ProviderName, ContactPhone, ContactEmail, Address, CoveragePercent) VALUES
(1, 'BlueCross Health',   '800-555-0201', 'contact@bluecross.example.com', '100 Health Way, NY',      0.8000),
(2, 'Aetna Secure',       '800-555-0202', 'support@aetna.example.com',     '200 Wellness Blvd, CA',   0.7500),
(3, 'Medicare Standard',  '800-555-0203', 'info@medicare.example.gov',     '300 Fed Ave, DC',         0.8500),
(4, 'Cigna Care',         '800-555-0204', 'claims@cigna.example.com',      '400 Corporate Dr, TX',    0.7000),
(5, 'UnitedHealth Group', '800-555-0205', 'help@uhg.example.com',          '500 Medical Pkwy, MN',    0.7800);

-- ── 3. Doctors ──────────────────────────────────────────────
INSERT INTO Doctor (DoctorID, FirstName, LastName, Specialty, Phone, DepartmentID) VALUES
(1,  'Gregory',  'House',    'Diagnostic Medicine',  '555-0401', 3),
(2,  'Allison',  'Cameron',  'Immunology',           '555-0402', 3),
(3,  'James',    'Wilson',   'Oncology',             '555-0403', 4),
(4,  'Lisa',     'Cuddy',    'Endocrinology',        '555-0404', 2),
(5,  'Derek',    'Shepherd', 'Neurosurgery',         '555-0405', 5),
(6,  'Preston',  'Burke',    'Cardiothoracic',       '555-0406', 1),
(7,  'Cristina', 'Yang',     'Cardiology',           '555-0407', 1),
(8,  'Arizona',  'Robbins',  'Pediatric Surgery',    '555-0408', 2),
(9,  'Amelia',   'Shepherd', 'Neurology',            '555-0409', 5),
(10, 'Owen',     'Hunt',     'Trauma',               '555-0410', 3);

-- ── 4. Nurses ───────────────────────────────────────────────
INSERT INTO Nurse (NurseID, FirstName, LastName, Certification, Phone, DepartmentID) VALUES
(1,  'Carla',   'Espinosa', 'RN',  '555-0501', 3),
(2,  'Abby',    'Lockhart', 'NP',  '555-0502', 3),
(3,  'Sam',     'Taggart',  'RN',  '555-0503', 4),
(4,  'Olivia',  'Benson',   'LPN', '555-0504', 2),
(5,  'Jackie',  'Peyton',   'RN',  '555-0505', 3),
(6,  'Rory',    'Williams', 'CNA', '555-0506', 5),
(7,  'Clara',   'Oswald',   'RN',  '555-0507', 1),
(8,  'Martha',  'Jones',    'NP',  '555-0508', 1),
(9,  'Donna',   'Noble',    'LPN', '555-0509', 4),
(10, 'Rose',    'Tyler',    'CNA', '555-0510', 2);

-- ── 5. Patients ─────────────────────────────────────────────
INSERT INTO Patient (PatientID, FirstName, LastName, DOB, Gender, Phone, Address, ProviderID) VALUES
(1,  'John',    'Doe',      '1985-04-12', 'Male',   '555-0301', '123 Elm St',          1),
(2,  'Jane',    'Smith',    '1990-08-22', 'Female', '555-0302', '456 Oak Ave',         2),
(3,  'Alice',   'Johnson',  '2015-11-05', 'Female', '555-0303', '789 Pine Rd',         1),
(4,  'Bob',     'Williams', '1972-02-15', 'Male',   '555-0304', '321 Maple Dr',        3),
(5,  'Charlie', 'Brown',    '1988-07-04', 'Male',   '555-0305', '111 Cedar Ln',        4),
(6,  'Diana',   'Prince',   '1995-12-01', 'Female', '555-0306', '222 Birch Blvd',      5),
(7,  'Evan',    'Wright',   '1960-01-20', 'Male',   '555-0307', '333 Walnut St',       1),
(8,  'Fiona',   'Gallagher','2001-03-17', 'Female', '555-0308', '444 Ash Ct',          2),
(9,  'George',  'Miller',   '1982-09-09', 'Male',   '555-0309', '555 Cherry Way',      3),
(10, 'Hannah',  'Abbott',   '1998-10-31', 'Female', '555-0310', '666 Spruce Trl',      4),
(11, 'Ian',     'Malcolm',  '1975-05-14', 'Male',   '555-0311', '777 Redwood Rd',      5),
(12, 'Julia',   'Child',    '1955-08-15', 'Female', '555-0312', '888 Willow Dr',       1),
(13, 'Kevin',   'Bacon',    '1968-07-08', 'Male',   '555-0313', '999 Cypress Cir',     2),
(14, 'Laura',   'Dern',     '1980-02-10', 'Female', '555-0314', '101 Aspen Way',       3),
(15, 'Michael', 'Scott',    '1965-03-15', 'Male',   '555-0315', '202 Paper St',        4),
(16, 'Nina',    'Simone',   '1940-02-21', 'Female', '555-0316', '303 Melody Ln',       5),
(17, 'Oscar',   'Isaac',    '1992-11-11', 'Male',   '555-0317', '404 Rebel Base',      1),
(18, 'Paula',   'Abdul',    '1978-06-19', 'Female', '555-0318', '505 Dance Ave',       2),
(19, 'Quincy',  'Jones',    '1950-01-05', 'Male',   '555-0319', '606 Jazz Blvd',       3),
(20, 'Rachel',  'Green',    '1991-05-05', 'Female', '555-0320', '707 Coffee Shop',     4),
(21, 'Sam',     'Gamgee',   '1985-09-22', 'Male',   '555-0321', '808 Shire Rd',        5),
(22, 'Tina',    'Fey',      '1982-12-12', 'Female', '555-0322', '909 Studio Pl',       1),
(23, 'Ursula',  'Buffay',   '1991-05-05', 'Female', '555-0323', '112 Twin St',         2),
(24, 'Victor',  'Hugo',     '1962-04-04', 'Male',   '555-0324', '223 Paris Blvd',      3),
(25, 'Wendy',   'Darling',  '2010-10-10', 'Female', '555-0325', '334 London Ln',       4),
(26, 'Xavier',  'Roberts',  '1977-07-07', 'Male',   '555-0326', '445 Mutant Way',      5),
(27, 'Yara',    'Shahidi',  '2005-02-10', 'Female', '555-0327', '556 Act Ave',         1),
(28, 'Zack',    'Morris',   '1989-08-08', 'Male',   '555-0328', '667 Bayside Ct',      2),
(29, 'Adam',    'Sandler',  '1970-01-01', 'Male',   '555-0329', '778 Comedy Dr',       3),
(30, 'Betty',   'White',    '1930-01-17', 'Female', '555-0330', '889 Golden Rd',       4);

-- ── 6. Appointments ─────────────────────────────────────────
INSERT INTO Appointment
    (AppointmentID, PatientID, DoctorID, NurseID, AppointmentDate,
     AppointmentTime, Status, Purpose) VALUES
(1,  1,  1,  1,  '2026-04-20', '09:00:00', 'Completed',  'Chest pain evaluation'),
(2,  2,  4,  2,  '2026-04-21', '10:30:00', 'Completed',  'Routine physical'),
(3,  3,  2,  1,  '2026-04-21', '13:00:00', 'Completed',  'Vaccination'),
(4,  4,  3,  3,  '2026-04-22', '11:15:00', 'Completed',  'Follow-up consultation'),
(5,  5,  5,  6,  '2026-04-23', '08:00:00', 'Completed',  'Migraine check'),
(6,  6,  6,  7,  '2026-04-24', '09:30:00', 'Completed',  'Heart murmur check'),
(7,  7,  7,  8,  '2026-04-25', '14:00:00', 'Canceled',   'Cholesterol screening'),
(8,  8,  8,  10, '2026-04-26', '10:00:00', 'Completed',  'Broken arm cast removal'),
(9,  9,  9,  6,  '2026-04-27', '11:45:00', 'Completed',  'Seizure observation'),
(10, 10, 10, 1,  '2026-04-28', '08:30:00', 'Completed',  'Laceration stitching'),
(11, 11, 1,  2,  '2026-04-29', '15:00:00', 'Completed',  'Unexplained fever'),
(12, 12, 2,  5,  '2026-04-30', '09:15:00', 'Completed',  'Allergy testing'),
(13, 13, 3,  3,  '2026-05-01', '10:00:00', 'Completed',  'Chemo session'),
(14, 14, 4,  4,  '2026-05-02', '13:30:00', 'Completed',  'Thyroid check'),
(15, 15, 5,  6,  '2026-05-03', '14:45:00', 'Completed',  'Concussion follow-up'),
(16, 16, 6,  7,  '2026-05-04', '08:15:00', 'Canceled',   'ECG test'),
(17, 17, 7,  8,  '2026-05-05', '09:00:00', 'Completed',  'Blood pressure monitor'),
(18, 18, 8,  10, '2026-05-06', '11:00:00', 'Completed',  'Annual pediatric check'),
(19, 19, 9,  6,  '2026-05-07', '15:30:00', 'Completed',  'Nerve conduction study'),
(20, 20, 10, 2,  '2026-05-08', '16:00:00', 'Completed',  'Sprained ankle'),
(21, 21, 1,  1,  '2026-05-09', '10:30:00', 'Completed',  'Fatigue diagnosis'),
(22, 22, 2,  5,  '2026-05-10', '13:15:00', 'Completed',  'Immunodeficiency panel'),
(23, 23, 3,  9,  '2026-05-11', '08:45:00', 'Completed',  'Tumor imaging results'),
(24, 24, 4,  4,  '2026-05-12', '09:30:00', 'Completed',  'Diabetes management'),
(25, 25, 5,  6,  '2026-05-13', '11:15:00', 'Completed',  'Vertigo assessment'),
(26, 26, 6,  7,  '2026-05-14', '14:00:00', 'Completed',  'Palpitations'),
(27, 27, 7,  8,  '2026-05-15', '15:45:00', 'Completed',  'Pre-op clearance'),
(28, 28, 8,  10, '2026-05-16', '10:15:00', 'Canceled',   'Flu symptoms'),
(29, 29, 9,  6,  '2026-05-17', '11:30:00', 'Completed',  'Dementia screening'),
(30, 30, 10, 1,  '2026-05-18', '08:00:00', 'Completed',  'Burn treatment');

-- ── 7. Diagnoses ────────────────────────────────────────────
INSERT INTO Diagnosis
    (DiagnosisID, AppointmentID, DiagnosisName, Notes, DiagnosisDate) VALUES
(1,  1,  'Mild Angina',           'Patient advised to monitor diet.',           '2026-04-20'),
(2,  2,  'Healthy',               'No issues found during physical.',           '2026-04-21'),
(3,  3,  'Vaccinated',            'Routine MMR administered.',                  '2026-04-21'),
(4,  4,  'Benign Cyst',           'No further growth observed.',                '2026-04-22'),
(5,  5,  'Chronic Migraine',      'Prescribed sumatriptan.',                    '2026-04-23'),
(6,  6,  'Heart Murmur',          'Innocent murmur, no action needed.',         '2026-04-24'),
(7,  7,  'Pending',               'Patient canceled.',                          '2026-04-25'),
(8,  8,  'Fractured Radius',      'Healing well, cast removed.',                '2026-04-26'),
(9,  9,  'Epilepsy',              'Adjusted medication dosage.',                '2026-04-27'),
(10, 10, 'Laceration',            '5 stitches applied to left forearm.',        '2026-04-28'),
(11, 11, 'Viral Infection',       'Rest and hydration advised.',                '2026-04-29'),
(12, 12, 'Pollen Allergy',        'Prescribed antihistamines.',                 '2026-04-30'),
(13, 13, 'Lung Cancer Stage II',  'Chemotherapy cycle 3 completed.',            '2026-05-01'),
(14, 14, 'Hypothyroidism',        'Levothyroxine dose increased.',              '2026-05-02'),
(15, 15, 'Mild Concussion',       'Cleared for normal activity.',               '2026-05-03'),
(16, 16, 'Pending',               'Patient canceled.',                          '2026-05-04'),
(17, 17, 'Hypertension',          'Blood pressure slightly elevated.',          '2026-05-05'),
(18, 18, 'Healthy',               'Growth is on track.',                        '2026-05-06'),
(19, 19, 'Carpal Tunnel',         'Referred to physical therapy.',              '2026-05-07'),
(20, 20, 'Grade 2 Sprain',        'RICE protocol recommended.',                 '2026-05-08'),
(21, 21, 'Anemia',                'Iron supplements prescribed.',               '2026-05-09'),
(22, 22, 'Lupus',                 'Routine monitoring, stable.',                '2026-05-10'),
(23, 23, 'Remission',             'Scan shows no new growth.',                  '2026-05-11'),
(24, 24, 'Type 2 Diabetes',       'A1C levels improved.',                       '2026-05-12'),
(25, 25, 'BPPV',                  'Epley maneuver performed.',                  '2026-05-13'),
(26, 26, 'Arrhythmia',            'Holter monitor ordered.',                    '2026-05-14'),
(27, 27, 'Cleared for Surgery',   'All vitals normal.',                         '2026-05-15'),
(28, 28, 'Pending',               'Patient canceled.',                          '2026-05-16'),
(29, 29, 'Early Onset Alzheimer', 'Family counseling recommended.',             '2026-05-17'),
(30, 30, 'Second Degree Burn',    'Dressed and bandaged.',                      '2026-05-18');

-- ── 8. Treatments ───────────────────────────────────────────
--  AppointmentID mirrors the Diagnosis's AppointmentID so the
--  stored procedure can sum costs per appointment directly.
INSERT INTO Treatment
    (TreatmentID, DiagnosisID, AppointmentID, TreatmentName, Description, TreatmentCost) VALUES
(1,  1,  1,  'Diet Plan',            'Consultation with nutritionist.',         150.00),
(2,  2,  2,  'Routine Check',        'Standard physical examination.',          100.00),
(3,  3,  3,  'Vaccine Admin',        'MMR injection administered.',              75.00),
(4,  4,  4,  'Observation',          'No intervention required.',                50.00),
(5,  5,  5,  'Medication',           'Sumatriptan prescription issued.',        120.00),
(6,  6,  6,  'Echocardiogram',       'Ultrasound of the heart.',                300.00),
(7,  7,  7,  'None',                 'Appointment canceled — no treatment.',       0.00),
(8,  8,  8,  'Cast Removal',         'Saw and clean radial cast.',               80.00),
(9,  9,  9,  'EEG',                  'Brain wave monitoring test.',             400.00),
(10, 10, 10, 'Sutures',              'Local anesthesia and 5 stitches.',        250.00),
(11, 11, 11, 'Rest Protocol',        'At-home care and hydration plan.',         50.00),
(12, 12, 12, 'Allergy Panel',        'Skin-prick test battery.',                200.00),
(13, 13, 13, 'Chemotherapy',         'IV drip session, cycle 3.',             1500.00),
(14, 14, 14, 'Blood Panel',          'Thyroid hormone level test.',              90.00),
(15, 15, 15, 'Neurological Exam',    'Reflex, vision, and balance tests.',      110.00),
(16, 16, 16, 'None',                 'Appointment canceled — no treatment.',       0.00),
(17, 17, 17, 'Medication Review',    'Adjusted Lisinopril dosage.',              85.00),
(18, 18, 18, 'Pediatric Exam',       'Standard child wellness check.',          100.00),
(19, 19, 19, 'Nerve Conduction',     'EMG electromyography test.',              350.00),
(20, 20, 20, 'Ankle Bracing',        'Applied supportive ankle brace.',          60.00),
(21, 21, 21, 'Iron Infusion',        'IV iron replacement therapy.',            400.00),
(22, 22, 22, 'Rheumatology Consult', 'Joint examination and assessment.',       180.00),
(23, 23, 23, 'MRI Brain Scan',       'Contrast brain imaging.',               1200.00),
(24, 24, 24, 'Dietary Counseling',   'Diabetic education session.',             130.00),
(25, 25, 25, 'Physical Therapy',     'Vestibular rehabilitation exercises.',    140.00),
(26, 26, 26, 'Holter Monitor',       '24-hour cardiac activity tracking.',      220.00),
(27, 27, 27, 'Pre-Op Panel',         'Full pre-operative blood and ECG.',       260.00),
(28, 28, 28, 'None',                 'Appointment canceled — no treatment.',       0.00),
(29, 29, 29, 'Cognitive Test',       'Standardized memory evaluation.',         175.00),
(30, 30, 30, 'Wound Care',           'Cleaning and silver-sulfadiazine dressing.',190.00);

-- ── 9. Billing Records ──────────────────────────────────────
--  All 26 records consolidated into a single multi-row INSERT
--  for efficiency — eliminates parser overhead and round-trips.
--
--  Insurance amounts per provider CoveragePercent:
--    BlueCross (1) 80 %, Aetna (2) 75 %, Medicare (3) 85 %,
--    Cigna (4) 70 %, UnitedHealth (5) 78 %
--
--  Formula:
--    InsuranceCoverage = ROUND(TotalCost * CoveragePercent, 2)
--    AmountOwed        = TotalCost - InsuranceCoverage
--    PaymentStatus     = Unpaid | Partial | Paid | Canceled
--
--  BillingID is AUTO_INCREMENT; AppointmentID has a UNIQUE
--  constraint preventing duplicate records.
INSERT INTO BillingRecord
    (PatientID, AppointmentID, TotalCost, InsuranceCoverage,
     AmountOwed, AmountPaid, PaymentStatus, PaymentMethod, BillingDate)
VALUES
-- Canceled appointments — $0 cost, no coverage
( 7,  7,    0.00,    0.00,   0.00,   0.00, 'Canceled', NULL,        '2026-04-25'),
(16, 16,    0.00,    0.00,   0.00,   0.00, 'Canceled', NULL,        '2026-05-04'),
(28, 28,    0.00,    0.00,   0.00,   0.00, 'Canceled', NULL,        '2026-05-16'),
-- Patient  1 — BlueCross  80 % — $150.00
( 1,  1,  150.00,  120.00,  30.00,  30.00, 'Paid',     'Card',      '2026-04-20'),
-- Patient  2 — Aetna      75 % — $100.00
( 2,  2,  100.00,   75.00,  25.00,  25.00, 'Paid',     'Cash',      '2026-04-21'),
-- Patient  3 — BlueCross  80 % — $75.00
( 3,  3,   75.00,   60.00,  15.00,  15.00, 'Paid',     'Insurance', '2026-04-21'),
-- Patient  4 — Medicare   85 % — $50.00
( 4,  4,   50.00,   42.50,   7.50,   0.00, 'Unpaid',   NULL,        '2026-04-22'),
-- Patient  5 — Cigna      70 % — $120.00
( 5,  5,  120.00,   84.00,  36.00,  20.00, 'Partial',  'Cash',      '2026-04-23'),
-- Patient  6 — UnitedHealth 78 % — $300.00
( 6,  6,  300.00,  234.00,  66.00,   0.00, 'Unpaid',   NULL,        '2026-04-24'),
-- Patient  8 — Aetna      75 % — $80.00
( 8,  8,   80.00,   60.00,  20.00,  20.00, 'Paid',     'Card',      '2026-04-26'),
-- Patient  9 — Medicare   85 % — $400.00
( 9,  9,  400.00,  340.00,  60.00,   0.00, 'Unpaid',   NULL,        '2026-04-27'),
-- Patient 10 — Cigna      70 % — $250.00
(10, 10,  250.00,  175.00,  75.00,  75.00, 'Paid',     'Card',      '2026-04-28'),
-- Patient 11 — UnitedHealth 78 % — $50.00
(11, 11,   50.00,   39.00,  11.00,  11.00, 'Paid',     'Cash',      '2026-04-29'),
-- Patient 12 — BlueCross  80 % — $200.00
(12, 12,  200.00,  160.00,  40.00,   0.00, 'Unpaid',   NULL,        '2026-04-30'),
-- Patient 13 — Aetna      75 % — $1500.00 (chemo)
(13, 13, 1500.00, 1125.00, 375.00, 200.00, 'Partial',  'Card',      '2026-05-01'),
-- Patient 14 — Medicare   85 % — $90.00
(14, 14,   90.00,   76.50,  13.50,  13.50, 'Paid',     'Insurance', '2026-05-02'),
-- Patient 15 — Cigna      70 % — $110.00
(15, 15,  110.00,   77.00,  33.00,  33.00, 'Paid',     'Card',      '2026-05-03'),
-- Patient 17 — BlueCross  80 % — $85.00
(17, 17,   85.00,   68.00,  17.00,  17.00, 'Paid',     'Cash',      '2026-05-05'),
-- Patient 18 — Aetna      75 % — $100.00
(18, 18,  100.00,   75.00,  25.00,   0.00, 'Unpaid',   NULL,        '2026-05-06'),
-- Patient 19 — Medicare   85 % — $350.00
(19, 19,  350.00,  297.50,  52.50,  52.50, 'Paid',     'Card',      '2026-05-07'),
-- Patient 20 — Cigna      70 % — $60.00
(20, 20,   60.00,   42.00,  18.00,  10.00, 'Partial',  'Cash',      '2026-05-08'),
-- Patient 21 — UnitedHealth 78 % — $400.00
(21, 21,  400.00,  312.00,  88.00,   0.00, 'Unpaid',   NULL,        '2026-05-09'),
-- Patient 22 — BlueCross  80 % — $180.00
(22, 22,  180.00,  144.00,  36.00,  36.00, 'Paid',     'Card',      '2026-05-10'),
-- Patient 23 — Aetna      75 % — $1200.00 (MRI)
(23, 23, 1200.00,  900.00, 300.00, 150.00, 'Partial',  'Card',      '2026-05-11'),
-- Patient 24 — Medicare   85 % — $130.00
(24, 24,  130.00,  110.50,  19.50,  19.50, 'Paid',     'Insurance', '2026-05-12'),
-- Patient 25 — Cigna      70 % — $140.00
(25, 25,  140.00,   98.00,  42.00,   0.00, 'Unpaid',   NULL,        '2026-05-13'),
-- Patient 26 — UnitedHealth 78 % — $220.00
(26, 26,  220.00,  171.60,  48.40,  48.40, 'Paid',     'Card',      '2026-05-14'),
-- Patient 27 — BlueCross  80 % — $260.00
(27, 27,  260.00,  208.00,  52.00,  52.00, 'Paid',     'Cash',      '2026-05-15'),
-- Patient 29 — Medicare   85 % — $175.00
(29, 29,  175.00,  148.75,  26.25,   0.00, 'Unpaid',   NULL,        '2026-05-17'),
-- Patient 30 — Cigna      70 % — $190.00
(30, 30,  190.00,  133.00,  57.00,  57.00, 'Paid',     'Card',      '2026-05-18');
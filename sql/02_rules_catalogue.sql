TRUNCATE TABLE rule_catalogue CASCADE;

INSERT INTO rule_catalogue
(rule_id, dimension, description, severity, classification, rationale,
 tested_by_injection, injection_rule)
VALUES

-- ============================================================
-- COMPLETENESS
-- ============================================================

('C-001','Completeness',
 'Latitude or longitude is missing.',
 'HIGH','ERROR',
 'Coordinates are required for spatial hazard and accumulation analysis.',
 TRUE,'C1'),

('C-002','Completeness',
 'Construction code is missing.',
 'MEDIUM','ERROR',
 'Construction affects vulnerability classification and loss estimation.',
 TRUE,'C2'),

('C-003','Completeness',
 'Year built is missing.',
 'MEDIUM','ERROR',
 'Building age can affect vulnerability and construction interpretation.',
 TRUE,'C3'),

('C-004','Completeness',
 'Number of storeys is missing.',
 'MEDIUM','ERROR',
 'Storey count can affect vulnerability and exposure interpretation.',
 TRUE,'C4'),

('C-005','Completeness',
 'Contents TIV is missing.',
 'MEDIUM','ERROR',
 'Missing contents exposure can understate total insured value.',
 TRUE,'C5'),

('C-006','Completeness',
 'Deductible is missing.',
 'LOW','ERROR',
 'Deductible information is relevant to policy-level loss calculations.',
 TRUE,'C6'),

('C-007','Completeness',
 'Occupancy code is missing.',
 'HIGH','ERROR',
 'Occupancy is a key vulnerability classification variable.',
 TRUE,'C7'),

-- ============================================================
-- VALIDITY
-- ============================================================

('V-001','Validity',
 'Building TIV is negative.',
 'HIGH','ERROR',
 'Negative insured value is not a valid exposure value.',
 TRUE,'V1'),

('V-002','Validity',
 'Building TIV is exactly zero.',
 'MEDIUM','UNKNOWN',
 'Zero TIV may represent a legitimate non-insured record or a data problem and requires investigation.',
 TRUE,'V2'),

('V-003','Validity',
 'Latitude or longitude is outside its valid geographic range.',
 'HIGH','ERROR',
 'Latitude must lie between -90 and 90 degrees and longitude between -180 and 180 degrees.',
 TRUE,'V3'),

('V-004','Validity',
 'Year built is later than the current calendar year.',
 'HIGH','ERROR',
 'A building cannot normally have a completed construction year in the future; planned construction is an exception requiring review.',
 TRUE,'V4'),

('V-005','Validity',
 'Year built is implausibly early.',
 'MEDIUM','UNKNOWN',
 'Very early construction dates may be legitimate but require investigation rather than automatic correction.',
 TRUE,'V5'),

('V-006','Validity',
 'Number of storeys is zero or negative.',
 'HIGH','ERROR',
 'A building record requires a positive storey count when the field is populated.',
 TRUE,'V6'),

('V-007','Validity',
 'Deductible exceeds building TIV.',
 'HIGH','ERROR',
 'A deductible greater than the relevant insured value is inconsistent with the exposure record.',
 TRUE,'V7'),

-- ============================================================
-- CONSISTENCY
-- ============================================================

('X-001','Consistency',
 'Timber construction is combined with an unusually high storey count.',
 'HIGH','UNKNOWN',
 'The combination is structurally unusual and should be reviewed against source data.',
 TRUE,'X1'),

('X-002','Consistency',
 'RCC construction is combined with an unusually early construction year.',
 'MEDIUM','UNKNOWN',
 'The combination may be legitimate but is sufficiently unusual to require review.',
 TRUE,'X2'),

('X-003','Consistency',
 'Residential occupancy has an exceptionally large building TIV.',
 'HIGH','UNKNOWN',
 'The value may be legitimate but is inconsistent with typical residential exposure patterns.',
 TRUE,'X3'),

('X-004','Consistency',
 'Warehouse occupancy has an unusually high storey count.',
 'MEDIUM','UNKNOWN',
 'The combination is unusual and requires source verification.',
 TRUE,'X4'),

('X-005','Consistency',
 'Floor area is inconsistent with the exposure characteristics.',
 'MEDIUM','UNKNOWN',
 'Floor area should be broadly consistent with TIV and building characteristics.',
 TRUE,'X5'),

('X-006','Consistency',
 'Postcode is inconsistent with the stated district.',
 'HIGH','ERROR',
 'Administrative geography should be internally consistent.',
 TRUE,'X6'),

('X-007','Consistency',
 'City is inconsistent with the supplied coordinates.',
 'HIGH','ERROR',
 'Location attributes should agree with spatial coordinates.',
 TRUE,'X7'),

-- ============================================================
-- DUPLICATION
-- ============================================================

('D-001','Duplication',
 'Exact duplicate exposure record detected.',
 'HIGH','ERROR',
 'Exact duplication can double-count insured exposure.',
 TRUE,'D1'),

('D-002','Duplication',
 'Multiple location IDs share identical coordinates.',
 'MEDIUM','UNKNOWN',
 'Different assets may legitimately share coordinates, especially at coarse geocoding levels.',
 TRUE,'D2'),

('D-003','Duplication',
 'Near-duplicate addresses are present.',
 'MEDIUM','UNKNOWN',
 'Similar addresses may represent duplicates or separate insured locations.',
 TRUE,'D3'),

('D-004','Duplication',
 'Same location ID has conflicting TIV values.',
 'HIGH','ERROR',
 'A location identifier should not represent contradictory exposure values without explanation.',
 TRUE,'D4'),

-- ============================================================
-- PLAUSIBILITY
-- ============================================================

('P-001','Plausibility',
 'Building TIV exceeds the frozen clean-baseline threshold stored in p001_reference.',
 'HIGH','ERROR',
 'Extreme values may indicate unit or scale errors and can materially affect accumulation.',
 TRUE,'P1'),

('P-002','Plausibility',
 'Exactly repeated round TIV value occurs unusually often.',
 'MEDIUM','UNKNOWN',
 'Repeated round values may indicate defaulting, rounding or data-entry problems.',
 TRUE,'P2'),

('P-003','Plausibility',
 'A single location represents an exceptionally large share of portfolio TIV.',
 'HIGH','UNKNOWN',
 'Extreme concentration can materially affect accumulation and should be validated.',
 TRUE,'P3'),

('P-004','Plausibility',
 'Construction year 1900 occurs unusually often.',
 'MEDIUM','UNKNOWN',
 'Repeated 1900 values can indicate a default or missing-value convention.',
 TRUE,'P4'),

('P-005','Plausibility',
 'Industrial records have an unusually uniform storey count.',
 'MEDIUM','UNKNOWN',
 'Uniform values across a heterogeneous occupancy class may indicate defaulting.',
 TRUE,'P5'),

-- ============================================================
-- GEOGRAPHY
-- ============================================================

('G-001','Geography',
 'Exposure coordinate falls outside the land area.',
 'HIGH','ERROR',
 'An insured building should normally be located on land; offshore coordinates require investigation.',
 TRUE,'G1'),

('G-002','Geography',
 'Latitude and longitude appear to have been swapped.',
 'HIGH','ERROR',
 'Swapped coordinates can place an otherwise valid location in the wrong geography.',
 TRUE,'G2'),

('G-003','Geography',
 'Coordinate is exactly 0,0.',
 'HIGH','ERROR',
 'The Gulf of Guinea coordinate is commonly indicative of missing or defaulted geolocation.',
 TRUE,'G3'),

('G-004','Geography',
 'Coordinate falls outside India.',
 'HIGH','ERROR',
 'The project portfolio is defined for the Indian study area.',
 TRUE,'G4'),

('G-005','Geography',
 'Multiple locations are concentrated at postcode centroid coordinates.',
 'MEDIUM','ASSUMPTION',
 'Postcode-level geocoding is a valid representation but introduces spatial concentration that must be documented.',
 TRUE,'G5'),

-- ============================================================
-- CODING
-- ============================================================

('K-001','Coding',
 'Construction code uses an unstandardised free-text variant.',
 'MEDIUM','ERROR',
 'Inconsistent coding can fragment vulnerability classifications.',
 TRUE,'K1'),

('K-002','Coding',
 'Occupancy code falls outside the controlled scheme.',
 'HIGH','ERROR',
 'Unknown occupancy codes cannot be reliably mapped to the vulnerability scheme.',
 TRUE,'K2'),

('K-003','Coding',
 'Multiple coding schemes are mixed within the portfolio.',
 'HIGH','ERROR',
 'Mixed coding systems can produce inconsistent vulnerability classification.',
 TRUE,'K3'),

('K-004','Coding',
 'Currency is inconsistent across records.',
 'HIGH','ERROR',
 'Mixed currencies make portfolio-level TIV and accumulation comparisons unreliable.',
 TRUE,'K4');

 -- ============================================================
-- MATERIALITY AXIS MAPPING
-- ============================================================
--
-- These flags describe which downstream risk dimension can be
-- affected by a rule. They are deliberately maintained in the
-- rule catalogue rather than inferred later in materiality SQL.
--
-- Hazard:
--   Geographic/location errors can alter hazard assignment,
--   spatial exposure placement, or accumulation location.
--
-- Vulnerability:
--   Construction, occupancy, storey count and building-age
--   characteristics can affect vulnerability interpretation.
--
-- Financial:
--   TIV, policy-value, deductible, currency and duplication
--   issues can directly affect financial exposure.
--
-- A rule may affect more than one axis.

UPDATE rule_catalogue
SET affects_hazard = TRUE
WHERE rule_id IN (
    'C-001',
    'V-003',
    'G-001',
    'G-002',
    'G-003',
    'G-004',
    'G-005',
    'X-006',
    'X-007'
);

UPDATE rule_catalogue
SET affects_vulnerability = TRUE
WHERE rule_id IN (
    'C-002',
    'C-003',
    'C-004',
    'C-007',
    'V-004',
    'V-005',
    'V-006',
    'X-001',
    'X-002',
    'X-004',
    'P-004',
    'P-005',
    'K-001',
    'K-002',
    'K-003'
);

UPDATE rule_catalogue
SET affects_financial = TRUE
WHERE rule_id IN (
    'C-005',
    'C-006',
    'V-001',
    'V-002',
    'V-007',
    'X-003',
    'X-005',
    'D-001',
    'D-002',
    'D-003',
    'D-004',
    'P-001',
    'P-002',
    'P-003',
    'K-004'
);


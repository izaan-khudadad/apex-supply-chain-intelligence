-- Run once in MySQL Workbench while connected as root.
-- Replace the password with a new strong password. Do not commit a changed copy.
CREATE USER IF NOT EXISTS 'apex_pipeline'@'localhost'
    IDENTIFIED BY 'REPLACE_WITH_A_NEW_STRONG_PASSWORD';

GRANT SELECT, INSERT, CREATE, DROP, INDEX
    ON apex_supply_chain.* TO 'apex_pipeline'@'localhost';

CREATE DATABASE IF NOT EXISTS banking_system;
USE banking_system;

CREATE TABLE customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(15),
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE accounts (
    account_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    account_type ENUM('Savings', 'Checking', 'Fixed Deposit') NOT NULL,
    account_number VARCHAR(20) UNIQUE NOT NULL,
    balance DECIMAL(15, 2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT,
    transaction_type ENUM('Deposit', 'Withdrawal', 'Transfer') NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    source_account VARCHAR(20),
    destination_account VARCHAR(20),
    transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(account_id)
);

DELIMITER //

CREATE PROCEDURE CreateAccount(
    IN p_customer_id INT,
    IN p_account_type VARCHAR(50),
    IN p_initial_deposit DECIMAL(15, 2),
    OUT p_account_id INT
)
BEGIN
    DECLARE new_account_number VARCHAR(20);
    SET new_account_number = CONCAT('ACC', p_customer_id, UNIX_TIMESTAMP());
    
    INSERT INTO accounts (customer_id, account_type, account_number, balance)
    VALUES (p_customer_id, p_account_type, new_account_number, p_initial_deposit);
    
    SET p_account_id = LAST_INSERT_ID();
    
    INSERT INTO transactions (account_id, transaction_type, amount)
    VALUES (p_account_id, 'Deposit', p_initial_deposit);
END //

CREATE FUNCTION GetAccountBalance(acc_id INT) 
RETURNS DECIMAL(15, 2)
READS SQL DATA
BEGIN
    DECLARE bal DECIMAL(15, 2);
    SELECT balance INTO bal FROM accounts WHERE account_id = acc_id;
    RETURN COALESCE(bal, 0.00);
END //

CREATE TRIGGER before_transaction
BEFORE INSERT ON transactions
FOR EACH ROW
BEGIN
    DECLARE current_balance DECIMAL(15, 2);
    
    IF NEW.transaction_type IN ('Withdrawal', 'Transfer') THEN
        SELECT balance INTO current_balance 
        FROM accounts 
        WHERE account_id = NEW.account_id;
        
        IF current_balance < NEW.amount THEN
            SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Insufficient balance for transaction';
        END IF;
    END IF;
END //

CREATE TRIGGER after_transaction
AFTER INSERT ON transactions
FOR EACH ROW
BEGIN
    IF NEW.transaction_type = 'Deposit' THEN
        UPDATE accounts 
        SET balance = balance + NEW.amount 
        WHERE account_id = NEW.account_id;
        
    ELSEIF NEW.transaction_type IN ('Withdrawal', 'Transfer') THEN
        UPDATE accounts 
        SET balance = balance - NEW.amount 
        WHERE account_id = NEW.account_id;
        
        IF NEW.transaction_type = 'Transfer' AND NEW.destination_account IS NOT NULL THEN
            UPDATE accounts 
            SET balance = balance + NEW.amount 
            WHERE account_number = NEW.destination_account;
        END IF;
    END IF;
END //

DELIMITER ;

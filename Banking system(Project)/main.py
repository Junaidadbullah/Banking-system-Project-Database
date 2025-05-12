from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from functools import wraps
import os
from dotenv import load_dotenv
import time

load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

def get_db_connection():
    return mysql.connector.connect(
        host=os.getenv('DB_HOST'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        database=os.getenv('DB_NAME')
    )

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'customer_id' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO customers (name, email, phone, password) VALUES (%s, %s, %s, %s)",
                         (name, email, phone, hashed_password))
            conn.commit()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except mysql.connector.Error as err:
            flash(f'Registration failed: {err}')
        finally:
            cursor.close()
            conn.close()
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM customers WHERE email = %s", (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['customer_id'] = user['customer_id']
            flash('Logged in successfully!')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')
            
        cursor.close()
        conn.close()
        
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT accounts.account_id, accounts.account_type, accounts.account_number, accounts.balance,
               (SELECT COUNT(*) FROM transactions WHERE transactions.account_id = accounts.account_id) as transaction_count
        FROM accounts 
        WHERE customer_id = %s
    """, (session['customer_id'],))
    
    accounts = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('dashboard.html', accounts=accounts)

@app.route('/create_account', methods=['GET', 'POST'])
@login_required
def create_account():
    if request.method == 'POST':
        account_type = request.form['account_type']
        initial_deposit = float(request.form['initial_deposit'])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            account_number = f"ACC{session['customer_id']}{int(time.time())}"
            cursor.execute("""
                INSERT INTO accounts (customer_id, account_type, account_number, balance) 
                VALUES (%s, %s, %s, %s)
            """, (session['customer_id'], account_type, account_number, initial_deposit))
            
            account_id = cursor.lastrowid
            
            cursor.execute("""
                INSERT INTO transactions (account_id, transaction_type, amount) 
                VALUES (%s, 'Deposit', %s)
            """, (account_id, initial_deposit))
            
            conn.commit()
            flash('Account created successfully!')
            return redirect(url_for('dashboard'))
            
        except mysql.connector.Error as err:
            conn.rollback()
            flash(f'Failed to create account: {err}')
        finally:
            cursor.close()
            conn.close()
            
    return render_template('create_account.html')

@app.route('/transactions/<int:account_id>')
@login_required
def transactions(account_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT t.*, a.account_number 
        FROM transactions t 
        JOIN accounts a ON t.account_id = a.account_id 
        WHERE t.account_id = %s AND a.customer_id = %s 
        ORDER BY transaction_date DESC
    """, (account_id, session['customer_id']))
    
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('transactions.html', transactions=transactions)

@app.route('/transfer', methods=['GET', 'POST'])
@login_required
def transfer():
    if request.method == 'POST':
        source_account = request.form['source_account']
        destination_account = request.form['destination_account']
        amount = float(request.form['amount'])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("START TRANSACTION")
            
            # Check source account balance
            cursor.execute("SELECT balance FROM accounts WHERE account_id = %s", (source_account,))
            balance = cursor.fetchone()[0]
            
            if balance < amount:
                raise Exception("Insufficient balance")
                
            # Create transfer transaction
            cursor.execute("""
                INSERT INTO transactions (account_id, transaction_type, amount, destination_account) 
                VALUES (%s, 'Transfer', %s, %s)
            """, (source_account, amount, destination_account))
            
            conn.commit()
            flash('Transfer successful!')
            return redirect(url_for('dashboard'))
            
        except Exception as err:
            conn.rollback()
            flash(f'Transfer failed: {err}')
        finally:
            cursor.close()
            conn.close()
            
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT account_id, account_number, account_type, balance 
        FROM accounts 
        WHERE customer_id = %s
    """, (session['customer_id'],))
    accounts = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('transfer.html', accounts=accounts)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('home'))

if __name__ == '__main__':
    app.run(debug=True)

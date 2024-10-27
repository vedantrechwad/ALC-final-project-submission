from flask import Flask, Response, flash, render_template, request, session, redirect, url_for
import sqlite3

app = Flask(__name__)
app.secret_key = 'secret_key'

# Database initialization
def init_db():
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            atm_pin TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users (username)
        )
    ''')
    conn.commit()
    conn.close()

# Initialize the database
init_db()

def get_user(username):
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username, password, atm_pin FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    return user

def add_user(username, password, atm_pin):
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO users (username, password, atm_pin) VALUES (?, ?, ?)', (username, password, atm_pin))
    conn.commit()
    conn.close()

def update_balance(username, amount):
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET balance = balance + ? WHERE username = ?', (amount, username))
    conn.commit()
    conn.close()

def get_balance(username):
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE username = ?', (username,))
    balance = cursor.fetchone()[0]
    conn.close()
    return balance

def log_transaction(username, transaction_type, amount):
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO transactions (username, transaction_type, amount) VALUES (?, ?, ?)', (username, transaction_type, amount))
    conn.commit()
    conn.close()

def get_transactions(username):
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('SELECT transaction_type, amount, timestamp FROM transactions WHERE username = ?', (username,))
    transactions = cursor.fetchall()
    conn.close()
    return transactions

def get_all_users():
    conn = sqlite3.connect('atm.db')
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users')
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]  # Extract usernames from tuples

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Admin login check directly with hardcoded admin credentials
        if username == "admin" and password == "admin":
            session['username'] = username
            session['user_name'] = "Admin"  # Set user name as 'Admin' for admin access
            session['is_admin'] = True
            return redirect(url_for('admin'))
        
        # Non-admin user check
        user = get_user(username)
        if user and user[1] == password:  # Check plain text password
            session['username'] = username
            session['user_name'] = username  # Set the username as the displayed name
            session['is_admin'] = False
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid credentials'
    
    return render_template('login.html', error=error)

@app.route('/admin')
def admin():
    if 'username' not in session or not session.get('is_admin', False):
        return redirect(url_for('login'))
    return render_template('admin.html', users=get_all_users())

@app.route('/add_user', methods=['POST'])
def add_user_route():
    if 'username' not in session or not session.get('is_admin', False):
        return redirect(url_for('login'))
    
    username = request.form['username']
    password = request.form['password']
    atm_pin = request.form['atm_pin']
    
    # Check if the username already exists
    if get_user(username):
        flash('User already exists', 'error')  # Use flash for better user feedback
        return redirect(url_for('admin'))  # Redirect back to the admin page after adding

    add_user(username, password, atm_pin)  # Call the function to add the user
    flash('User created successfully!', 'success')  # Notify success
    return redirect(url_for('admin'))  # Redirect back to the admin page after adding

@app.route('/transactions', methods=['GET'])
def transactions():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    transactions = get_transactions(username)  # Fetch transactions for the logged-in user
    return render_template('transactions.html', transactions=transactions)  # Render a transactions template

@app.route('/download_transactions', methods=['GET'])
def download_transactions():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    transactions = get_transactions(username)  # Fetch transactions for the logged-in user

    # Create a CSV response
    def generate():
        yield 'Transaction Type,Amount,Timestamp\n'  # CSV Header
        for transaction in transactions:
            yield f"{transaction[0]},{transaction[1]},{transaction[2]}\n"

    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=transactions.csv"})

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    user_name = session['user_name']  # Fetch the user's name from the session
    balance = get_balance(username)
    transactions = get_transactions(username)
    
    return render_template('dashboard.html', user_name=user_name, balance=balance, transactions=transactions)

@app.route('/deposit', methods=['POST'])
def deposit():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    amount = int(request.form['amount'])
    atm_pin = request.form['atm_pin']

    user = get_user(username)
    if atm_pin != user[2]:
        return 'Invalid ATM PIN', 400

    update_balance(username, amount)
    log_transaction(username, 'deposit', amount)
    return redirect(url_for('dashboard'))

@app.route('/withdraw', methods=['POST'])
def withdraw():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    amount = int(request.form['amount'])
    atm_pin = request.form['atm_pin']

    user = get_user(username)
    if atm_pin != user[2]:
        return 'Invalid ATM PIN', 400

    balance = get_balance(username)
    if amount > balance:
        return 'Insufficient balance', 400

    update_balance(username, -amount)
    log_transaction(username, 'withdrawal', amount)
    return redirect(url_for('dashboard'))

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()  # Clear the session
    return redirect(url_for('login'))  # Redirect to the login page

if __name__ == '__main__':
    app.run(debug=True)

import os
import sqlite3
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DISPOSABLE_EMAILS = ['bugmenot.com', 'tempmail.com', '10minutemail.com', 'guerrillamail.com', 'yopmail.com']

# Free Gmail SMTP Configuration (App Password)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "your_email@gmail.com"       # Yahan apna Gmail daal sakte ho
SENDER_PASSWORD = "your_app_password"         # Gmail App Password

def send_email_otp(receiver_email, otp_code):
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = receiver_email
        msg['Subject'] = "Sandepani School Portal - Email Verification OTP"
        
        body = f"Hello,\n\nYour OTP for Sandepani Portal registration is: {otp_code}\n\nDo not share this code with anyone.\n\nRegards,\nSandepani School"
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        # Agar SMTP configured nahi hai to console me print ho jayega testing ke liye
        if SENDER_EMAIL != "your_email@gmail.com":
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Email Error: {e}")

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        name TEXT,
        username TEXT UNIQUE,
        address TEXT,
        bio TEXT,
        gender TEXT,
        dp TEXT,
        role TEXT DEFAULT 'Student',
        has_red_tick INTEGER DEFAULT 0,
        class_name TEXT,
        section TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        target_leader TEXT,
        complaint_text TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

init_db()

def generate_captcha():
    import string
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_captcha = request.form.get('captcha')
        if user_captcha != session.get('captcha_text'):
            flash('Galt Captcha Code!')
            session['captcha_text'] = generate_captcha()
            return render_template('login.html', captcha=session['captcha_text'])

        identifier = request.form.get('identifier')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE (phone = ? OR username = ?) AND password = ?', 
                            (identifier, identifier, password)).fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Galt Username ya Password!')
            
    session['captcha_text'] = generate_captcha()
    return render_template('login.html', captcha=session['captcha_text'])

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        existing_user = conn.execute('SELECT * FROM users WHERE phone = ? OR email = ?', (phone, email)).fetchone()
        conn.close()
        
        if existing_user:
            flash('Ye Mobile number ya Email pehle se registered hai!')
            return render_template('signup.html')
            
        domain = email.split('@')[-1] if '@' in email else ''
        if domain in DISPOSABLE_EMAILS:
            flash('Fake/Temporary Email allowed nahi hai!')
            return render_template('signup.html')
            
        otp = str(random.randint(100000, 999999))
        session.clear()
        session['temp_user'] = {
            'phone': phone,
            'email': email,
            'password': password,
            'otp': otp
        }
        
        send_email_otp(email, otp)
        flash(f'OTP Sent Successfully to {email} (For testing, check server logs if SMTP not set)')
        return redirect(url_for('verify_otp'))
        
    return render_template('signup.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        temp_user = session.get('temp_user')
        
        if temp_user and str(entered_otp).strip() == str(temp_user['otp']):
            session['signup_success'] = True
            return redirect(url_for('profile_setup'))
        else:
            flash('Galt OTP! Dobara koshish karein.')
            
    return render_template('verify_otp.html')

@app.route('/profile-setup', methods=['GET', 'POST'])
def profile_setup():
    if not session.get('signup_success'):
        return redirect(url_for('signup'))
        
    if request.method == 'POST':
        temp_user = session.get('temp_user')
        if not temp_user:
            return redirect(url_for('signup'))
            
        name = request.form.get('name')
        username = request.form.get('username')
        address = request.form.get('address')
        bio = request.form.get('bio')
        gender = request.form.get('gender')
        class_name = request.form.get('class_name')
        section = request.form.get('section')
        
        file = request.files.get('dp')
        dp_name = 'default.png'
        if file and file.filename != '':
            dp_name = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], dp_name))

        conn = get_db_connection()
        try:
            conn.execute('''INSERT INTO users 
                (phone, email, password, name, username, address, bio, gender, dp, class_name, section) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (temp_user['phone'], temp_user['email'], temp_user['password'], name, username, address, bio, gender, dp_name, class_name, section))
            conn.commit()
            conn.close()
            session.clear()
            flash('Account ban gaya! Ab Login karein.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Username pehle se taken hai!')
            
    return render_template('profile_setup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    all_users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    
    leaders = [
        {"title": "Prime Minister (PM)", "name": "PM Post", "desc": "Overall school administration."},
        {"title": "Shiksha Mantri", "name": "Education Leader", "desc": "Studies & learning environment."},
        {"title": "Sports Mantri", "name": "Khel Mantri", "desc": "Sports events & physical activities."},
        {"title": "Jal & Paryavaran Mantri", "name": "Environment Leader", "desc": "Cleanliness & green campus."}
    ]
    
    return render_template('dashboard.html', user=user, leaders=leaders, all_users=all_users)

@app.route('/submit-complaint', methods=['POST'])
def submit_complaint():
    if 'user_id' not in session:
        return jsonify({'status': 'error', 'message': 'Not logged in'})
    
    target_leader = request.form.get('leader')
    complaint_text = request.form.get('complaint')
    
    conn = get_db_connection()
    conn.execute('INSERT INTO complaints (user_id, target_leader, complaint_text) VALUES (?, ?, ?)',
                 (session['user_id'], target_leader, complaint_text))
    conn.commit()
    conn.close()
    
    return jsonify({'status': 'success', 'message': 'Complaint Send ho gayi!'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)

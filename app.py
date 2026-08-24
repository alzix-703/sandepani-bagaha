import os
import sqlite3
import random
import string
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sandepani_secret_key_super_secure'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

DISPOSABLE_EMAILS = ['bugmenot.com', 'tempmail.com', '10minutemail.com', 'guerrillamail.com', 'yopmail.com']

# Aap yahan Fast2SMS se API key lekar dalna (Optional real SMS send karne ke liye)
FAST2SMS_API_KEY = "1LgRSEw0MO9V4BGnopJrlF8j6mfcvA2hueYPqkIyWiZzXHNKTbP8qhR9CuSgr1s2Bt7MI4pecXzbmF0k"

def send_real_sms(phone_number, otp_code):
    """Real phone SMS send karne ke liye function"""
    if FAST2SMS_API_KEY != "YOUR_FAST2SMS_API_KEY_HERE":
        url = "https://www.fast2sms.com/dev/bulkV2"
        payload = f"variables_values={otp_code}&route=otp&numbers={phone_number}"
        headers = {
            'authorization': FAST2SMS_API_KEY,
            'Content-Type': "application/x-www-form-urlencoded"
        }
        try:
            requests.post(url, data=payload, headers=headers)
        except Exception as e:
            print(f"SMS Error: {e}")

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
    c.execute('''CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        type TEXT,
        message TEXT
    )''')
    conn.commit()
    conn.close()

init_db()

def generate_captcha():
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
            flash('Galt Captcha Code! Phir se try karo.')
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
            flash('Galt Username/Phone ya Password!')
            
    session['captcha_text'] = generate_captcha()
    return render_template('login.html', captcha=session['captcha_text'])

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        phone = request.form.get('phone')
        email = request.form.get('email')
        password = request.form.get('password')
        
        domain = email.split('@')[-1] if '@' in email else ''
        if domain in DISPOSABLE_EMAILS:
            flash('Fake/Temporary Email allowed nahi hai!')
            return render_template('signup.html')
            
        otp = str(random.randint(100000, 999999))
        session['temp_user'] = {
            'phone': phone,
            'email': email,
            'password': password,
            'otp': otp
        }
        
        # Real Phone SMS Call
        send_real_sms(phone, otp)
        
        flash(f'Verification OTP sent to {phone}! (Demo OTP: {otp})')
        return redirect(url_for('verify_otp'))
        
    return render_template('signup.html')

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        temp_user = session.get('temp_user')
        
        if temp_user and entered_otp == temp_user['otp']:
            session['signup_success'] = True
            return redirect(url_for('profile_setup'))
        else:
            flash('Galt OTP! Sahi OTP dalo.')
            
    return render_template('verify_otp.html')

@app.route('/profile-setup', methods=['GET', 'POST'])
def profile_setup():
    if not session.get('signup_success'):
        return redirect(url_for('signup'))
        
    if request.method == 'POST':
        temp_user = session.get('temp_user')
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
            session.pop('temp_user', None)
            session.pop('signup_success', None)
            flash('Account successfully ban gaya! Ab Login karo.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            conn.close()
            flash('Username pehle se taken hai, koi aur chunno.')
            
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
        {"title": "Prime Minister (PM)", "name": "PM Post", "desc": "Overall school administration & main rules handle karte hain."},
        {"title": "Shiksha Mantri", "name": "Education Leader", "desc": "Studies, syllabus aur school learning environment ke zimmedar."},
        {"title": "Sports Mantri", "name": "Khel Mantri", "desc": "Sports events, games aur physical activities maintain karte hain."},
        {"title": "Jal & Paryavaran Mantri", "name": "Environment Leader", "desc": "Cleanliness, water supply aur green campus ke head."}
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

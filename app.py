import os
import sqlite3
import random
import time
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "school_secret_key_arpit"
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Database Setup
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            class_sec TEXT,
            phone TEXT UNIQUE,
            password TEXT,
            profile_pic TEXT,
            role TEXT DEFAULT 'student',
            badge TEXT DEFAULT 'none'
        )
    ''')
    # Complaints Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            leader_role TEXT,
            subject TEXT,
            description TEXT,
            timestamp REAL,
            status TEXT DEFAULT 'Pending'
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect('/dashboard')
    return render_template('login.html')

@app.route('/signup', methods=['POST'])
def signup():
    name = request.form['name']
    class_sec = request.form['class_sec']
    phone = request.form['phone']
    password = request.form['password']
    role = request.form.get('role', 'student')
    
    # Profile Pic Upload
    file = request.files.get('profile_pic')
    filename = "default.png"
    if file and file.filename != '':
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
    # Set Badge
    badge = 'none'
    if role == 'PM':
        badge = 'red_tick'
    elif role != 'student':
        badge = 'blue_tick'
        
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, class_sec, phone, password, profile_pic, role, badge) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (name, class_sec, phone, password, filename, role, badge))
        conn.commit()
        conn.close()
        flash("Account created! Please login.")
    except Exception as e:
        flash("Phone number already exists!")
    return redirect('/')

@app.route('/login', methods=['POST'])
def login():
    phone = request.form['phone']
    password = request.form['password']
    captcha = request.form['captcha']
    
    if captcha != "4": # Simple math captcha (2+2)
        flash("Wrong Captcha!")
        return redirect('/')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE phone=? AND password=?", (phone, password))
    user = cursor.fetchone()
    conn.close()

    if user:
        session['user_id'] = user[0]
        session['name'] = user[1]
        session['role'] = user[6]
        session['badge'] = user[7]
        session['pic'] = user[5]
        return redirect('/dashboard')
    else:
        flash("Invalid Credentials!")
        return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Fetch complaints based on role
    if session['role'] == 'student':
        cursor.execute("SELECT * FROM complaints WHERE user_id=?", (session['user_id'],))
    else:
        cursor.execute("SELECT * FROM complaints WHERE leader_role=? OR leader_role='PM'", (session['role'],))
    
    complaints = cursor.fetchall()
    conn.close()
    
    current_time = time.time()
    return render_template('dashboard.html', user=session, complaints=complaints, current_time=current_time)

@app.route('/submit_complaint', methods=['POST'])
def submit_complaint():
    if 'user_id' not in session:
        return redirect('/')
    
    leader_role = request.form['leader_role']
    description = request.form['description']
    
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO complaints (user_id, user_name, leader_role, subject, description, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (session['user_id'], session['name'], leader_role, leader_role + " Issue", description, time.time()))
    conn.commit()
    conn.close()
    
    flash("Complaint Sent Successfully!")
    return redirect('/dashboard')

@app.route('/resolve_complaint/<int:id>')
def resolve_complaint(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE complaints SET status='Resolved' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

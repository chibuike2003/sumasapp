import os
from flask import Flask, render_template, request, redirect, url_for, flash, session,jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from sqlalchemy import or_
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from itertools import groupby
from collections import defaultdict
from sqlalchemy.orm import joinedload

import csv
from flask import Response, stream_with_context
from google import genai
from dotenv import load_dotenv

# 1. Load the variables from the .env file
load_dotenv()
app = Flask(__name__)

# --- Configurations ---
app.config['SECRET_KEY'] = 'sumas_portal_ultra_secure_secret_key_2026'

# SQLite Database configuration mapping parameters
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sumasappuni.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Mail / Gmail SMTP Server Setup 
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'collegiumunncourtesyportal@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'fwbz fdyq vsav nsxz')
app.config['MAIL_DEFAULT_SENDER'] = ('SUMAS Portal Hub', app.config['MAIL_USERNAME'])

# Core Engine Extension Initializations
db = SQLAlchemy(app)
mail = Mail(app)


class AcademicScope(db.Model):
    __tablename__ = 'academic_scopes'

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), unique=True, nullable=False)
    faculty = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())

    # ADD THIS: This defines the back_populates target
    student = db.relationship('Student', back_populates='academic_scope')


class Admin(db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    department = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='scrypt')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)



class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_year = db.Column(db.String(20), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    faculty = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    course_code = db.Column(db.String(20), unique=True, nullable=False)
    course_title = db.Column(db.String(200), nullable=False)
    unit_load = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f'<Course {self.course_code}>'

class Registration(db.Model):
    __tablename__ = 'registration'
    id = db.Column(db.Integer, primary_key=True)
    
    # Use the actual table names defined in the other models
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Define the relationships
    # The first argument is the Class Name, not the table name
    course = db.relationship('Course', backref='registrations')
    student = db.relationship('Student', backref='registrations')

class Lecturer(db.Model):
    __tablename__ = 'lecturers'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    department = db.Column(db.String(100), nullable=False)
    
    # Relationships
    results = db.relationship('Result', back_populates='lecturer', cascade="all, delete-orphan")
    
    # Link to LecturerCourse
    courses = db.relationship('LecturerCourse', back_populates='lecturer', cascade="all, delete-orphan")

class LecturerCourse(db.Model):
    __tablename__ = 'lecturer_courses'
    id = db.Column(db.Integer, primary_key=True)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('lecturers.id'), nullable=False)
    # ADD THIS: Link directly to the course by ID
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    
    # Relationships
    lecturer = db.relationship('Lecturer', back_populates='courses')
    course = db.relationship('Course', backref='lecturer_assignments')


class Student(db.Model):
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Relationships
    academic_scope = db.relationship('AcademicScope', back_populates='student', uselist=False, cascade="all, delete-orphan")
    results = db.relationship('Result', back_populates='student', lazy='dynamic', cascade="all, delete-orphan")
    academic_scope = db.relationship('AcademicScope', back_populates='student', uselist=False, cascade="all, delete-orphan")  
    def __repr__(self):
        return f"<Student {self.reg_number}>"

class Result(db.Model):
    __tablename__ = 'results'
    
    id = db.Column(db.Integer, primary_key=True)
    lecturer_id = db.Column(db.Integer, db.ForeignKey('lecturers.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False) 
    
    # Historical data to keep records if student profile changes
    student_name = db.Column(db.String(100), nullable=False)
    reg_number = db.Column(db.String(50), nullable=False)
    
    course_code = db.Column(db.String(20), nullable=False)
    course_title = db.Column(db.String(150), nullable=False)
    session_written = db.Column(db.String(50), nullable=False)
    year = db.Column(db.String(20), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    
    ca_score = db.Column(db.Float, nullable=False)
    exam_score = db.Column(db.Float, nullable=False)
    total_score = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(2), nullable=True)
    
    uploaded_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    # Relationships
    student = db.relationship('Student', back_populates='results')
    lecturer = db.relationship('Lecturer', back_populates='results')
    
    def __repr__(self):
        return f"<Result {self.reg_number} - {self.course_code}>"

# --- Helper Function for Automated Welcome Email ---
def send_welcome_email(student_email, student_name, reg_number):
    subject = "Welcome to SUMAS Student Portal - Account Created Successfully"
    
    # Beautiful styled HTML email template matching layout system configurations
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Welcome to SUMAS</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">
            <tr>
                <td align="center" style="padding: 40px 0; background-color: #f8fafc;">
                    <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05), 0 2px 4px -1px rgba(0,0,0,0.03); border: 1px solid #e2e8f0;">
                        <!-- Header Banner -->
                        <tr>
                            <td style="background-color: #1d4ed8; padding: 40px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: 700; letter-spacing: -0.5px;">SUMAS</h1>
                                <p style="color: #93c5fd; margin: 5px 0 0 0; text-transform: uppercase; font-size: 12px; font-weight: 600; letter-spacing: 1px;">Enugu State University of Medical & Applied Sciences</p>
                            </td>
                        </tr>
                        <!-- Body Content -->
                        <tr>
                            <td style="padding: 40px; color: #334155;">
                                <h2 style="color: #0f172a; margin-top: 0; font-size: 22px; font-weight: 700;">Account Activated Successfully 🎉</h2>
                                <p style="font-size: 16px; line-height: 1.6; color: #475569;">Dear <strong>{student_name}</strong>,</p>
                                <p style="font-size: 16px; line-height: 1.6; color: #475569;">Congratulations! Your student access account profile has been successfully provisioned within the central academic system hub.</p>
                                
                                <!-- Credentials Box -->
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f1f5f9; border-radius: 12px; margin: 25px 0; border: 1px solid #e2e8f0;">
                                    <tr>
                                        <td style="padding: 20px;">
                                            <p style="margin: 0 0 8px 0; font-size: 14px; color: #64748b;"><strong style="color: #334155;">Registration Number:</strong> {reg_number.upper()}</p>
                                            <p style="margin: 0; font-size: 14px; color: #64748b;"><strong style="color: #334155;">Portal Username:</strong> {student_email}</p>
                                        </td>
                                    </tr>
                                </table>

                                <p style="font-size: 16px; line-height: 1.6; color: #475569;">You can now log in to proceed with your course registration parameters, view structured examination records, and reconcile semester fee balances.</p>
                                
                                <!-- Button Link -->
                                <table border="0" cellpadding="0" cellspacing="0" style="margin: 30px auto 0 auto;">
                                    <tr>
                                        <td align="center" style="border-radius: 12px; background-color: #1d4ed8;">
                                            <a href="http://127.0.0.1:5000/login" target="_blank" style="border: solid 1px #1d4ed8; border-radius: 12px; color: #ffffff; display: inline-block; font-size: 15px; font-weight: 600; padding: 14px 28px; text-decoration: none; text-transform: capitalize;">Access Student Workspace</a>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                        <!-- Footer System Segment -->
                        <tr>
                            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 24px; text-align: center; color: #94a3b8; font-size: 12px;">
                                <p style="margin: 0 0 4px 0;">&copy; 2026 SUMAS ICT Directorate. All rights reserved.</p>
                                <p style="margin: 0;">This is an automated notification. Please do not reply directly to this mail.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    msg = Message(subject=subject, recipients=[student_email], html=html_body)
    mail.send(msg)



def send_profile_update_email(student_email, student_name, changes_dict):
    subject = "Security Alert: SUMAS Profile Update Notification"
    
    # Dynamically build the HTML list items based on exactly what changed
    changes_html = ""
    for field, values in changes_dict.items():
        changes_html += f"""
        <tr style="border-bottom: 1px solid #f1f5f9;">
            <td style="padding: 12px; font-size: 14px; color: #475569; font-weight: 600; text-transform: uppercase; tracking-wider: 0.5px;">{field}</td>
            <td style="padding: 12px; font-size: 14px; color: #ef4444; text-decoration: line-through;">{values['old']}</td>
            <td style="padding: 12px; font-size: 14px; color: #10b981; font-weight: 500;">{values['new']}</td>
        </tr>
        """

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>SUMAS Profile Updated</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%">
            <tr>
                <td align="center" style="padding: 40px 0; background-color: #f8fafc;">
                    <table border="0" cellpadding="0" cellspacing="0" width="600" style="background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); border: 1px solid #e2e8f0;">
                        <!-- Security Alert Header Banner -->
                        <tr>
                            <td style="background-color: #0f172a; padding: 30px 40px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 24px; font-weight: 700;">SUMAS Portal Security</h1>
                                <p style="color: #94a3b8; margin: 5px 0 0 0; font-size: 11px; text-transform: uppercase; letter-spacing: 1px;">Account Modification Log</p>
                            </td>
                        </tr>
                        <!-- Content Body -->
                        <tr>
                            <td style="padding: 40px; color: #334155;">
                                <h3 style="color: #0f172a; margin-top: 0; font-size: 18px;">Profile Changes Detected</h3>
                                <p style="font-size: 15px; line-height: 1.6; color: #475569;">Hello {student_name},</p>
                                <p style="font-size: 15px; line-height: 1.6; color: #475569;">This notification confirms that your student profile configuration parameters were explicitly modified. Below is an audit breakdown tracking your updates:</p>
                                
                                <!-- Changes Audit Table Grid -->
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 25px 0; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; border-collapse: collapse;">
                                    <thead>
                                        <tr style="background-color: #f8fafc; border-bottom: 1px solid #e2e8f0; text-align: left;">
                                            <th style="padding: 12px; font-size: 12px; color: #64748b; text-transform: uppercase;">Parameter</th>
                                            <th style="padding: 12px; font-size: 12px; color: #64748b; text-transform: uppercase;">Previous Value</th>
                                            <th style="padding: 12px; font-size: 12px; color: #64748b; text-transform: uppercase;">Updated Value</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {changes_html}
                                    </tbody>
                                </table>

                                <p style="font-size: 14px; color: #ef4444; font-weight: 500; background-color: #fef2f2; padding: 12px; border-radius: 8px; border: 1px solid #fee2e2;">
                                    <strong>Security Note:</strong> If you did not authorize these operational workspace profile modifications, please contact the SUMAS ICT Directorate helpdesk immediately to flag your token matrix.
                                </p>
                            </td>
                        </tr>
                        <!-- Footer System Segment -->
                        <tr>
                            <td style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px; text-align: center; color: #94a3b8; font-size: 11px;">
                                <p style="margin: 0;">&copy; 2026 SUMAS ICT Directorate. Automated Security Integrity Stream.</p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    # Send email to the student's primary email address
    msg = Message(subject=subject, recipients=[student_email], html=html_body)
    mail.send(msg)


# --- Core App Routes ---

@app.route('/')
def home():
    # Base root index automatically pathways out out to explicit sign in workspace
    return render_template('index.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Safely extract and sanitize input properties
        reg_number = request.form.get('reg_number', '').strip().upper()
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password')
        
        # Backend payload structural completeness checking validation rules
        if not reg_number or not name or not email or not password:
            flash("All fields are strictly required to proceed.", "error")
            return redirect(url_for('signup'))
            
        if len(password) < 8:
            flash("Password validation failed: Must be 8 or more characters long.", "error")
            return redirect(url_for('signup'))

        # Check unique constraint criteria database parameters for Reg Number
        existing_reg = Student.query.filter_by(reg_number=reg_number).first()
        if existing_reg:
            flash(f"Registration Number '{reg_number}' already exists on the portal hierarchy.", "error")
            return redirect(url_for('signup'))

        # Check unique constraint criteria database parameters for Email Address
        existing_email = Student.query.filter_by(email=email).first()
        if existing_email:
            flash(f"Email address '{email}' is already associated with another student account.", "error")
            return redirect(url_for('login'))

        try:
            # Securely hash user password payload mapping parameters
            hashed_password = generate_password_hash(password, method='scrypt')
            
            new_student = Student(
                reg_number=reg_number,
                name=name,
                email=email,
                password_hash=hashed_password
            )
            
            db.session.add(new_student)
            db.session.commit()
            
            # Send the beautiful automated greeting email pipeline
            send_welcome_email(email, name, reg_number)
            
            flash("Registration Successful! A validation confirmation email has been routed to your inbox.", "success")
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash("System Error encountered: Processing interrupted. Verification failed.", "error")
            return redirect(url_for('signup'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('login_identity', '').strip()
        password = request.form.get('password')
        remember_me = request.form.get('remember_me') # Will return 'on' if checked

        if not identity or not password:
            flash("Please enter both your identity reference and password.", "error")
            return redirect(url_for('login'))

        # Query checking identity references against email column OR registration column data matching
        student = Student.query.filter(
            or_(
                Student.email == identity.lower(),
                Student.reg_number == identity.upper()
            )
        ).first()

        # Securely evaluate if student instance payload satisfies password check values
        if student and check_password_hash(student.password_hash, password):
            # Establish localized session variables configuration setup
            session.clear()
            session['student_id'] = student.id
            session['student_name'] = student.name
            session['student_reg'] = student.reg_number
            
            if remember_me:
                session.permanent = True
            
            flash(f"Welcome back, {student.name}!", "success")
            return redirect(url_for('dashboard'))
        else:
            # Prevent metadata discovery profile timing enumeration attacks via vague statements
            flash("Invalid registration details or password. Please try again.", "error")
            return redirect(url_for('login'))

    return render_template('login.html')






@app.route('/dashboard')
def dashboard():
    # 1. Auth check
    if 'student_id' not in session:
        flash("Access Denied: Please sign in.", "error")
        return redirect(url_for('login'))
        
    # 2. Fetch student
    student = Student.query.get(session['student_id'])
    if not student:
        session.clear()
        return redirect(url_for('login'))

    # 3. Fetch registrations and transform into a JSON-serializable list of dicts
    # We query Registration and join with Course to access details
    regs_query = db.session.query(Registration).join(Course)\
                 .filter(Registration.student_id == student.id)\
                 .order_by(Course.session_year, Course.level, Course.semester).all()
    
    # Transform objects to dictionaries (This fixes the JSON serialization error)
    data = []
    for r in regs_query:
        data.append({
            'id': r.id,
            'session': r.course.session_year,
            'level': r.course.level,
            'semester': r.course.semester,
            'course': {
                'course_code': r.course.course_code,
                'course_title': r.course.course_title,
                'unit_load': r.course.unit_load
            }
        })
    
    # 4. Group by (session, level, semester)
    # We use the transformed data list
    grouped_regs = {}
    for key, group in groupby(data, lambda x: (x['session'], x['level'], x['semester'])):
        grouped_regs[key] = list(group)
        
    return render_template('dashboard.html', student=student, grouped_regs=grouped_regs)




@app.route('/update_academic_scope', methods=['POST'])
def update_academic_scope():
    if 'student_id' not in session:
        flash("Access Denied: Session expired.", "error")
        return redirect(url_for('login'))
        
    student = Student.query.get(session['student_id'])
    if not student:
        flash("Profile records not found.", "error")
        return redirect(url_for('dashboard'))

    # CRITICAL SECURITY CHECK: Prevent alteration if a mapping record already exists
    existing_scope = AcademicScope.query.filter_by(student_id=student.id).first()
    if existing_scope:
        flash("Security Restriction: Your Faculty and Department choices are locked and cannot be altered.", "error")
        return redirect(url_for('dashboard'))

    faculty = request.form.get('faculty', '').strip()
    department = request.form.get('department', '').strip()

    if not faculty or not department:
        flash("Academic Update Failed: Select valid options for both fields.", "error")
        return redirect(url_for('dashboard'))

    try:
        # Build and bind the one-time record
        new_scope = AcademicScope(
            student_id=student.id,
            faculty=faculty,
            department=department
        )
        db.session.add(new_scope)
        db.session.commit()
        
        # Keep active application session footprints updated
        session['student_faculty'] = faculty
        session['student_department'] = department
        
        flash("Academic assignment locked in successfully!", "success")
    except Exception as e:
        db.session.rollback()
        print(f"[DB EXCEPTION]: Error committing permanent AcademicScope. Details: {e}")
        flash("An internal database error occurred while initializing your setup.", "error")
        
    return redirect(url_for('dashboard'))



@app.route('/update_profile', methods=['POST'])
def update_profile():
    # Verify the user is authenticated in the session
    if 'student_id' not in session:
        flash("Access Denied: Please sign in to authenticate your context.", "error")
        return redirect(url_for('login'))
        
    student = Student.query.get(session['student_id'])
    if not student:
        flash("Student profile records not found.", "error")
        return redirect(url_for('login'))

    # Extract form values
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    new_password = request.form.get('new_password', '')

    # Base profile input validation
    if not name or not email:
        flash("Name and Email fields cannot be left empty.", "error")
        return redirect(url_for('dashboard'))

    # Check unique constraint criteria for email if it changed
    if email != student.email:
        existing_email = Student.query.filter_by(email=email).first()
        if existing_email:
            flash(f"The email address '{email}' is already taken by another user profile.", "error")
            return redirect(url_for('dashboard'))
        student.email = email

    # Update student details
    student.name = name

    # Process and hash new password if the field was filled out
    if new_password:
        if len(new_password) < 8:
            flash("Password update failed: Must be 8 or more characters long.", "error")
            return redirect(url_for('dashboard'))
        student.password_hash = generate_password_hash(new_password, method='scrypt')

    try:
        db.session.commit()
        
        # Keep current application state in sync with updated records
        session['student_name'] = student.name
        
        flash("Your profile parameters have been updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("A system error occurred while updating settings data profiles.", "error")
        
    return redirect(url_for('dashboard'))





@app.route('/student/search_courses', methods=['GET'])
def search_courses():
    # Fetch distinct values for the dropdowns
    sessions = db.session.query(Course.session_year).distinct().all()
    levels = db.session.query(Course.level).distinct().all()
    semesters = db.session.query(Course.semester).distinct().all()
    
    # Get parameters if user has already searched
    session_year = request.args.get('session')
    level = request.args.get('level')
    semester = request.args.get('semester')
    
    courses = []
    if session_year and level and semester:
        courses = Course.query.filter_by(
            session_year=session_year,
            level=level,
            semester=semester
        ).all()

    return render_template('student_course_list.html', 
                           courses=courses, 
                           sessions=[s[0] for s in sessions],
                           levels=[l[0] for l in levels],
                           semesters=[sem[0] for sem in semesters])




@app.route('/student/register_courses', methods=['POST'])
def register_courses():
    if 'student_id' not in session:
        return redirect(url_for('login'))

    # Get list of selected course IDs from the form
    selected_ids = request.form.getlist('course_ids')
    
    # 1. Fetch the selected courses from the database
    selected_courses = Course.query.filter(Course.id.in_(selected_ids)).all()
    
    # 2. Calculate total units
    total_units = sum(int(c.unit_load) for c in selected_courses)
    
    # 3. Enforce the 24-unit limit
    if total_units > 24:
        flash(f"Registration failed: Total units ({total_units}) exceed the maximum limit of 24.", "error")
        return redirect(url_for('search_courses'))
    
    # 4. Proceed with saving registration to the database
    # (Assuming you have a 'Registration' model)
    for course in selected_courses:
        new_reg = Registration(student_id=session['student_id'], course_id=course.id)
        db.session.add(new_reg)
    
    db.session.commit()
    flash(f"Successfully registered {len(selected_courses)} courses!", "success")
    return redirect(url_for('dashboard'))




@app.route('/my-results', methods=['GET'])
def view_my_results():
    # Enforce session-based authentication
    if 'student_id' not in session:
        flash('Please log in to view your results.', 'warning')
        return redirect(url_for('login'))
    
    # Filter results by the ID stored in the session
    # We use session['student_id'] as the source of truth
    student_results = Result.query.filter_by(student_id=session['student_id']).all()
    
    return render_template('student_results.html', results=student_results)

# Configure the API

# ==================== GEMINI CONFIG ====================

api_key = ""   # ← Paste your real Gemini API key inside the quotes

if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
    print("⚠️  WARNING: You forgot to put your actual Gemini API key!")
else:
    print("✅ Gemini API key loaded successfully (hardcoded).")

# Initialize the client
client = genai.Client(api_key=api_key)



@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if request.method == 'POST':
        user_input = request.json.get("message")
        if not user_input:
            return jsonify({"reply": "Please provide a message."}), 400

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-exp",   # More reliable model
                contents=[{"role": "user", "parts": [{"text": user_input}]}],
            )
            return jsonify({"reply": response.text})
        
        except Exception as e:
            print(f"Gemini API Error: {e}")
            return jsonify({"reply": "Sorry, AI is temporarily unavailable. Try again."}), 500

    return render_template('chat.html')





def get_grade_point(grade):
    mapping = {'A': 5.0, 'B': 4.0, 'C': 3.0, 'D': 2.0, 'E': 1.0, 'F': 0.0}
    return mapping.get(grade.upper(), 0.0)





@app.route('/student/cgpa')
def student_cgpa():
    student_id = session.get('student_id')
    results = Result.query.filter_by(student_id=student_id).all()
    
    total_gp = 0.0
    total_units = 0.0
    
    # Dictionary to group by semester
    semester_data = defaultdict(list)
    
    for res in results:
        course = Course.query.filter_by(course_code=res.course_code).first()
        unit_load = course.unit_load if course else 0
        
        grade_point = get_grade_point(res.grade)
        gp = grade_point * unit_load
        
        # Add to cumulative totals
        total_gp += gp
        total_units += unit_load
        
        # Append to the dictionary for the template
        semester_data[(res.year, res.semester)].append({
            'code': res.course_code,
            'grade': res.grade,
            'units': unit_load,
            'gp': gp
        })
        
    cgpa = (total_gp / total_units) if total_units > 0 else 0.0
    
    # Pass semester_data to the template
    return render_template('cgpa_view.html', 
                           cgpa=round(cgpa, 2), 
                           semester_data=semester_data)



@app.route('/student/results-summary')
def student_results_summary():
    student_id = session.get('student_id')
    # Join with Course to get unit_load directly
    results = db.session.query(Result, Course.unit_load)\
        .join(Course, Result.course_code == Course.course_code)\
        .filter(Result.student_id == student_id).all()
    
    # Dictionary to hold data: { (year, semester): [results_list] }
    semester_data = defaultdict(list)
    
    overall_total_gp = 0.0
    overall_total_units = 0.0
    
    for res, unit_load in results:
        gp = get_grade_point(res.grade) * unit_load
        semester_data[(res.year, res.semester)].append({
            'course': res.course_title,
            'code': res.course_code,
            'grade': res.grade,
            'units': unit_load,
            'gp': gp
        })
        overall_total_gp += gp
        overall_total_units += unit_load
        
    cgpa = (overall_total_gp / overall_total_units) if overall_total_units > 0 else 0.0
    
    return render_template('results_summary.html', 
                           semester_data=semester_data, 
                           cgpa=round(cgpa, 2))




@app.route('/student/last-course-level')
def student_last_course_level():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    
    # Get the latest registration for this student
    last_reg = Registration.query.filter_by(student_id=session['student_id'])\
        .order_by(Registration.id.desc())\
        .first()
    
    if not last_reg:
        return "No registration records found.", 404
    
    # Access the course object via the relationship defined in your model
    last_course = last_reg.course
    
    return render_template('last_course_level.html', 
                           course=last_course)





@app.route('/student/total-units')
def student_total_units():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))
    
    student_id = session['student_id']
    
    # Use func.sum to add up the unit_load directly in the database
    total_units = db.session.query(func.sum(Course.unit_load))\
        .join(Registration, Registration.course_id == Course.id)\
        .filter(Registration.student_id == student_id)\
        .scalar() or 0
        
    return render_template('total_units.html', total_units=total_units)


@app.route('/logout')
def logout():
    session.clear()
    flash("You have successfully signed out of your portal device workspace profile.", "success")
    return redirect(url_for('login'))





















# Define your secret system verification authority bypass passphrase key.
# In production, it is highly recommended to store this inside your secret environment variables (.env file)
SYSTEM_AUTHORITY_KEY = os.getenv('SUMAS_ADMIN_PASSPHRASE', 'SUMAS_CORE_SECURE_2026')

@app.route('/admin/signup', methods=['GET', 'POST'])
def admin_signup_post():
    # 1. Extract payload parameters from form inputs
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    department = request.form.get('department', '')
    admin_key = request.form.get('admin_key', '')
    password = request.form.get('password', '')
    compliance_check = request.form.get('compliance_check')

    # 2. Strict validation sweeps
    if not all([name, email, department, admin_key, password]):
        flash("Registration failed: All fields must be completely filled out.", "error")
        return render_template('adminsignup.html')

    if not compliance_check:
        flash("Registration failed: You must accept institutional regulatory compliance terms.", "error")
        return render_template('adminsignup.html')

    # 3. Security Check: Validate matching authorization credentials key
    if admin_key != SYSTEM_AUTHORITY_KEY:
        flash("Access Denied: The System Authority Key provided is invalid.", "error")
        return render_template('adminsignup.html')

    # 4. Domain Check: Enforce official institutional email verification
    if not email.endswith('@sumas.edu.ng'):
        flash("Validation Error: Administrative access requires an official '@sumas.edu.ng' email account.", "error")
        return render_template('adminsignup.html')

    # 5. Check if the admin email already exists in the system database
    existing_admin = Admin.query.filter_by(email=email).first()
    if existing_admin:
        flash(f"Account registration conflict: '{email}' is already registered.", "error")
        return render_template('adminsignup.html')

    # 6. Initialize database model entry mapping parameters
    new_admin = Admin(
        name=name,
        email=email,
        department=department
    )
    # Apply cryptographical password hash protection mapping
    new_admin.set_password(password)

    try:
        # Commit record cleanly into the database engine
        db.session.add(new_admin)
        db.session.commit()
        
        # Flash positive feedback confirmation status to the next loading template context view page
        flash("Administrative credential profile workspace has been provisioned successfully! You can now log in.", "success")
        return redirect(url_for('admin_login'))  # Redirect to your admin login screen endpoint
        
    except Exception as e:
        db.session.rollback()
        # Log system errors elegantly
        print(f"[DB EXCEPTION]: Admin creation rollback executed. Details: {e}")
        flash("An internal core system database failure occurred while setting up the profile.", "error")
        return render_template('adminsignup.html')




@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'GET':
        return render_template('admin_login.html')
        
    # POST processing logic pipeline
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')

    if not email or not password:
        flash("Authentication Error: All verification inputs are mandatory.", "error")
        return render_template('admin_login.html')

    # Query matching against administrative structural table entries
    admin = Admin.query.filter_by(email=email).first()

    if admin and admin.check_password(password):
        # Establish isolated administrative context scope variables inside session tracking cookies
        session.clear() # Clear any existing student data footprints out of execution bounds
        session['admin_id'] = admin.id
        session['admin_name'] = admin.name
        session['admin_dept'] = admin.department
        
        return redirect(url_for('admin_dashboard'))
    else:
        flash("Invalid Credentials: Cross-verify your institutional credentials network profile entries.", "error")
        return render_template('admin_login.html')





@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash("Access Restricted: Please login.", "error")
        return redirect(url_for('admin_login'))
        
    search_query = request.args.get('q', '').strip()
    # Capture the page number from the URL, default to 1
    page = request.args.get('page', 1, type=int)
    
    query = db.session.query(Registration).join(Student).join(Course)
    
    if search_query:
        query = query.filter(
            (Student.name.ilike(f"%{search_query}%")) | 
            (Course.course_code.ilike(f"%{search_query}%"))
        )
        
    # Implement pagination: 20 items per page
    pagination = query.paginate(page=page, per_page=20, error_out=False)
    registrations = pagination.items
    students = Student.query.all()
    courses = Course.query.all()
    
    
    return render_template('admin_dashboard.html', 
                           registrations=registrations,
                           pagination=pagination, # Pass the object to the template
                           students=students,
                           courses=courses,
                           search_query=search_query)


@app.route('/admin/export_registrations')
def export_registrations():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))

    search_query = request.args.get('q', '')
    query = db.session.query(Registration).join(Student).join(Course)
    
    if search_query:
        query = query.filter(
            (Student.name.ilike(f"%{search_query}%")) | 
            (Course.course_code.ilike(f"%{search_query}%"))
        )
    
    registrations = query.all()

    # Generator function to stream CSV data
    def generate():
        data = [['Student Name', 'Course Code', 'Course Title']]
        for reg in registrations:
            data.append([reg.student.name, reg.course.course_code, reg.course.course_title])
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(data)
        yield output.getvalue()

    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=registrations.csv"}
    )



@app.route('/admin/student/edit/<int:student_id>', methods=['POST'])
def admin_edit_student(student_id):
    if 'admin_id' not in session:
        flash("Unauthorized entity manipulation attempted.", "error")
        return redirect(url_for('admin_login'))
        
    student = Student.query.get_or_404(student_id)
    
    try:
        # 1. Update Core Student Model Fields
        student.name = request.form.get('name')
        student.email = request.form.get('email')
        
        # 2. Update or Initialize Associated AcademicScope Model Parameters
        scope = AcademicScope.query.filter_by(student_id=student.id).first()
        if not scope:
            scope = AcademicScope(student_id=student.id)
            db.session.add(scope)
            
        scope.faculty = request.form.get('faculty')
        scope.department = request.form.get('department')
        
        db.session.commit()
        flash(f"Student mapping coordinates for {student.name} updated successfully.", "success")
    except Exception as e:
        db.session.rollback()
        flash("System validation fault encountered during entity modification.", "error")
        
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/student/delete/<int:student_id>', methods=['POST'])
def admin_delete_student(student_id):
    if 'admin_id' not in session:
        flash("Unauthorized deletion parameters passed.", "error")
        return redirect(url_for('admin_login'))
        
    student = Student.query.get_or_404(student_id)
    
    try:
        # First drop dependent records matching foreign key constraints
        AcademicScope.query.filter_by(student_id=student.id).delete()
        
        # Drop parent student row safely
        db.session.delete(student)
        db.session.commit()
        flash(f"Student entity metadata matching records [{student.name}] dropped from ledger.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Database structural constraint rejected deletion execution pipeline.", "error")
        
    return redirect(url_for('admin_dashboard'))




@app.route('/admin/add_course', methods=['POST'])
def add_course():
    if 'admin_id' not in session:
        flash("Unauthorized access. Please log in.", "error")
        return redirect(url_for('admin_login'))

    # Get and clean form data
    course_code = request.form.get('course_code', '').strip().upper()
    course_title = request.form.get('course_title', '').strip()
    session_year = request.form.get('session')
    level = request.form.get('level')
    semester = request.form.get('semester')
    faculty = request.form.get('faculty')
    department = request.form.get('department')
    unit_load = request.form.get('unit_load')

    # Check if course already exists
    existing_course = Course.query.filter_by(course_code=course_code).first()
    
    if existing_course:
        flash(f"Course with code '{course_code}' already exists!", "error")
        return redirect(url_for('admin_dashboard'))

    # Create new course
    new_course = Course(
        session_year=session_year,
        level=level,
        semester=semester,
        faculty=faculty,
        department=department,
        course_code=course_code,
        course_title=course_title,
        unit_load=unit_load
    )
    
    db.session.add(new_course)
    db.session.commit()
    
    flash(f"Course '{course_code}' - {course_title}' successfully added to catalog.", "success")
    return redirect(url_for('admin_dashboard'))


# ====================== EDIT COURSE ======================
@app.route('/admin/course/edit/<int:course_id>', methods=['POST'])
def edit_course(course_id):
    if 'admin_id' not in session:
        flash("Unauthorized access. Please login as admin.", "error")
        return redirect(url_for('admin_login'))

    course = Course.query.get_or_404(course_id)

    # Get form data
    new_course_code = request.form.get('course_code', '').strip().upper()
    new_course_title = request.form.get('course_title', '').strip()
    new_unit_load = request.form.get('unit_load')

    # === Check for duplicate course code (excluding current course) ===
    existing = Course.query.filter(
        Course.course_code.ilike(new_course_code),
        Course.id != course_id
    ).first()

    if existing:
        flash(f"Error updating course. Course code '{new_course_code}' already exists.", "error")
        return redirect(url_for('admin_dashboard'))  # You can change this if using modal

    # Update course details
    course.session_year = request.form.get('session')
    course.level = request.form.get('level')
    course.semester = request.form.get('semester')
    course.faculty = request.form.get('faculty')
    course.department = request.form.get('department')
    course.course_code = new_course_code
    course.course_title = new_course_title
    course.unit_load = new_unit_load

    try:
        db.session.commit()
        flash(f"Course '{course.course_code}' updated successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash("An unexpected error occurred while updating the course.", "error")
        print(f"Error: {e}")  # For debugging

    return redirect(url_for('admin_dashboard'))


# ====================== DELETE COURSE ======================
@app.route('/admin/course/delete/<int:course_id>', methods=['POST'])
def delete_course(course_id):
    if 'admin_id' not in session:
        flash("Unauthorized access. Please login as admin.", "error")
        return redirect(url_for('admin_login'))

    course = Course.query.get_or_404(course_id)
    course_code = course.course_code  # Save for flash message

    try:
        db.session.delete(course)
        db.session.commit()
        flash(f"Course '{course_code}' has been successfully deleted.", "success")
    except Exception as e:
        db.session.rollback()
        flash("Error deleting course. Please try again.", "error")
    
    return redirect(url_for('admin_dashboard'))



@app.route('/admin/registrations')
def admin_registrations():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    all_registrations = Registration.query.all()
    
    student_map = defaultdict(list)
    for reg in all_registrations:
        # Use .course_title here
        if reg.course:
            student_map[reg.student].append(reg.course)
    
    return render_template('registrations.html', student_map=student_map)




@app.route('/admin-view-results', methods=['GET'])
def adminview_results():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))


    # Main data
    all_results = Result.query.order_by(Result.uploaded_at.desc()).all()
    students = Student.query.all()
    admins = Admin.query.all()
    courses = Course.query.all()
    
    # Optional: Add some useful aggregates
    total_results = len(all_results)
    recent_results = Result.query.order_by(Result.uploaded_at.desc()).limit(10).all()
    
    return render_template('adminviewresults.html', 
                           results=all_results,
                           students=students,
                           admins=admins,
                           courses=courses,
                           total_results=total_results,
                           recent_results=recent_results)



@app.route('/admin/logout')
def admin_logout():
    # Strip session clean to prevent cross-contamination or unauthorized cookie persistence 
    session.clear()
    flash("Session terminated safely. Administrative terminal node deactivated successfully.", "success")
    return redirect(url_for('admin_login'))







@app.route('/lecturer/signup', methods=['GET', 'POST'])
def lecturer_signup():
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')
        password = request.form.get('password')
        department = request.form.get('department')

        # 1. Check if the lecturer already exists
        lecturer_exists = Lecturer.query.filter_by(email=email).first()
        
        if lecturer_exists:
            flash('An account with this email already exists. Please log in.', 'danger')
            return redirect(url_for('lecturer_signup'))

        # 2. Hash the password and save
        hashed_pw = generate_password_hash(password)
        new_lecturer = Lecturer(
            name=name,
            email=email,
            password=hashed_pw,
            department=department
        )
        
        try:
            db.session.add(new_lecturer)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('lecturer_login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            return redirect(url_for('lecturer_signup'))

    return render_template('lecturersignup.html')

@app.route('/lecturer/login', methods=['GET', 'POST'])
def lecturer_login():
    if request.method == 'POST':
        lecturer = Lecturer.query.filter_by(email=request.form['email']).first()
        if lecturer and check_password_hash(lecturer.password, request.form['password']):
            session['lecturer_id'] = lecturer.id
            return redirect(url_for('lecturer_dashboard'))
        flash('Invalid credentials')
    return render_template('lecturerlogin.html')


@app.route('/lecturer/dashboard')
def lecturer_dashboard():
    if 'lecturer_id' not in session:
        return redirect(url_for('lecturer_login'))
    
    # ... session check ...
    lecturer = Lecturer.query.get(session['lecturer_id'])
    
    # Fetch ALL courses so the lecturer can choose one to add
    all_courses = Course.query.all() 
    
    return render_template('lecturerdashboard.html', 
                           lecturer=lecturer, 
                           lecturer_courses=lecturer.courses,
                           all_available_courses=all_courses)


# ====================== HELPER FUNCTIONS ======================
def parse_input(text):
    if not text: return []
    return [item.strip() for item in text.replace('\n', ',').split(',') if item.strip()]

def calculate_grade(total):
    if total >= 70: return 'A'
    if total >= 60: return 'B'
    if total >= 50: return 'C'
    if total >= 45: return 'D'
    if total >= 40: return 'E'
    return 'F'

def validate_bulk_results(names, regnos, ca_scores, exam_scores):
    errors = []
    n, r, c, e = parse_input(names), parse_input(regnos), parse_input(ca_scores), parse_input(exam_scores)

    if not n:
        errors.append("At least one student entry is required.")
    elif not (len(n) == len(r) == len(c) == len(e)):
        errors.append("All fields must have the same number of entries.")
    
    # Check if scores are valid numbers
    try:
        [float(x) for x in c]
        [float(x) for x in e]
    except ValueError:
        errors.append("Scores must be numeric values.")
    
    return errors

# ====================== MAIN ROUTES ======================
@app.route('/upload-results', methods=['GET', 'POST'])
def upload_results():
    if 'lecturer_id' not in session:
        return redirect(url_for('lecturer_login'))
    
    if request.method == 'POST':
        names = parse_input(request.form.get('studentNamesBulk'))
        regnos = parse_input(request.form.get('regNumbersBulk'))
        ca_scores = [float(x) for x in parse_input(request.form.get('caScoresBulk'))]
        exam_scores = [float(x) for x in parse_input(request.form.get('examScoresBulk'))]

        errors = validate_bulk_results(
            request.form.get('studentNamesBulk'), 
            request.form.get('regNumbersBulk'), 
            request.form.get('caScoresBulk'), 
            request.form.get('examScoresBulk')
        )

        if errors:
            for error in errors: flash(error, "error")
            return render_template('upload_results.html', form_data=request.form)

        try:
            for i in range(len(regnos)):
                student = Student.query.filter_by(reg_number=regnos[i]).first()
                
                if not student:
                    flash(f"Student {regnos[i]} not found. Skipping...", "warning")
                    continue

                total = ca_scores[i] + exam_scores[i]
                result = Result(
                    lecturer_id=session['lecturer_id'],
                    student_id=student.id,
                    student_name=names[i],
                    reg_number=regnos[i],
                    course_code=request.form.get('courseCode'),
                    course_title=request.form.get('courseTitle'),
                    session_written=request.form.get('sessionWritten'),
                    year=request.form.get('year'),
                    semester=request.form.get('semester'),
                    ca_score=ca_scores[i],
                    exam_score=exam_scores[i],
                    total_score=total,
                    grade=calculate_grade(total)
                )
                db.session.add(result)

            db.session.commit()
            flash("Results uploaded successfully!", "success")
            return redirect(url_for('display_uploaded_results'))
        except Exception as e:
            db.session.rollback()
            flash(f"An unexpected error occurred: {str(e)}", "error")

    return render_template('upload_results.html')


@app.route('/results', methods=['GET'])
def view_results():
    if 'lecturer_id' not in session:
        return redirect(url_for('lecturer_login'))
    
    # Fetch all results, ordered by the date they were uploaded (newest first)
    all_results = Result.query.order_by(Result.uploaded_at.desc()).all()
    
    return render_template('results.html', results=all_results)


@app.route('/lecturer/add-course', methods=['POST'])
def lecturer_add_course():
    if 'lecturer_id' not in session:
        return redirect(url_for('lecturer_login'))
    
    # We now get the course_id from the form
    course_id = request.form.get('course_id')
    
    # Create the link using the ID
    new_course = LecturerCourse(
        lecturer_id=session['lecturer_id'],
        course_id=course_id
    )
    
    db.session.add(new_course)
    db.session.commit()
    
    flash('Course assigned successfully!', 'success')
    return redirect(url_for('lecturer_dashboard'))

# ====================== LECTURER COURSE & STUDENT MANAGEMENT ======================

@app.route('/lecturer/all-registrations')
def all_registrations():
    if 'lecturer_id' not in session:
        return redirect(url_for('lecturer_login'))
    
    search_query = request.args.get('q', '').strip()
    
    # Start the query joining all three relevant tables
    query = Registration.query.join(Student).join(Course)\
        .options(joinedload(Registration.student), joinedload(Registration.course))
    
    # Apply search filter
    if search_query:
        query = query.filter(
            or_(
                Student.name.ilike(f"%{search_query}%"),
                Course.course_title.ilike(f"%{search_query}%"),
                Course.course_code.ilike(f"%{search_query}%")
            )
        )
    
    registrations = query.order_by(Course.course_title, Student.name).all()
    
    # Grouping data for the UI
    grouped_data = defaultdict(list)
    for reg in registrations:
        grouped_data[reg.course].append(reg)
        
    return render_template('all_registrations.html', 
                           grouped_data=grouped_data, 
                           search_query=search_query)





if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Auto-provisions SQLite database tables if they do not exist
    app.run(debug=True)
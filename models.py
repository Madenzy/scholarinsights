from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

GRADE_SCALE = [(80, 'A'), (65, 'B'), (50, 'C'), (40, 'D'), (0, 'F')]


def calculate_grade(score):
    for boundary, letter in GRADE_SCALE:
        if score >= boundary:
            return letter
    return 'F'


# Parent ↔ Student many-to-many
parent_student = db.Table(
    'parent_student',
    db.Column('parent_user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('student_id', db.Integer, db.ForeignKey('students.id'), primary_key=True),
)


class School(db.Model):
    __tablename__ = 'schools'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(50))
    address = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='school', lazy=True, foreign_keys='Student.school_id')
    reports = db.relationship('Report', backref='school', lazy=True, foreign_keys='Report.school_id')


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150))
    # roles: super_admin | school_admin | teacher | student | parent
    role = db.Column(db.String(20), nullable=False, default='teacher')
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school = db.relationship('School', backref='users')
    # For teachers: classes they own
    classes = db.relationship('Class', backref='teacher', lazy=True, foreign_keys='Class.teacher_id')
    # For parents: linked children
    children = db.relationship('Student', secondary=parent_student, backref='parents', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_super_admin(self):
        return self.role == 'super_admin'

    @property
    def is_admin(self):
        return self.role == 'school_admin'

    @property
    def is_staff(self):
        return self.role in ('school_admin', 'teacher')

    @property
    def is_portal_user(self):
        return self.role in ('student', 'parent')

    @property
    def display_name(self):
        return self.full_name or self.username


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    grade_level = db.Column(db.String(50))
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='class_', lazy=True)


class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    reg_number = db.Column(db.String(50), nullable=False)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10))
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    # Optional login account for this student
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    login_user = db.relationship(
        'User', foreign_keys=[user_id], backref='student_profile', uselist=False
    )
    reports = db.relationship('Report', backref='student', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('reg_number', 'school_id', name='uq_reg_school'),
    )

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'

    @property
    def has_account(self):
        return self.user_id is not None


class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)

    grades = db.relationship('Grade', backref='subject', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('code', 'school_id', name='uq_code_school'),
    )


class AcademicTerm(db.Model):
    __tablename__ = 'academic_terms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    term_number = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)

    reports = db.relationship('Report', backref='term', lazy=True)


class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    term_id = db.Column(db.Integer, db.ForeignKey('academic_terms.id'), nullable=False)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    teacher_comment = db.Column(db.Text)
    head_comment = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft | published
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    grades = db.relationship('Grade', backref='report', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('student_id', 'term_id', name='uq_student_term'),
    )

    @property
    def average_score(self):
        if not self.grades:
            return None
        return round(sum(g.score for g in self.grades) / len(self.grades), 1)

    @property
    def overall_grade(self):
        avg = self.average_score
        return calculate_grade(avg) if avg is not None else '-'


class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    grade_letter = db.Column(db.String(2))
    comment = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint('report_id', 'subject_id', name='uq_report_subject'),
    )

from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from flask_mail import Mail
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
mail = Mail()

# Seeded onto every new school (and backfilled onto existing ones) as a
# starting point; schools can add/edit/remove bands from there via the
# Grading settings page.
DEFAULT_GRADE_BANDS = [
    # (letter, min_score, remark, is_pass)
    ('A', 80, 'Excellent', True),
    ('B', 65, 'Well done', True),
    ('C', 50, 'Satisfactory', True),
    ('D', 40, 'Needs improvement', True),
    ('F', 0, 'Work harder', False),
]


def calculate_grade(score, bands):
    """Return the GradeBand whose range a score falls into.

    `bands` is any iterable of objects with .min_score/.letter/.is_pass/.remark
    (i.e. a school's GradeBand rows). Returns None if `bands` is empty.
    """
    ordered = sorted(bands, key=lambda b: b.min_score, reverse=True)
    for band in ordered:
        if score >= band.min_score:
            return band
    return ordered[-1] if ordered else None


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
    logo_filename = db.Column(db.String(255))
    theme_color = db.Column(db.String(7), nullable=False, default='#4f46e5')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    students = db.relationship('Student', backref='school', lazy=True, foreign_keys='Student.school_id')
    reports = db.relationship('Report', backref='school', lazy=True, foreign_keys='Report.school_id')
    grade_bands = db.relationship(
        'GradeBand', backref='school', lazy=True, cascade='all, delete-orphan',
        order_by='GradeBand.min_score.desc()',
    )


class GradeBand(db.Model):
    """One letter grade's range for a school, e.g. A starting at 80%."""
    __tablename__ = 'grade_bands'
    id = db.Column(db.Integer, primary_key=True)
    school_id = db.Column(db.Integer, db.ForeignKey('schools.id'), nullable=False)
    letter = db.Column(db.String(4), nullable=False)
    min_score = db.Column(db.Float, nullable=False)
    remark = db.Column(db.String(50))
    is_pass = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = (
        db.UniqueConstraint('school_id', 'letter', name='uq_gradeband_school_letter'),
    )


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
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    login_user = db.relationship(
        'User', foreign_keys=[user_id],
        backref=db.backref('student_profile', uselist=False),
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
    def overall_band(self):
        avg = self.average_score
        if avg is None:
            return None
        return calculate_grade(avg, self.school.grade_bands)

    @property
    def overall_grade(self):
        band = self.overall_band
        return band.letter if band else '-'

    @property
    def overall_is_pass(self):
        band = self.overall_band
        return band.is_pass if band else True


class Grade(db.Model):
    __tablename__ = 'grades'
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    score = db.Column(db.Float, nullable=False)
    grade_letter = db.Column(db.String(4))
    is_pass = db.Column(db.Boolean, nullable=False, default=True)
    auto_remark = db.Column(db.String(50))
    comment = db.Column(db.String(255))

    __table_args__ = (
        db.UniqueConstraint('report_id', 'subject_id', name='uq_report_subject'),
    )

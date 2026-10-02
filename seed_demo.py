"""
Seed a fully populated demo school for testing.

Creates a school, an admin, teachers, classes, subjects, academic terms,
students, parents, and reports with grades across two completed terms.
Safe to re-run: if the demo school already exists, it (and everything
under it) is deleted first and recreated fresh.

Usage:
    python seed_demo.py
"""
import random
from datetime import date

from app import create_app
from models import (
    db, School, User, Class, Subject, AcademicTerm, Student, Report, Grade,
    calculate_grade,
)

random.seed(42)

SCHOOL_NAME = 'Riverside High School'
DEMO_PASSWORD = 'TestPass123!'

FIRST_NAMES_M = [
    'Tendai', 'Tinashe', 'Tapiwa', 'Farai', 'Kudzai', 'Simba', 'Tatenda',
    'Munyaradzi', 'Blessing', 'Takudzwa', 'Brian', 'Kelvin', 'Wayne', 'Ryan',
]
FIRST_NAMES_F = [
    'Chiedza', 'Rumbidzai', 'Ropafadzo', 'Anesu', 'Rufaro', 'Nyasha', 'Vimbai',
    'Panashe', 'Tariro', 'Fadzai', 'Michelle', 'Natasha', 'Faith', 'Grace',
]
SURNAMES = [
    'Moyo', 'Ncube', 'Dube', 'Sibanda', 'Chirwa', 'Mhlanga', 'Chikwava',
    'Mutasa', 'Gumbo', 'Chaka', 'Madziva', 'Zhou', 'Mabhena', 'Chigumba',
    'Nyathi', 'Mapfumo', 'Chikafu', 'Mukwena', 'Banda', 'Phiri',
]

CLASSES = [
    ('Form 1A', 'Form 1'), ('Form 1B', 'Form 1'),
    ('Form 2A', 'Form 2'), ('Form 2B', 'Form 2'),
    ('Form 3A', 'Form 3'), ('Form 4A', 'Form 4'),
]

SUBJECTS = [
    ('Mathematics', 'MATH'), ('English Language', 'ENG'), ('Combined Science', 'SCI'),
    ('Biology', 'BIO'), ('History', 'HIST'), ('Geography', 'GEO'),
    ('Computer Science', 'ICT'), ('Shona', 'SHO'),
]

TEACHER_COMMENTS = {
    'A': "Excellent work this term. Keeps up a consistently high standard.",
    'B': "A solid, reliable performance. Room to push for even more.",
    'C': "Satisfactory progress. Needs to be more consistent with homework.",
    'D': "Struggling with the core concepts. Extra practice recommended.",
    'F': "Serious concerns here. Needs urgent extra support and revision.",
}
HEAD_COMMENTS = {
    'A': "A credit to the school. Keep it up.",
    'B': "Good overall term. Encouraged to aim higher.",
    'C': "An average term. More focus needed next term.",
    'D': "Below expectations. Please see the class teacher.",
    'F': "Needs immediate attention and a support plan.",
}


def grade_band(letter):
    return letter if letter in TEACHER_COMMENTS else 'F'


def make_reg_number(i):
    return f'2026/{i:03d}'


def main():
    app = create_app()
    with app.app_context():
        existing = School.query.filter_by(name=SCHOOL_NAME).first()
        if existing:
            print(f'Removing existing "{SCHOOL_NAME}" and all its data...')
            Grade.query.filter(Grade.report_id.in_(
                db.session.query(Report.id).filter_by(school_id=existing.id)
            )).delete(synchronize_session=False)
            Report.query.filter_by(school_id=existing.id).delete(synchronize_session=False)
            Student.query.filter_by(school_id=existing.id).update({'user_id': None})
            db.session.execute(
                db.text('DELETE FROM parent_student WHERE student_id IN '
                        '(SELECT id FROM students WHERE school_id = :sid)'),
                {'sid': existing.id},
            )
            Student.query.filter_by(school_id=existing.id).delete(synchronize_session=False)
            Class.query.filter_by(school_id=existing.id).update({'teacher_id': None})
            User.query.filter_by(school_id=existing.id).delete(synchronize_session=False)
            Class.query.filter_by(school_id=existing.id).delete(synchronize_session=False)
            Subject.query.filter_by(school_id=existing.id).delete(synchronize_session=False)
            AcademicTerm.query.filter_by(school_id=existing.id).delete(synchronize_session=False)
            db.session.delete(existing)
            db.session.commit()

        school = School(
            name=SCHOOL_NAME,
            email='admin@riversidehigh.example',
            phone='+263 77 123 4567',
            address='14 Riverside Drive, Harare',
            theme_color='#1E6F46',
        )
        db.session.add(school)
        db.session.flush()

        admin = User(
            username='riverside_admin', email='admin@riversidehigh.example',
            full_name='Grace Mapfumo', role='school_admin', school_id=school.id,
        )
        admin.set_password(DEMO_PASSWORD)
        db.session.add(admin)

        subjects = []
        for name, code in SUBJECTS:
            subject = Subject(name=name, code=code, school_id=school.id)
            db.session.add(subject)
            subjects.append(subject)

        terms = []
        term_specs = [
            ('2026 - Term 1', 2026, 1, date(2026, 1, 13), date(2026, 4, 10)),
            ('2026 - Term 2', 2026, 2, date(2026, 5, 5), date(2026, 8, 7)),
            ('2026 - Term 3', 2026, 3, date(2026, 9, 7), date(2026, 12, 4)),
        ]
        for name, year, num, start, end in term_specs:
            term = AcademicTerm(name=name, year=year, term_number=num,
                                 start_date=start, end_date=end, school_id=school.id)
            db.session.add(term)
            terms.append(term)
        db.session.flush()

        teachers = []
        used_names = set()

        def unique_name():
            while True:
                pool = FIRST_NAMES_M + FIRST_NAMES_F
                name = f'{random.choice(pool)} {random.choice(SURNAMES)}'
                if name not in used_names:
                    used_names.add(name)
                    return name

        for _ in CLASSES:
            full_name = unique_name()
            username = full_name.lower().replace(' ', '.')
            teacher = User(
                username=username, email=f'{username}@riversidehigh.example',
                full_name=full_name, role='teacher', school_id=school.id,
            )
            teacher.set_password(DEMO_PASSWORD)
            db.session.add(teacher)
            teachers.append(teacher)
        db.session.flush()

        classes = []
        for (name, grade_level), teacher in zip(CLASSES, teachers):
            klass = Class(name=name, grade_level=grade_level, teacher_id=teacher.id, school_id=school.id)
            db.session.add(klass)
            classes.append(klass)
        db.session.flush()

        students = []
        reg_counter = 1
        birth_year_by_grade = {'Form 1': 2012, 'Form 2': 2011, 'Form 3': 2010, 'Form 4': 2009}
        for klass in classes:
            for _ in range(6):
                gender = random.choice(['Male', 'Female'])
                first = random.choice(FIRST_NAMES_M if gender == 'Male' else FIRST_NAMES_F)
                last = random.choice(SURNAMES)
                dob_year = birth_year_by_grade[klass.grade_level]
                student = Student(
                    reg_number=make_reg_number(reg_counter),
                    first_name=first, last_name=last, gender=gender,
                    date_of_birth=date(dob_year, random.randint(1, 12), random.randint(1, 28)),
                    class_id=klass.id, school_id=school.id,
                )
                reg_counter += 1
                db.session.add(student)
                students.append(student)
        db.session.flush()

        # A handful of students get portal logins
        portal_students = random.sample(students, 6)
        for i, student in enumerate(portal_students, start=1):
            username = f'{student.first_name}.{student.last_name}'.lower()
            user = User(
                username=username, email=f'{username}@student.riversidehigh.example',
                full_name=student.full_name, role='student', school_id=school.id,
            )
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            db.session.flush()
            student.user_id = user.id

        # A handful of parents, each linked to 1-2 students
        parent_pool = list(students)
        random.shuffle(parent_pool)
        created_parents = []
        while len(parent_pool) >= 2 and len(created_parents) < 5:
            kids = [parent_pool.pop(), parent_pool.pop()] if random.random() < 0.4 else [parent_pool.pop()]
            surname = kids[0].last_name
            full_name = f'{random.choice(FIRST_NAMES_M + FIRST_NAMES_F)} {surname}'
            username = f'parent.{surname}.{len(created_parents)}'.lower()
            parent = User(
                username=username, email=f'{username}@example.com',
                full_name=full_name, role='parent', school_id=school.id,
            )
            parent.set_password(DEMO_PASSWORD)
            parent.children = kids
            db.session.add(parent)
            created_parents.append(parent)
        db.session.flush()

        # Reports + grades for the two completed terms
        for term in terms[:2]:
            for student in students:
                # Each student has an underlying ability level so grades correlate across subjects
                ability = random.gauss(68, 16)
                report = Report(student_id=student.id, term_id=term.id, school_id=school.id, status='published')
                db.session.add(report)
                db.session.flush()

                scores = []
                for subject in subjects:
                    score = max(5, min(100, round(random.gauss(ability, 10))))
                    scores.append(score)
                    db.session.add(Grade(
                        report_id=report.id, subject_id=subject.id, score=score,
                        grade_letter=calculate_grade(score),
                    ))
                avg = sum(scores) / len(scores)
                band = grade_band(calculate_grade(avg))
                report.teacher_comment = TEACHER_COMMENTS[band]
                report.head_comment = HEAD_COMMENTS[band]

        db.session.commit()

        print(f'\nSeeded "{SCHOOL_NAME}" (school id {school.id})')
        print(f'  {len(classes)} classes, {len(subjects)} subjects, {len(terms)} terms')
        print(f'  {len(students)} students, {len(teachers)} teachers, {len(created_parents)} parents')
        print(f'  Reports generated for: {terms[0].name}, {terms[1].name} ({terms[2].name} left empty)')
        print(f'\nAll demo accounts share the password: {DEMO_PASSWORD}\n')
        print(f'  School admin : {admin.username}')
        print(f'  Teachers     : {", ".join(t.username for t in teachers)}')
        print(f'  Students     : {", ".join(u.username for u in User.query.filter_by(school_id=school.id, role="student"))}')
        print(f'  Parents      : {", ".join(p.username for p in created_parents)}')


if __name__ == '__main__':
    main()

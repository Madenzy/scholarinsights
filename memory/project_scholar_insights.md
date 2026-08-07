---
name: project-scholar-insights
description: Scholar Insights Hub — Flask + PostgreSQL student report management system built for schools
metadata:
  type: project
---

This project was converted from a static landing page into a full Flask + PostgreSQL web app.

**Why:** User asked to build a student report management system using Flask and PostgreSQL.

**Stack:** Flask 3.0, Flask-SQLAlchemy, Flask-Login, psycopg2-binary, Jinja2 templates.

**Key models:** User (admin/teacher roles), Class, Student, Subject, AcademicTerm, Report, Grade.

**Grade scale:** A ≥80, B ≥65, C ≥50, D ≥40, F <40.

**How to apply:** When adding features, follow the existing blueprint pattern in `routes/`. All templates extend `templates/base.html` with a sidebar layout. Auth templates use the standalone `auth-page` layout (no sidebar).

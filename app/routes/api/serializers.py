def serialize_school(school):
    if not school:
        return None
    return {
        'id': school.id,
        'name': school.name,
        'logo_url': f'/static/uploads/logos/{school.logo_filename}' if school.logo_filename else None,
    }


def serialize_user(user):
    if not user:
        return None
    return {
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'full_name': user.full_name,
        'display_name': user.display_name,
        'role': user.role,
        'is_super_admin': user.is_super_admin,
        'is_admin': user.is_admin,
        'is_staff': user.is_staff,
        'is_portal_user': user.is_portal_user,
        'school': serialize_school(user.school),
    }

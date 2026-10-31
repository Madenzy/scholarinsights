import csv
import io
import re
from datetime import date, datetime

from openpyxl import load_workbook

# Canonical field -> accepted header aliases (already lowercased, non-alphanumeric stripped)
FIELD_ALIASES = {
    'reg_number': {
        'regnumber', 'regno', 'reg', 'registrationnumber', 'registrationno',
        'admissionnumber', 'admissionno', 'studentid', 'idnumber', 'id',
    },
    'first_name': {
        'firstname', 'fname', 'givenname', 'forename',
    },
    'last_name': {
        'lastname', 'lname', 'surname', 'familyname',
    },
    'full_name': {
        'name', 'fullname', 'studentname',
    },
    'gender': {
        'gender', 'sex',
    },
    'date_of_birth': {
        'dateofbirth', 'dob', 'birthdate', 'birthday',
    },
    'class': {
        'class', 'classname', 'classroom', 'grade', 'gradelevel', 'form', 'section',
    },
}

DATE_FORMATS = (
    '%Y-%m-%d', '%Y/%m/%d',
    '%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y',
    '%m/%d/%Y', '%m-%d-%Y',
    '%d %B %Y', '%d %b %Y',
    '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y',
    '%d-%b-%Y', '%d-%B-%Y',
)

TEXT_ENCODINGS = ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1')


class ImportError_(Exception):
    pass


def _clean_key(key):
    return re.sub(r'[^a-z0-9]', '', (key or '').strip().lower())


def _alias_map():
    mapping = {}
    for canonical, aliases in FIELD_ALIASES.items():
        mapping[canonical] = canonical
        for alias in aliases:
            mapping[alias] = canonical
    return mapping


def parse_upload(file):
    """Read an uploaded CSV/TSV/TXT/XLSX file and return (rows, canonical_fields_found).

    `rows` is a list of dicts keyed by canonical field name (reg_number, first_name,
    last_name, full_name, gender, date_of_birth, class), with any unmapped columns
    ignored. Blank rows are skipped.
    """
    filename = (file.filename or '').lower()

    if filename.endswith(('.xlsx', '.xlsm')):
        raw_rows, header_row = _read_excel(file)
    elif filename.endswith(('.csv', '.tsv', '.txt')):
        raw_rows, header_row = _read_delimited(file)
    else:
        raise ImportError_(
            'Unsupported file type. Please upload a .csv, .tsv, .txt, or .xlsx file.'
        )

    if not header_row:
        raise ImportError_('The file appears to be empty.')

    alias_map = _alias_map()
    header_to_canonical = {}
    for original in header_row:
        key = _clean_key(original)
        if key in alias_map:
            header_to_canonical[original] = alias_map[key]

    found_fields = set(header_to_canonical.values())
    has_reg = 'reg_number' in found_fields
    has_name = ('first_name' in found_fields and 'last_name' in found_fields) or 'full_name' in found_fields
    if not has_reg or not has_name:
        raise ImportError_(
            'Could not find registration number and name columns. Expected headers such as '
            '"reg_number" (or Reg No / Admission No) plus either "first_name" & "last_name", '
            'or a single "name" column.'
        )

    rows = []
    for raw in raw_rows:
        row = {}
        for original, value in raw.items():
            canonical = header_to_canonical.get(original)
            if not canonical:
                continue
            row[canonical] = value
        if any((str(v).strip() if v is not None else '') for v in row.values()):
            rows.append(row)

    return rows


def _read_excel(file):
    try:
        wb = load_workbook(file, read_only=True, data_only=True)
    except Exception as exc:
        raise ImportError_(f'Could not read the Excel file: {exc}')

    sheet = wb.worksheets[0]
    rows_iter = sheet.iter_rows(values_only=True)
    try:
        header_row = [str(h).strip() if h is not None else '' for h in next(rows_iter)]
    except StopIteration:
        return [], []

    raw_rows = []
    for values in rows_iter:
        if values is None or all(v is None or str(v).strip() == '' for v in values):
            continue
        row = {}
        for i, header in enumerate(header_row):
            if not header:
                continue
            value = values[i] if i < len(values) else None
            row[header] = value
        raw_rows.append(row)

    return raw_rows, [h for h in header_row if h]


def _read_delimited(file):
    raw_bytes = file.stream.read()
    text = None
    for encoding in TEXT_ENCODINGS:
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise ImportError_('Could not read the file. Please upload a UTF-8 encoded file.')

    text = text.replace('\r\n', '\n').replace('\r', '\n')

    sample = text[:4096]
    delimiter = ','
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
        delimiter = dialect.delimiter
    except csv.Error:
        first_line = sample.split('\n', 1)[0]
        for candidate in ('\t', ';', '|', ','):
            if candidate in first_line:
                delimiter = candidate
                break

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return [], []

    header_row = [h.strip() for h in reader.fieldnames if h]
    raw_rows = []
    for raw in reader:
        if raw is None:
            continue
        row = {k.strip(): v for k, v in raw.items() if k}
        if any((v or '').strip() for v in row.values() if v is not None):
            raw_rows.append(row)

    return raw_rows, header_row


def normalize_gender(value):
    if not value:
        return ''
    v = str(value).strip().lower()
    if v in ('m', 'male', 'boy'):
        return 'Male'
    if v in ('f', 'female', 'girl'):
        return 'Female'
    if not v:
        return ''
    return str(value).strip().title()


def parse_date(value):
    """Parse a date from a string, datetime, or date. Returns None for blank input.
    Raises ValueError if the value is present but unparseable.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    raise ValueError(text)


def split_full_name(name):
    parts = str(name).strip().split(None, 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ''
    return '', ''

# ui/utils.py
import os
import csv
from PyQt6.QtWidgets import QMessageBox
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter

def detect_language(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    ext_map = {
        '.py': 'python', '.c': 'c', '.cpp': 'cpp', '.cc': 'cpp',
        '.rb': 'ruby', '.pl': 'perl', '.php': 'php', '.js': 'javascript',
        '.html': 'html', '.sh': 'bash', '.java': 'java',
    }
    return ext_map.get(ext, 'text')

def get_highlighted_html(code, language):
    try:
        lexer = get_lexer_by_name(language)
    except Exception:
        lexer = get_lexer_by_name('text')
    css = '. { background: transparent !important; }'
    formatter = HtmlFormatter(style='monokai', full=True, noclasses=True, cssstyles=css)
    return highlight(code, lexer, formatter)

def parse_data(filename):
    exploits = []
    with open(filename, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            exploits.append({
                'signatures': row.get('codes', '').replace(';', ', '),
                'description': row.get('description', ''),
                'type': row.get('type', ''),
                'platform': row.get('platform', ''),
                'link': f"https://www.exploit-db.com/exploits/{row.get('id', '')}",
                'author': row.get('author', ''),
                'date': row.get('date_published', ''),
                'verified': row.get('verified', ''),
                'file_path': row.get('file', '')
            })
    return exploits

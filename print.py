from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import os

# Set up Jinja2 environment
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
env = Environment(loader=FileSystemLoader(template_dir))

# Patient data (you can modify these values or load from a database/API)
patient_data = {
    'nik': '3174092508760012',
    'nama': 'Agus Prasetyo Hartoyo',
    'tanggal_lahir': '25-08-1976',
    'jenis_kelamin': 'Laki-laki',
    'kelompok': '-'
}

# Load and render the main template
template = env.get_template('reports.html')
html_content = template.render(**patient_data)

# Convert to PDF using WeasyPrint
HTML(string=html_content, base_url=template_dir).write_pdf(
    "templates/reports.pdf",
    stylesheets=[CSS("templates/print.css")]
)

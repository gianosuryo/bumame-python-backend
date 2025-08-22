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

prescreening_test_data = [
    {
        "title": "I. RIWAYAT PENYAKIT SENDIRI",
        "data": [
            ["a. Riwayat Penyakit", "Tidak Ada"],
            ["a. Riwayat Penyakit", "Tidak Ada"]
        ]
    },
]

physical_examination_data = [["Kulit","Normal"]]
vital_signs_data = [["Tensi (mmHg)", "-"]]
conclusions_data = [["Hasil Darah", "Peningkatan Trombosit (449,000 *), Peningkatan Leukosit (12,750 *), Peningkatan SGPT / ALT (65 *), Peningkatan Asam Urat (9.4 *), Peningkatan Glukosa 2jpp (143 *), Peningkatan Kolesterol Total (220 *)"], ["Urin", "H Keruh *, Proteinuria (H Positif 3 *), Kristaluria (H Amorf (+) *)"], ["Tanda Vital", "Prahipertensi (116/85), Obesitas Kelas 1 (26.6), Astigmatisme OS"], ["Pemeriksaan Fisik", "Caries, Calculus"], ["Rontgen Thorax", "•⁠  ⁠Tidak tampak bronkopneumonia / pneumonia / TB.<br>•⁠  ⁠Tidak tampak kardiomegali."], ["EKG", "Normal Sinus Rhythm"], ["Audiometri", "Ambang batas normal telinga kanan dan kiri"]]
advice_data = "Olahraga ringan rutin 3x dalam seminggu dalam durasi 30-45 menit, menjaga asupan makan, cukup asupan air putih, makan bergizi dan nutrisi seimbang, beristirahat yang cukup, mengelola stres dengan baik, lakukan pemeriksaan tekanan darah secara berkala di fasilitas kesehatan, diet rendah lemak, konsultasi dengan dokter spesialis gizi terkait berat badan berlebih, lakukan pemeriksaan ke dokter gigi terkait pemeriksaan gigi, konsultasi dengan dokter spesialis penyakit dalam terkait hasil laboratorium dan urin. Lakukan MCU 1 tahun mendatang."
analysis_data = "Fit with note"

lab_header_data = {
    "no_barcode": "2507283091",
    "tanggal_periksa": "2025-07-28 00:00:00",
    "nama": "Melita",
    "tgl_lahir": "1989-07-21 00:00:00",
    "jenis_kelamin": "Perempuan",
    "departemen": "Export Import",
    "jabatan": "Foreman",
    "lokasi_pengambilan": "HO",
    "perusahaan": "PT. Fajar Surya Wisesa Tbk.",
    "nohp": "",
    "no_identitas_ktp_sim": "",
    "alamat": "JAKARTA PUSAT ADMINISTRASI",
    "kota": ".",
    "npk": "32002999"
}

lab_section_data = [
    {
        "title": "HEMATOLOGI",
        "tests": [
            {
                "name": "Hemoglobin (HGB)",
                "hasil": "15.0 g/dL",
                "satuan": "g/dL",
                "nilai_rujukan": "13.5 - 17.5",
                "keterangan": "Normal"
            }
        ]
    }
]

electromedical_data = [
    {
        "title": "Pemeriksaan Radiologi - Rontgen Thorax",
        "data": [
            ["Kesimpulan", "Tidak tampak bronkopneumonia / pneumonia / TB."],
            ["Saran", "Pola hidup sehat dan olahraga teratur"]
        ],
        "url": "sample-elektromedis.png"
    },
    {
        "title": "Pemeriksaan Elektrokardiografi (EKG)",
        "data": [
            ["Kesimpulan", "Sinus Rhythm, Borderline LAD"],
            ["Saran", "Pola hidup sehat dan olahraga teratur"]
        ],
        "url": "sample-elektromedis.png"
    }
]

dokter_pemeriksa_data = {
    "name": "dr. Muhammad Reza Kurniawan",
    "title": "Dokter Pemeriksa",
    "signature_url": "internal_reza_signature.png"
}

penanggung_jawab_lab_data = {
    "name": "dr. Muhammad Reza Kurniawan",
    "title": "Penanggung Jawab Laboratorium",
    "signature_url": "internal_reza_signature.png"
}

diperiksa_oleh_data = {
    "name": "dr. Muhammad Reza Kurniawan",
    "title": "Diperiksa Oleh",
    "signature_url": "internal_reza_signature.png"
}

# Load and render the main template
template = env.get_template('reports.html')
html_content = template.render(patient_data=patient_data, prescreening_test_data=prescreening_test_data, physical_examination_data=physical_examination_data, vital_signs_data=vital_signs_data, conclusions_data=conclusions_data, advice_data=advice_data, analysis_data=analysis_data, lab_header_data=lab_header_data, lab_section_data=lab_section_data, electromedical_data=electromedical_data, dokter_pemeriksa_data=dokter_pemeriksa_data, penanggung_jawab_lab_data=penanggung_jawab_lab_data, diperiksa_oleh_data=diperiksa_oleh_data)

# Convert to PDF using WeasyPrint
HTML(string=html_content, base_url=template_dir).write_pdf(
    "templates/reports.pdf",
    stylesheets=[CSS("templates/print.css")]
)

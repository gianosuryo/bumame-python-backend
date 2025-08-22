from typing import Optional, Dict, TypedDict
from langgraph.graph import StateGraph, END, START
from config.logging import logger
from helper.singleton import singleton
from google.cloud import storage
import time
import os
import uuid
import subprocess
import platform
import requests
import io
import fitz  # PyMuPDF
from PIL import Image
import re
from PIL import ImageChops
from helper.database import db_postgres
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime

LOG_SIZE = 100
class CustomizeVariableReport(TypedDict):
    """Customize variable report"""
    header_image_url: Optional[str]
    footer_image_url: Optional[str]
    penanggung_jawab_hasil: Optional[str]
    perujuk_lab: Optional[str]
    terms_analisis_fit: Optional[str]
    terms_analisis_fit_with_note: Optional[str]
    terms_analisis_unfit_temporary: Optional[str]
    dokter_internal: Optional[str]
    penanggung_jawab_hasil_signature_url: Optional[str]
    dokter_internal_signature_url: Optional[str]
    perujuk_lab_signature_url: Optional[str]

class _ReportGeneratorState(TypedDict):
    """State for report generation process"""
    patient_id: str
    patient_data: Optional[Dict]
    formatted_patient_data: Optional[Dict]
    formatted_prescreening_test_data: Optional[Dict]
    formatted_physical_examination_data: Optional[Dict]
    formatted_vital_signs_data: Optional[Dict]
    formatted_conclusions_data: Optional[Dict]
    formatted_advice_data: Optional[Dict]
    formatted_analysis_data: Optional[Dict]
    formatted_lab_header_data: Optional[Dict]
    formatted_lab_section_data: Optional[Dict]
    formatted_electromedical_data: Optional[Dict]
    formatted_dokter_pemeriksa_data: Optional[Dict]
    formatted_penanggung_jawab_lab_data: Optional[Dict]
    formatted_diperiksa_oleh_data: Optional[Dict]
    files: Optional[Dict[str, str]]
    error: Optional[str]
    customize_variable_report: Optional[CustomizeVariableReport]

@singleton
class AgentReportGenerator:
    def __init__(self):
        # Define state schema
        self.state_graph = StateGraph(_ReportGeneratorState)
        
        # Add nodes - removing the reference to _load_patient_data
        self.state_graph.add_node("formatting_patient_data", self._formatting_patient_data)
        self.state_graph.add_node("formatting_prescreening_test_data", self._formatting_prescreening_test_data)
        self.state_graph.add_node("formatting_physical_examination_data", self._formatting_physical_examination_data)
        self.state_graph.add_node("formatting_vital_signs_data", self._formatting_vital_signs_data)
        self.state_graph.add_node("formatting_conclusions_advice_data", self._formatting_conclusions_advice_data)
        self.state_graph.add_node("formatting_lab_section_data", self._formatting_lab_section_data)
        self.state_graph.add_node("formatting_electromedical_data", self._formatting_electromedical_data)
        self.state_graph.add_node("formatting_worker_data", self._formatting_worker_data)

        self.state_graph.add_node("generate_report", self._generate_report)
        self.state_graph.add_node("cleanup", self._cleanup_files)
        
        # Define edges - starting directly from generate_report
        self.state_graph.add_edge(START, "formatting_patient_data")
        self.state_graph.add_edge("formatting_patient_data", "formatting_prescreening_test_data")
        self.state_graph.add_edge("formatting_prescreening_test_data", "formatting_physical_examination_data")
        self.state_graph.add_edge("formatting_physical_examination_data", "formatting_vital_signs_data")
        self.state_graph.add_edge("formatting_vital_signs_data", "formatting_conclusions_advice_data")
        self.state_graph.add_edge("formatting_conclusions_advice_data", "formatting_lab_section_data")
        self.state_graph.add_edge("formatting_lab_section_data", "formatting_electromedical_data")
        self.state_graph.add_edge("formatting_electromedical_data", "formatting_worker_data")
        self.state_graph.add_edge("formatting_worker_data", "generate_report")
        
        self.state_graph.add_edge("generate_report", "cleanup")
        self.state_graph.add_edge("cleanup", END)
                
        # Compile the graph
        self.chain = self.state_graph.compile()

    def run_with_data(self, patient_data: Dict) -> bool:
        """Run the report generation process with provided patient data"""
        start_time = time.time()
        logger.info(f"Starting report generation for patient {patient_data['patient_id']}")
        
        try:
            # Initialize state with provided data
            customize_variable_report = CustomizeVariableReport(
                header_image_url=None,
                footer_image_url=None,
                penanggung_jawab_hasil=None,
                perujuk_lab=None,
                terms_analisis_fit=None,
                dokter_internal=None,
                penanggung_jawab_hasil_signature_url=None,
                dokter_internal_signature_url=None,
                perujuk_lab_signature_url=None,
            )
            
            state: _ReportGeneratorState = {
                "patient_id": patient_data['patient_id'],
                "patient_data": patient_data,
                "files": None,
                "error": None,
                "customize_variable_report": customize_variable_report
            }
            
            # Run the graph
            final_state = self.chain.invoke(state)
            
            if final_state.get("error"):
                raise Exception(final_state["error"])
            
            execution_time = time.time() - start_time
            logger.info(f"Report generation completed in {execution_time:.2f} seconds")
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

    def _formatting_patient_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format patient data"""
        try:
            patient_data = {
                'nik': '3174092508760012',
                'nama': 'Agus Prasetyo Hartoyo',
                'tanggal_lahir': '25-08-1976',
                'jenis_kelamin': 'Laki-laki',
                'kelompok': '-'
            }
            state["formatted_patient_data"] = patient_data
        except Exception as e:
            logger.error(f"Error formatting patient data: {str(e)}")
            raise

        return state

    def _formatting_prescreening_test_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format prescreening test data"""
        try:
            prescreening_test_data = [
                {
                    "title": "I. RIWAYAT PENYAKIT SENDIRI",
                    "data": [
                        ["a. Riwayat Penyakit", "Tidak Ada"],
                        ["a. Riwayat Penyakit", "Tidak Ada"]
                    ]
                },
            ]

            state["formatted_prescreening_test_data"] = prescreening_test_data
        except Exception as e:
            logger.error(f"Error formatting prescreening test data: {str(e)}")
            raise

        return state

    def _formatting_physical_examination_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format physical examination data"""
        try:
            physical_examination_data = [["Kulit","Normal"]]
            state["formatted_physical_examination_data"] = physical_examination_data
        except Exception as e:
            logger.error(f"Error formatting physical examination data: {str(e)}")
            raise
        
        return state

    def _formatting_vital_signs_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format vital signs data"""
        try:
            vital_signs_data = [["Tensi (mmHg)", "-"]]
            state["formatted_vital_signs_data"] = vital_signs_data
        except Exception as e:
            logger.error(f"Error formatting vital signs data: {str(e)}")
            raise
        
        return state

    def _formatting_conclusions_advice_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format conclusions and advice data"""
        try:
            conclusions_data = [["Hasil Darah", "Peningkatan Trombosit (449,000 *), Peningkatan Leukosit (12,750 *), Peningkatan SGPT / ALT (65 *), Peningkatan Asam Urat (9.4 *), Peningkatan Glukosa 2jpp (143 *), Peningkatan Kolesterol Total (220 *)"], ["Urin", "H Keruh *, Proteinuria (H Positif 3 *), Kristaluria (H Amorf (+) *)"], ["Tanda Vital", "Prahipertensi (116/85), Obesitas Kelas 1 (26.6), Astigmatisme OS"], ["Pemeriksaan Fisik", "Caries, Calculus"], ["Rontgen Thorax", "•⁠  ⁠Tidak tampak bronkopneumonia / pneumonia / TB.<br>•⁠  ⁠Tidak tampak kardiomegali."], ["EKG", "Normal Sinus Rhythm"], ["Audiometri", "Ambang batas normal telinga kanan dan kiri"]]
            advice_data = [["Saran", "Pola hidup sehat dan olahraga teratur"]]
            analysis_data = [["Analisis", "Pola hidup sehat dan olahraga teratur"]]

            state["formatted_conclusions_data"] = conclusions_data
            state["formatted_advice_data"] = advice_data
            state["formatted_analysis_data"] = analysis_data
        except Exception as e:
            logger.error(f"Error formatting conclusions and advice data: {str(e)}")
            raise
        
        return state

    def _formatting_lab_section_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format lab section data"""
        try:
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

            state["formatted_lab_header_data"] = lab_header_data
            state["formatted_lab_section_data"] = lab_section_data
        except Exception as e:
            logger.error(f"Error formatting lab section data: {str(e)}")
            raise
        
        return state

    def _formatting_electromedical_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format electromedical data"""
        try:
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
            state["formatted_electromedical_data"] = electromedical_data
        except Exception as e:
            logger.error(f"Error formatting electromedical data: {str(e)}")
            raise
        
        return state

    def _formatting_worker_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Format worker data"""
        try:
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
            state["formatted_dokter_pemeriksa_data"] = dokter_pemeriksa_data
            state["formatted_penanggung_jawab_lab_data"] = penanggung_jawab_lab_data
            state["formatted_diperiksa_oleh_data"] = diperiksa_oleh_data
        except Exception as e:
            logger.error(f"Error formatting worker data: {str(e)}")
            raise
        
        return state

    def _generate_report(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Generate PDF report and upload directly to GCS"""
        try:            
            # Set up Jinja2 environment
            template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
            env = Environment(loader=FileSystemLoader(template_dir))
            
            # Load and render the main template
            template = env.get_template('reports.html')
            html_content = template.render(patient_data=state["formatted_patient_data"], prescreening_test_data=state["formatted_prescreening_test_data"], physical_examination_data=state["formatted_physical_examination_data"], vital_signs_data=state["formatted_vital_signs_data"], conclusions_data=state["formatted_conclusions_data"], advice_data=state["formatted_advice_data"], analysis_data=state["formatted_analysis_data"], lab_header_data=state["formatted_lab_header_data"], lab_section_data=state["formatted_lab_section_data"], electromedical_data=state["formatted_electromedical_data"], dokter_pemeriksa_data=state["formatted_dokter_pemeriksa_data"], penanggung_jawab_lab_data=state["formatted_penanggung_jawab_lab_data"], diperiksa_oleh_data=state["formatted_diperiksa_oleh_data"])

            patient_name = state["patient_data"]["identity"]["basic_info"][1][1]
            company_name = state["patient_data"]["company"]

            appointment_id = state["patient_data"]["appointment_id"]
            appointment_patient_id = state["patient_data"]["patient_id"]
            safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c.isspace()).replace(" ", "_")
            safe_company_name = "".join(c for c in company_name if c.isalnum() or c.isspace()).replace(" ", "_")

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{appointment_id}_{appointment_patient_id}_{safe_patient_name}_{safe_company_name}_{timestamp}"

            # Convert to PDF using WeasyPrint
            HTML(string=html_content, base_url=template_dir).write_pdf(
                f"temp/{filename}.pdf",
                stylesheets=[CSS("templates/print.css")]
            )
            
            return state
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

    def _cleanup_files(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """No longer needed as we clean up temporary files immediately"""
        return state
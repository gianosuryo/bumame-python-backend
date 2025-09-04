from typing import Optional, Dict, TypedDict, List
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
from typing import Tuple
from PIL import Image
import re
from PIL import ImageChops
from helper.database import db_postgres
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader
import os
from datetime import datetime, timedelta
from helper.mics import ROMAN_NUMERALS
from helper.language_mapping_medical_report import get_text
from service.translate_service import TranslateService
import string
from service.misc_service import MiscService
from helper.common import download_from_gcs

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
    need_to_cleaned_file: Optional[List[str]]
    file_path: Optional[str]
    url_file_path: Optional[str]
    files: Optional[Dict[str, str]]
    header_image_url: Optional[str]
    footer_image_url: Optional[str]
    error: Optional[str]
    customize_variable_report: Optional[CustomizeVariableReport]

@singleton
class AgentReportGenerator:
    def __init__(self):
        # Define state schema
        self.state_graph = StateGraph(_ReportGeneratorState)
        
        # Add nodes - removing the reference to _load_patient_data
        self.state_graph.add_node("setup_customize_variable", self._setup_customize_variable)
        self.state_graph.add_node("formatting_patient_data", self._formatting_patient_data)
        self.state_graph.add_node("formatting_prescreening_test_data", self._formatting_prescreening_test_data)
        self.state_graph.add_node("formatting_physical_examination_data", self._formatting_physical_examination_data)
        self.state_graph.add_node("formatting_vital_signs_data", self._formatting_vital_signs_data)
        self.state_graph.add_node("formatting_conclusions_advice_data", self._formatting_conclusions_advice_data)
        self.state_graph.add_node("formatting_lab_section_data", self._formatting_lab_section_data)
        self.state_graph.add_node("formatting_electromedical_data", self._formatting_electromedical_data)
        self.state_graph.add_node("generate_report", self._generate_report)
        self.state_graph.add_node("uploadcleanup", self._upload_cleanup_files)
        
        # Define edges - starting directly from generate_report
        self.state_graph.add_edge(START, "setup_customize_variable")
        self.state_graph.add_edge("setup_customize_variable", "formatting_patient_data")
        self.state_graph.add_edge("formatting_patient_data", "formatting_prescreening_test_data")
        self.state_graph.add_edge("formatting_prescreening_test_data", "formatting_physical_examination_data")
        self.state_graph.add_edge("formatting_physical_examination_data", "formatting_vital_signs_data")
        self.state_graph.add_edge("formatting_vital_signs_data", "formatting_conclusions_advice_data")
        self.state_graph.add_edge("formatting_conclusions_advice_data", "formatting_lab_section_data")
        self.state_graph.add_edge("formatting_lab_section_data", "formatting_electromedical_data")
        self.state_graph.add_edge("formatting_electromedical_data", "generate_report")
        # self.state_graph.add_edge("generate_report", END)

        self.state_graph.add_edge("generate_report", "uploadcleanup")
        self.state_graph.add_edge("uploadcleanup", END)
                
        # Compile the graph
        self.chain = self.state_graph.compile()

    def run_with_data(self, patient_data: Dict) -> str:
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
                "file_path": None,
                "url_file_path": "",
                "files": None,
                "error": None,
                "customize_variable_report": customize_variable_report,
                "need_to_cleaned_file": []
            }
            
            # Run the graph
            final_state = self.chain.invoke(state)
            
            if final_state.get("error"):
                raise Exception(final_state["error"])
            
            execution_time = time.time() - start_time
            logger.info(f"Report generation completed in {execution_time:.2f} seconds")
            logger.info(f"URL file path: {final_state['url_file_path']}")
            
            return final_state["url_file_path"]
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

    def _setup_customize_variable(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Generating customize variable ".center(LOG_SIZE, "-"))
        logger.info(f"Setup customize variable for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Setup customize variable"""
        try:
            # Get customize variable report
            get_customize_variable_report_query = """
                SELECT bacv.key, bacv.value FROM b2b_bumame_appointment_customize_variable bacv
                LEFT JOIN b2b_bumame_appointment_patient bap ON bacv.appointment_id = bap.appointment_id
                WHERE bap.id = %s AND bap.is_deleted = 0 AND bacv.is_deleted = 0
            """
            try:
                customize_variable_report = db_postgres.fetch_query(get_customize_variable_report_query, (state["patient_data"]["patient_id"],))
                if customize_variable_report:
                    for row in customize_variable_report:
                        # Access tuple elements by index: row[0] = key, row[1] = value
                        state["customize_variable_report"][row[0]] = row[1]
                        logger.info(f"Customize variable report: {row[0]} = {row[1]}")
                
                current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                assets_dir = os.path.join(current_dir, "assets")

                if state["customize_variable_report"].get("header_image_url") is not None:
                    state["customize_variable_report"]["header_image_url"] = state["customize_variable_report"]["header_image_url"]
                else:
                    state["customize_variable_report"]["header_image_url"] = os.path.join(assets_dir, "top-bumame.png")

                logger.info(f"Header image URL: {state['customize_variable_report']['header_image_url']}")

                if state["customize_variable_report"].get("footer_image_url") is not None:
                    state["customize_variable_report"]["footer_image_url"] = state["customize_variable_report"]["footer_image_url"]
                else:
                    state["customize_variable_report"]["footer_image_url"] = os.path.join(assets_dir, "bottom-bumame.png")

                dokter_pemeriksa_data = {
                    "name": "dr. Muhammad Reza Kurniawan",
                    "title": "Dokter Pemeriksa",
                    "signature_url": os.path.join(assets_dir, "internal_reza_signature.png")
                }
                penanggung_jawab_lab_data = {
                    "name": "dr. Dwi Utomo Nusantara, Sp. PK",
                    "title": "Penanggung Jawab Laboratorium",
                    "signature_url": os.path.join(assets_dir, "penanggung_jawab_dwi_utomo_signature.jpg")
                }
                diperiksa_oleh_data = {
                    "name": "Yaufita Lokananta",
                    "title": "Diperiksa Oleh",
                    "signature_url": os.path.join(assets_dir, "pemeriksa_yaufita_signature.jpg")
                }

                if state["customize_variable_report"].get("dokter_internal_signature_url") is not None:
                    dokter_pemeriksa_data["signature_url"] = state["customize_variable_report"]["dokter_internal_signature_url"]
        
                if state["customize_variable_report"].get("dokter_internal") is not None:
                    dokter_pemeriksa_data["name"] = state["customize_variable_report"]["dokter_internal"]

                if state["customize_variable_report"].get("penanggung_jawab_hasil") is not None:
                    penanggung_jawab_lab_data["name"] = state["customize_variable_report"]["penanggung_jawab_hasil"]

                if state["customize_variable_report"].get("perujuk_lab") is not None:
                    diperiksa_oleh_data["name"] = state["customize_variable_report"]["perujuk_lab"]

                if state["customize_variable_report"].get("penanggung_jawab_hasil_signature_url") is not None:
                    penanggung_jawab_lab_data["signature_url"] = state["customize_variable_report"]["penanggung_jawab_hasil_signature_url"]

                if state["customize_variable_report"].get("perujuk_lab_signature_url") is not None:
                    diperiksa_oleh_data["signature_url"] = state["customize_variable_report"]["perujuk_lab_signature_url"]

                state["formatted_dokter_pemeriksa_data"] = dokter_pemeriksa_data
                state["formatted_penanggung_jawab_lab_data"] = penanggung_jawab_lab_data
                state["formatted_diperiksa_oleh_data"] = diperiksa_oleh_data
                state["header_image_url"] = state["customize_variable_report"].get("header_image_url")
                state["footer_image_url"] = state["customize_variable_report"].get("footer_image_url")


                logger.info(f"Get customize variable report for patient {state['patient_data']['appointment_id']}")
            except Exception as e:
                logger.error(f"Failed to get customize variable report: {str(e)}")
                state["error"] = f"Failed to get customize variable report: {str(e)}"
                raise
            
        except Exception as e:
            logger.error(f"Error setting up customize variable: {str(e)}")
            raise
        
        return state

    def _formatting_patient_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting patient data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting patient data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format patient data"""
        try:
            patient_data = {
                'nik': state["patient_data"]["nik"],
                'nama': state["patient_data"]["nama"],
                'tanggal_lahir': state["patient_data"]["tanggal_lahir"],
                'jenis_kelamin': state["patient_data"]["jenis_kelamin"],
                'kelompok': state["patient_data"]["kelompok"],
                'checkin_date': state["patient_data"]["checkin_date"],
                'company': state["patient_data"]["company"],
                'patient_photo_url': state["patient_data"]["patient_photo_url"]
            }
            state["formatted_patient_data"] = patient_data
        except Exception as e:
            logger.error(f"Error formatting patient data: {str(e)}")
            raise

        return state

    def _formatting_prescreening_test_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting prescreening test data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting prescreening test data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format prescreening test data"""
        try:
            prescreening_test = state["patient_data"]["keluhan_sekarang"]
            language = state["patient_data"]["language"]
            # Add each subsection
            sections = [
                (get_text("personal_medical_history", language), prescreening_test["riwayat_penyakit_sendiri"]),
                (get_text("family_medical_history", language), prescreening_test["riwayat_penyakit_keluarga"]),
                (get_text("habits", language), prescreening_test["kebiasaan"])
            ]

            # ini khusus untuk dynamic section
            for key, _ in prescreening_test.items():
                if key not in ["riwayat_penyakit_sendiri", "riwayat_penyakit_keluarga", "kebiasaan", "consent_form"]:
                    sections.append((key, prescreening_test[key]))
                        
            formatted_prescreening_test_data = []

            translate_service = TranslateService()
            for index, (title, items) in enumerate(sections):
                items_data = []
                items.sort(key=lambda x: x[0])  # Sort based on the first element of each subarray

                for i, (key, value) in enumerate(items):
                    display_value = value.strip() if value else ""
                    title_item = translate_service.prescreening_test_label(key, language)

                    if not display_value or display_value == "" or display_value.lower() in ["null", "none", "n/a", "-"]:
                        display_value = "-"
                    else:
                        display_value = translate_service.prescreening_test_answer(value, language)

                    key = re.sub(r'[a-zA-Z]\. ', '', key)

                    if f"{string.ascii_lowercase[i]}." not in title_item:
                        title_item = f"{string.ascii_lowercase[i]}. {title_item}"

                    items_data.append([title_item, display_value])

                formatted_prescreening_test_data.append({
                    "title": f"{ROMAN_NUMERALS[index + 1]}. {title}",
                    "data": items_data
                })

            state["formatted_prescreening_test_data"] = formatted_prescreening_test_data
        except Exception as e:
            logger.error(f"Error formatting prescreening test data: {str(e)}")
            raise

        return state

    def _formatting_physical_examination_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting physical examination data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting physical examination data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format physical examination data"""
        try:
            physical_examination = state["patient_data"]["pemeriksaan_fisik"]
            language = state["patient_data"]["language"]

            list_data_header = {
                "Kepala dan Sistem Endokrin":["Kepala & Leher", "Kelenjar Tiroid/Gondok", "Kelenjar Limfe"],
                "Pemeriksaan Umum": ["Kulit", "Status Mental", "Keadaan Umum"],
                "Mata dan Penglihatan": ["Mata", "Kelainan Mata", "Buta Warna"],
                "Telinga, Hidung, dan Tenggorokan": ["Telinga", "Tenggorokan", "Tonsil", "Hidung", "Sinus"],
                "Gigi": ["Gigi"],
                "Sistem Kardiopulmonal": ["Dada", "Paru", "Jantung"],
                "Sistem Pencernaan dan Urologi": ["Abdomen", "Hati", "Perabaan", "Ginjal"],
                "Muskuloskeletal dan Neurologis": ["Tulang Belakang", "Neurologis", "Extrimitas", "Musculoskeletal"],
                "Carpal Tunnel Syndrome":["Tinel", "Phalen"],
                "Low Back Pain":["Kernig", "Lasegue", "Patrick-Kontrapatrick", "Bragard"],
                "Romberg":["Terbuka", "Tertutup"],
                "Smell Test":["Smell"],
                "Lainnya":[]
            }

            # would be like this : {"Kepala dan Sistem Endokrin": [["Kepala & Leher", "Normal"]]}
            list_data_new = {}
            for header_key, header_value in list_data_header.items():
                list_data_new[header_key] = []

            translate_service = TranslateService()
            for i, (key, value) in enumerate(physical_examination):
                is_skipped = False
                for header_key, header_value in list_data_header.items():
                    for header_value_item in header_value:
                        lower_header_value_item = header_value_item.lower()
                        lower_key = key.lower()
                        if lower_header_value_item in lower_key:
                            formatted_label_key = translate_service.pemeriksaan_fisik_label(key, language)
                            new_value = translate_service.pemeriksaan_fisik_answer(value, language)
                            if header_key == "Carpal Tunnel Syndrome":
                                formatted_label_key = formatted_label_key.replace("CARPAL TUNNEL SYNDROME - ", "")
                            
                            if header_key == "Low Back Pain":
                                formatted_label_key = formatted_label_key.replace("LOW BACK PAIN - ", "")

                            if header_key == "Romberg":
                                formatted_label_key = formatted_label_key.replace("ROMBERG TEST - ", "")

                            if header_key == "Smell Test":
                                formatted_label_key = formatted_label_key.replace("SMELL TEST - ", "")

                            if new_value == "":
                                new_value = "-"

                            formatted_label_key = string.capwords(formatted_label_key)
                            list_data_new[header_key].append([formatted_label_key, new_value])
                            is_skipped = True
                            break

                if not is_skipped:
                    list_data_new["Lainnya"].append([key, value])

            formatted_physical_examination_data = []
            for header_key, header_value in list_data_new.items():
                if len(header_value) > 0:
                    formatted_physical_examination_data.append({
                        "title": header_key,
                        "data": header_value
                    })

            state["formatted_physical_examination_data"] = formatted_physical_examination_data
        except Exception as e:
            logger.error(f"Error formatting physical examination data: {str(e)}")
            raise
        
        return state

    def _formatting_vital_signs_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting vital signs data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting vital signs data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format vital signs data"""
        try:
            vital_signs_data = state["patient_data"]["vital_signs"]
            language = state["patient_data"]["language"]
            weight_str = ""
            height_str = ""

            list_data_header = {
                "Tanda-tanda Vital":["Tensi", "Nadi", "Suhu", "SpO2", "Berat Badan", "Tinggi Badan", "Lingkar Perut", "BMI", "Vital Sign", "Respiratory"],
                "Visus": ["Glasses", "Visus", "Spheris", "Cylinder", "Axis"],
                "Lainnya":[]
            }

            list_data_new = {}
            for header_key, header_value in list_data_header.items():
                list_data_new[header_key] = []

            translate_service = TranslateService()
            for (key, value) in vital_signs_data:
                is_skipped = False
                for header_key, header_value in list_data_header.items():
                    for header_value_item in header_value:
                        lower_header_value_item = header_value_item.lower()
                        lower_key = key.lower()
                        if lower_header_value_item in lower_key:
                            formatted_label_key = translate_service.vital_signs_label(key, language)
                            formatted_value = translate_service.vital_signs_answer(value, language)

                            if lower_header_value_item == "berat badan":
                                weight_str = formatted_value

                            if lower_header_value_item == "tinggi badan":
                                height_str = formatted_value
                            
                            list_data_new[header_key].append([formatted_label_key, formatted_value])
                            is_skipped = True
                            break

                if not is_skipped:
                    list_data_new["Lainnya"].append([key, value])

            formatted_vital_signs_data = []
            for header_key, header_value in list_data_new.items():
                items_data = []
                for i, (key, value) in enumerate(header_value):
                    display_value = value.strip() if value else ""
                    if not display_value or display_value == "" or display_value.lower() in ["null", "none", "n/a", "-"]:
                        display_value = "-"
                
                        if "bmi" in key.lower():    
                            bmi_service = MiscService()
                            bmi_result = bmi_service.calculate_bmi(weight_str, height_str)
                            if bmi_result['bmi'] is None:
                                display_value = "-"
                            else:
                                display_value = f"{bmi_result['bmi']}, {bmi_result['category']}"
                                display_value = translate_service.vital_signs_answer(display_value, language)

                        # Add degree symbol for temperature values
                        if "suhu" in key.lower() or "temperature" in key.lower():
                            # Check if the value contains temperature indicators and doesn't already have degree symbol
                            if any(temp_indicator in display_value.lower() for temp_indicator in ['c', 'celsius', 'f', 'fahrenheit']):
                                # Replace standalone 'c' at the end with '°C'
                                display_value = re.sub(r'\b(\d+(?:\.\d+)?)\s*c\b', r'\1°C', display_value, flags=re.IGNORECASE)
                                # Replace standalone 'f' at the end with '°F'
                                display_value = re.sub(r'\b(\d+(?:\.\d+)?)\s*f\b', r'\1°F', display_value, flags=re.IGNORECASE)
                                # Replace 'celsius' with '°C'
                                display_value = re.sub(r'\bcelsius\b', '°C', display_value, flags=re.IGNORECASE)
                                # Replace 'fahrenheit' with '°F'
                                display_value = re.sub(r'\bfahrenheit\b', '°F', display_value, flags=re.IGNORECASE)
                        
                    items_data.append([key, display_value])

                if len(items_data) > 0:
                    formatted_vital_signs_data.append({
                        "title": header_key,
                        "data": items_data
                    })

            state["formatted_vital_signs_data"] = formatted_vital_signs_data
        except Exception as e:
            logger.error(f"Error formatting vital signs data: {str(e)}")
            raise
        
        return state

    def _formatting_conclusions_advice_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting conclusions and advice data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting conclusions and advice data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format conclusions and advice data"""
        try:
            translate_service = TranslateService()
            language = state["patient_data"]["language"]

            conclusions_data = state["patient_data"]["conclusions"]
            advice_data = str.replace(state["patient_data"]["advice"], "\n", "<br>")
            analysis_data = str.replace(state["patient_data"]["analysis"], "\n", "<br>")

            formatted_conclusions_data = []
            for i, (key, value) in enumerate(conclusions_data):
                display_value = value.strip() if value else ""
                if not display_value or display_value == "" or str(display_value).lower() in ["null", "none", "n/a", "-"]:
                    display_value = "-"

                display_value = str.replace(display_value, "\n", "<br>")

                formatted_conclusions_data.append([translate_service.other_label(key, language), display_value])

            advice_display = advice_data.strip() if advice_data else ""
            if not advice_display or advice_display == "" or str(advice_display).lower() in ["null", "none", "n/a", "-"]:
                advice_display = "-"

            if "Fit" in analysis_data:
                if state["customize_variable_report"].get("terms_analisis_fit"):
                    analysis_data = state["customize_variable_report"]["terms_analisis_fit"]
            elif "Fit to work" in analysis_data:
                if state["customize_variable_report"].get("terms_analisis_fit"):
                    analysis_data = state["customize_variable_report"]["terms_analisis_fit"]
            elif "Fit with note" in analysis_data:
                if state["customize_variable_report"].get("terms_analisis_fit_with_note"):
                    analysis_data = state["customize_variable_report"]["terms_analisis_fit_with_note"]
            elif "Unfit temporary" in analysis_data:
                if state["customize_variable_report"].get("terms_analisis_unfit_temporary"):
                    analysis_data = state["customize_variable_report"]["terms_analisis_unfit_temporary"]
        
            # Add analysis text
            analysis_display = analysis_data.strip() if analysis_data else ""
            if not analysis_display or analysis_display == "" or str(analysis_display).lower() in ["null", "none", "n/a", "-"]:
                analysis_display = "-"

            state["formatted_conclusions_data"] = formatted_conclusions_data
            state["formatted_advice_data"] = advice_display
            state["formatted_analysis_data"] = analysis_display
        except Exception as e:
            logger.error(f"Error formatting conclusions and advice data: {str(e)}")
            raise
        
        return state

    def _formatting_lab_section_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting lab section data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting lab section data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format lab section data"""
        try:
            translate_service = TranslateService()
            language = state["patient_data"]["language"]

            lab_header_data = {}
            lab_section_data = {}

            if state["patient_data"]["laboratory_results"] and state["patient_data"]["laboratory_results"].get("header"):
                lab_header_data = state["patient_data"]["laboratory_results"]["header"]

            if state["patient_data"]["laboratory_results"] and state["patient_data"]["laboratory_results"].get("sections"):
                lab_section_data = state["patient_data"]["laboratory_results"]["sections"]

            formatted_lab_header_data = lab_header_data
            formatted_lab_section_data = []

            for lab_header_data_key, lab_header_data_value in formatted_lab_header_data.items():
                if lab_header_data_key == "tanggal_periksa" or lab_header_data_key == "tgl_lahir":
                    if lab_header_data_value:
                        try:
                            date_obj = datetime.strptime(lab_header_data_value, "%Y-%m-%d %H:%M:%S")
                            formatted_lab_header_data[lab_header_data_key] = date_obj.strftime("%d-%m-%Y")
                        except ValueError:
                            formatted_lab_header_data[lab_header_data_key] = lab_header_data_value
                else:
                    formatted_lab_header_data[lab_header_data_key] = lab_header_data_value

            for section_data in lab_section_data:
                # check subsection to see if it need to show in the report if has value in test
                is_show_section = False
                sections_name = translate_service.lab_label(section_data["name"], language)
                subsections_data = section_data["subsections"]

                item_tests = []

                for item_subsections_data in subsections_data:
                    for item_subsection_tests_data in item_subsections_data["tests"]:
                        subsection_hasil = item_subsection_tests_data["hasil"]

                        if subsection_hasil and subsection_hasil.strip() != "":
                            is_show_section = True
                            break

                    if not is_show_section:
                        continue

                    for item_subsection_tests_data in item_subsections_data["tests"]:
                        item_subsection_hasil = item_subsection_tests_data["hasil"]
                        item_subsection_name = item_subsection_tests_data["name"]
                        item_subsection_nilai_rujukan = item_subsection_tests_data["nilai_rujukan"]
                        item_subsection_satuan = item_subsection_tests_data["satuan"] if item_subsection_tests_data.get("satuan") else "-"
                        item_subsection_keterangan = item_subsection_tests_data["keterangan"] if item_subsection_tests_data.get("keterangan") else "-"

                        if item_subsection_hasil.strip() == "" or item_subsection_hasil.strip() == "-":
                            continue

                        item_tests.append({
                            "name": item_subsection_name,
                            "hasil": item_subsection_hasil,
                            "satuan": item_subsection_satuan,
                            "nilai_rujukan": item_subsection_nilai_rujukan,
                            "keterangan": item_subsection_keterangan,
                            "is_contain_asterisk": "*" in item_subsection_hasil.strip().lower()
                        })

                if len(item_tests) > 0:
                    formatted_lab_section_data.append({
                        "title": sections_name,
                        "tests": item_tests
                    })

            state["formatted_lab_header_data"] = formatted_lab_header_data
            state["formatted_lab_section_data"] = formatted_lab_section_data
        except Exception as e:
            logger.error(f"Error formatting lab section data: {str(e)}")
            raise
        
        return state

    def _formatting_electromedical_data(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Formatting electromedical data ".center(LOG_SIZE, "-"))
        logger.info(f"Formatting electromedical data for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Format electromedical data"""
        try:
            electromedical_data = state["patient_data"]["electromedical_examination"]
            translate_service = TranslateService()
            language = state["patient_data"]["language"]

            formatted_electromedical_data = []

            for key_electromedical_data in electromedical_data:
                items_data = []
                url_image = ""
                kesimpulan = ""
                saran = ""
                dokter = ""
                diagnosa_audiometri = []
                
                for item_data_key, item_data_value in electromedical_data[key_electromedical_data].items():
                    item_data_title = str.replace(item_data_key, "_", " ").title()

                    if "url" in item_data_key:
                        url_image = item_data_value
                        continue

                    if "title" in item_data_key or "subtitle" in item_data_key:
                        continue

                    if "kesimpulan" in item_data_title.lower():
                        kesimpulan = item_data_value
                        continue
                    
                    if "saran" in item_data_title.lower():
                        saran = item_data_value
                        continue

                    if "dokter" in item_data_title.lower():
                        dokter = item_data_value["name"]
                        continue

                    if "audiometri" not in key_electromedical_data:
                        items_data.append([item_data_title, str.replace(item_data_value, "\n", "<br>")])
                    else:
                        if "diagnosis" in item_data_key:
                            diagnosa_audiometri = []
                            if "telinga_kanan" in item_data_value:
                                kanan_ac = item_data_value["telinga_kanan"]["ac"]
                                if kanan_ac:
                                    diagnosa_audiometri.append({
                                        "label": get_text("right_ear_ac", language),
                                        "data": kanan_ac
                                    })
                                kanan_bc = item_data_value["telinga_kanan"]["bc"]
                                if kanan_bc:
                                    diagnosa_audiometri.append({
                                        "label": get_text("right_ear_bc", language),
                                        "data": kanan_bc
                                    })
                            
                            if "telinga_kiri" in item_data_value:
                                kiri_ac = item_data_value["telinga_kiri"]["ac"]
                                if kiri_ac:
                                    diagnosa_audiometri.append({
                                        "label": get_text("left_ear_ac", language),
                                        "data": kiri_ac
                                    })
                                kiri_bc = item_data_value["telinga_kiri"]["bc"]
                                if kiri_bc:
                                    diagnosa_audiometri.append({
                                        "label": get_text("left_ear_bc", language),
                                        "data": kiri_bc
                                    })
                

                # add kesimpulan, saran, dokter
                items_data.append([get_text("conclusion_lower", language), str.replace(kesimpulan, "\n", "<br>")])
                items_data.append([get_text("advice_lower", language), str.replace(saran, "\n", "<br>")])
                items_data.append([get_text("examining_doctor", language) + "*", dokter])

                downloaded_url_image = url_image
                new_width = 0
                max_height = 0
                if url_image != "":
                    if key_electromedical_data == "audiometri":
                        downloaded_url_image = url_image
                    else:
                        logger.info(f"Downloading and converting PDF to image: {key_electromedical_data}")
                        
                        if "drive.google.com" in url_image:
                            downloaded_url_image, new_width, max_height = self.download_and_convert_pdf_to_image(url_image)
                        else:
                            bucket_name = url_image.split("/")[3]
                            source_blob_name = "/".join(url_image.split("/")[4:])
                            logger.info(f"Downloading from GCS: {bucket_name}, {source_blob_name}")
                            downloaded_url_image = download_from_gcs(bucket_name, source_blob_name)

                        state["need_to_cleaned_file"].append(downloaded_url_image)
                        # get root folder
                        root_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        downloaded_url_image = os.path.join(root_folder, downloaded_url_image)
                        logger.info(f"Success download and convert PDF to image: {key_electromedical_data}")


                formatted_electromedical_data.append({
                    "key": key_electromedical_data,
                    "title": get_text(f"electromedical_label_{key_electromedical_data}", language),
                    "data": items_data,
                    "url": downloaded_url_image,
                    "diagnosis": diagnosa_audiometri,
                    "is_landscape": new_width > max_height,
                })
            
            logger.info(f"Formatted electromedical data: {formatted_electromedical_data}")

            state["formatted_electromedical_data"] = formatted_electromedical_data
        except Exception as e:
            logger.error(f"Error formatting electromedical data: {str(e)}")
            raise
        
        return state


    def _generate_report(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Generating report ".center(LOG_SIZE, "-"))
        logger.info(f"Generating report for patient {state['patient_data']['appointment_id']}/{state['patient_data']['patient_id']}")
        """Generate PDF report and upload directly to GCS"""
        try:            
            # Set up Jinja2 environment
            template_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
            env = Environment(loader=FileSystemLoader(template_dir))
            
            # Load and render the main template
            template = env.get_template('reports.html')
            html_content = template.render(patient_data=state["formatted_patient_data"], prescreening_test_data=state["formatted_prescreening_test_data"], physical_examination_data=state["formatted_physical_examination_data"], vital_signs_data=state["formatted_vital_signs_data"], conclusions_data=state["formatted_conclusions_data"], advice_data=state["formatted_advice_data"], analysis_data=state["formatted_analysis_data"], lab_header_data=state["formatted_lab_header_data"], lab_section_data=state["formatted_lab_section_data"], electromedical_data=state["formatted_electromedical_data"], dokter_pemeriksa_data=state["formatted_dokter_pemeriksa_data"], penanggung_jawab_lab_data=state["formatted_penanggung_jawab_lab_data"], diperiksa_oleh_data=state["formatted_diperiksa_oleh_data"], header_image_url=state["header_image_url"], footer_image_url=state["footer_image_url"])

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
                f"tmp/{filename}.pdf",
                stylesheets=[CSS("templates/print.css")]
            )
            
            state["need_to_cleaned_file"].append(f"tmp/{filename}.pdf")
            state["file_path"] = f"tmp/{filename}.pdf"

            return state
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

    def _upload_cleanup_files(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        logger.info(" Upload and cleanup files ".center(LOG_SIZE, "-"))

        if not os.path.exists(state["file_path"]):
            raise Exception("PDF file was not created")

        # Upload to GCS immediately
        storage_client = storage.Client()
        bucket_name = 'bumame-private-document'
        bucket = storage_client.bucket(bucket_name)
        
        filename = state["patient_data"].get('filename', 'report') + ".pdf"
        blob_name = f"b2b-medical-report/{filename}"
        blob = bucket.blob(blob_name)
        state["url_file_path"] = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
        
        # Upload file and make it public
        blob.upload_from_filename(state["file_path"])
        
        # Get the public URL
        # url = blob.generate_signed_url(expiration=timedelta(hours=1))
        # logger.info(f"URL report: {url}")
        update_status_query = """
        UPDATE b2b_bumame_appointment_patient_analysis
        SET examination_status = 'generated',
            medical_report_url_v2 = %s,
            result_issued_at = NOW()
        WHERE appointment_patient_id = %s AND is_deleted = 0
        """
        db_postgres.execute_query(update_status_query, (state["url_file_path"], state["patient_data"]["patient_id"]))
        logger.info(f"Updated examination_status to 'generated' and saved URL for patient {state['patient_data']['patient_id']}")

        logger.info(f"Cleanup files for patient {state['patient_data']['patient_id']}")
        """Cleanup files"""
        try:
            for file in state["need_to_cleaned_file"]:
                root_folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                file_path = os.path.join(root_folder, file)
                if os.path.exists(file_path):
                    os.remove(file_path)
                else:
                    logger.warning(f"File not found: {file}")
            state["need_to_cleaned_file"] = []
        except Exception as e:
            logger.error(f"Error cleaning up files: {str(e)}")
            raise
        return state
    
    def download_and_convert_pdf_to_image(self, url) -> Tuple[str, int, int]:
        """Download PDF from Google Drive and convert to image"""
        try:
            # Extract file ID from Google Drive URL
            file_id = self.get_google_drive_file_id(url)
            if not file_id:
                raise ValueError(f"Invalid Google Drive URL: {url}")
            
            # Create direct download link
            download_url = f"https://drive.google.com/uc?id={file_id}&export=download"
            
            # Download PDF with proper headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(download_url, headers=headers, allow_redirects=True)
            
            if response.status_code != 200:
                raise Exception(f"Failed to download PDF. Status code: {response.status_code}")
            
            # Convert PDF to image
            pdf_content = io.BytesIO(response.content)
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            
            if pdf_document.page_count == 0:
                raise Exception("PDF document is empty")
            
            # Get first page and convert to high-resolution image
            first_page = pdf_document[0]
            zoom = 2  # Increase zoom for better quality
            mat = fitz.Matrix(zoom, zoom)
            pix = first_page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            image = Image.open(io.BytesIO(img_data))
            
            # Auto-crop to remove white borders
            bg = Image.new(image.mode, image.size, 'white')
            diff = ImageChops.difference(image, bg)
            bbox = diff.getbbox()
            if bbox:
                image = image.crop(bbox)
            
            # Enhance image quality and compress
            image = image.convert('RGB')
            
            # Calculate new dimensions with max height 720px while maintaining aspect ratio
            max_height = 1080
            ratio = max_height / float(image.size[1])  # Calculate ratio based on height only
            new_width = int(image.size[0] * ratio)
            new_size = (new_width, max_height)
            
            # Resize image
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Create bytes buffer with compression
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='PNG', optimize=True, quality=85)
            img_buffer.seek(0)

            # save image to temp file
            filename = f"tmp/temp_image_{uuid.uuid4()}.png"
            image.save(filename, optimize=True, quality=85)
            
            pdf_document.close()
            return filename, new_width, max_height
            
        except Exception as e:
            logger.error(f"Error converting PDF to image: {str(e)}")
            raise

    def get_google_drive_file_id(self, url):
        """Extract file ID from Google Drive URL"""
        patterns = [
            r'https://drive\.google\.com/open\?id=([a-zA-Z0-9_-]+)',
            r'https://drive\.google\.com/file/d/([a-zA-Z0-9_-]+)',
            r'https://drive\.google\.com/uc\?id=([a-zA-Z0-9_-]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
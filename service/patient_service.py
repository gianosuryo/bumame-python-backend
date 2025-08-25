from helper.database import db_postgres
from config.logging import logger
from typing import Dict, Any
from helper.language_mapping_medical_report import get_text
import json
from datetime import datetime, timedelta

class PatientService:
    def get_patient_data(appointment_patient_id: str, appointment_id: str, language: str = "id") -> Dict[str, Any]:
        """
        Get patient data from database for report generation
        """
        try:
            # Get company name from company_client table through appointment
            company_query = """
            SELECT cc.name as company_name 
            FROM b2b_bumame_appointment a
            JOIN b2b_bumame_company_client cc ON a.company_client_id = cc.id
            WHERE a.id = %s AND a.is_deleted = 0 AND cc.is_deleted = 0
            """
            company_data = db_postgres.fetch_query(company_query, (appointment_id,))
            
            if not company_data:
                raise ValueError(f"Company data not found for appointment_id: {appointment_id}")
            
            company_name = company_data[0][0]
            print(f"Company name retrieved: {company_name}")

            # Get patient analysis record
            analysis_query = """
            SELECT 
                id, appointment_id, appointment_patient_id, examination_status, 
                doctor_examiner_name, prescreening_test_json, physical_examination_json, 
                vital_sign_examination_json, lab_examination_json, electromedical_examination_json, 
                examination_conclusion_json, examination_advice, examination_analysis,
                is_deleted, specimen_taken_at, result_issued_at, created_at, updated_at
            FROM b2b_bumame_appointment_patient_analysis 
            WHERE appointment_patient_id = %s AND is_deleted = 0
            """
            analysis_data = db_postgres.fetch_query(analysis_query, (appointment_patient_id,))
            
            if not analysis_data:
                raise ValueError(f"Patient analysis data not found for appointment_patient_id: {appointment_patient_id}")
            
            # print(f"Analysis data retrieved: {analysis_data}")
            analysis_record = analysis_data[0]
            
            # Get patient details including photo URL
            patient_query = """
            SELECT 
                id, appointment_id, name, nik, birth_date, gender, 
                "group", is_deleted, created_at, updated_at, d_day_photo_proof_url, check_in_at
            FROM b2b_bumame_appointment_patient
            WHERE id = %s AND is_deleted = 0
            """
            patient_data = db_postgres.fetch_query(patient_query, (appointment_patient_id,))
            
            if not patient_data:
                raise ValueError(f"Patient data not found for id: {appointment_patient_id}")
            
            # print(f"Patient data retrieved: {patient_data}")
            patient_record = patient_data[0]
            
            # Get appointment details
            appointment_id = patient_record[1]  # appointment_id from patient record
            appointment_query = """
            SELECT id, institution_name, is_deleted, created_at, updated_at
            FROM b2b_bumame_appointment
            WHERE id = %s AND is_deleted = 0
            """
            appointment_data = db_postgres.fetch_query(appointment_query, (appointment_id,))
            
            if not appointment_data:
                raise ValueError(f"Appointment data not found for id: {appointment_id}")
            
            
            # Initialize with default sample structures (based on JSON examples)
            # These are fallbacks that match the expected structure for each section
            prescreening_test = {
                "riwayat_penyakit_sendiri": [
                    ["a. Riwayat Penyakit", "Tidak Ada"]
                ],
                "riwayat_penyakit_keluarga": [
                    ["a. Riwayat Penyakit", "Tidak Ada"]
                ],
                "kebiasaan": [
                    ["a. Kebiasaan", "Tidak Ada"]
                ]
            }
            
            # physical_examination = [
            #     ["Kulit", "Normal"],
            #     ["Kesadaran Umum", "Normal"]
            # ]

            physical_examination = []
            vital_sign = []
            # vital_sign = [
            #     ["Tensi (mmHg)", "-"],
            #     ["Nadi (X/menit)", "-"],
            #     ["Berat Badan (kg)", "-"],
            #     ["Tinggi Badan (cm)", "-"],
            #     ["BMI", "-"]
            # ]
            
            lab_examination = {
                "header": {
                    "nama": "-",
                    "no_rm": "-"
                },
                "sections": []
            }
            
            # Define default structure for each examination type
            default_exam_structures = {
                "rontgen": {
                    "title": "HASIL PEMERIKSAAN RADIOLOGI",
                    "subtitle": "THORAX FOTO",
                    "hasil": "Tidak ada data",
                    "kesimpulan": "Tidak ada data",
                    "dokter": {
                        "name": "-",
                        "title": "Dokter Pemeriksa"
                    },
                    "url": "-"
                },
                "audiometri": {
                    "diagnosis": [["Tidak ada data", "Tidak ada data"]]
                },
                "ekg": {
                    "title": "Pemeriksaan Elektrokardiografi (EKG)",
                    "subtitle": "Hasil Perekaman Aktivitas Listrik Jantung",
                    "hasil": "Tidak ada data",
                    "kesimpulan": "Tidak ada data",
                    "dokter": {
                        "name": "-",
                        "title": "Dokter Pemeriksa"
                    },
                    "url": "-"
                },
                "spirometri": {
                    "title": "Pemeriksaan Fungsi Paru - Spirometri",
                    "subtitle": "Hasil Pengukuran Kapasitas dan Aliran Udara Paru",
                    "hasil": "Tidak ada data",
                    "kesimpulan": "Tidak ada data",
                    "dokter": {"name": "-", "title": "Dokter Pemeriksa"},
                    "url": "-"
                },
                "treadmill": {
                    "title": "Pemeriksaan Treadmill Test",
                    "subtitle": "Hasil Uji Toleransi Jantung terhadap Stres",
                    "hasil": "Tidak ada data",
                    "kesimpulan": "Tidak ada data",
                    "dokter": {"name": "-", "title": "Dokter Pemeriksa"},
                    "url": "-"
                },
                "usg_abdomen": {
                    "title": "Pemeriksaan Ultrasonografi - Abdomen",
                    "subtitle": "Hasil Pemindaian USG pada Organ Abdomen",
                    "hasil": "Tidak ada data",
                    "kesimpulan": "Tidak ada data",
                    "dokter": {"name": "-", "title": "Dokter Pemeriksa"},
                    "url": "-"
                },
                "usg_mammae": {
                    "title": "Pemeriksaan Ultrasonografi - Mammae",
                    "subtitle": "Hasil Pemindaian USG pada Jaringan Payudara",
                    "hasil": "Tidak ada data",
                    "kesimpulan": "Tidak ada data",
                    "dokter": {"name": "-", "title": "Dokter Pemeriksa"},
                    "url": "-"
                }
            }
            
            examination_conclusion = [
                ["Tanda Vital", "-"],
                ["Pemeriksaan Fisik", "-"]
            ]
            
            # Map column indexes to clear field names for debugging
            fields_map = {
                5: "prescreening_test_json",
                6: "physical_examination_json",
                7: "vital_sign_examination_json",
                8: "lab_examination_json",
                9: "electromedical_examination_json",
                10: "examination_conclusion_json"
            }
            
            electromedical_examination = {}

            for idx, field_name in fields_map.items():
                try:
                    json_str = analysis_record[idx]
                    if json_str and json_str.strip():
                        # print(f"Raw {field_name} data: {json_str[:200]}...")  # Print first 200 chars
                        
                        parsed_data = json.loads(json_str)
                        # print(f"Successfully parsed {field_name}: {type(parsed_data)}")
                        # print(f"Sample content of {field_name}: {str(parsed_data)[:200]}...")
                        
                        # Assign the parsed data to the correct variable
                        if idx == 5:
                            if isinstance(parsed_data, dict):
                                prescreening_test = parsed_data
                            else:
                                print(f"WARNING: prescreening_test_json is not a dict, using default")
                        elif idx == 6:
                            if isinstance(parsed_data, list):
                                physical_examination = parsed_data
                            else:
                                print(f"WARNING: physical_examination_json is not a list, using default")
                        elif idx == 7:
                            if isinstance(parsed_data, list):
                                vital_sign = parsed_data
                            else:
                                print(f"WARNING: vital_sign_examination_json is not a list, using default")
                        elif idx == 8:
                            if isinstance(parsed_data, dict):
                                lab_examination = parsed_data
                            else:
                                print(f"WARNING: lab_examination_json is not a dict, using default")
                        elif idx == 9:
                            if isinstance(parsed_data, dict):
                                electromedical_examination = parsed_data
                                print(f"Loaded electromedical examination data: {list(electromedical_examination.keys())}")
                            else:
                                print(f"WARNING: electromedical_examination_json is not a dict, using empty dict")
                                electromedical_examination = {}
                        elif idx == 10:
                            if isinstance(parsed_data, list):
                                examination_conclusion = parsed_data
                            else:
                                print(f"WARNING: examination_conclusion_json is not a list, using default")
                    else:
                        print(f"Empty or whitespace {field_name}, using default")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON parse error in {field_name}: {e}")
                    print(f"JSON parse error in {field_name}: {e}")
                    # print(f"Raw JSON data: {analysis_record[idx][:200]}...")  # Print first 200 chars
                    print(f"Using default structure for {field_name}")
            
            # Format birth date safely
            birth_date = patient_record[4]
            checkin_date = patient_record[11]
            formatted_birth_date = "-"
            formatted_checkin_date = "-"
            
            if birth_date:
                # Add one day to the birth date
                if hasattr(birth_date, 'strftime'):
                    # If it's a datetime object, add one day
                    birth_date_plus_one = birth_date + timedelta(days=1)
                    formatted_birth_date = birth_date_plus_one.strftime("%d-%m-%Y")
                else:
                    # If it's a string or other format, try to convert and add one day
                    try:
                        if isinstance(birth_date, str):
                            # Try to parse the string as a date
                            parsed_date = datetime.strptime(birth_date, "%Y-%m-%d")
                            birth_date_plus_one = parsed_date + timedelta(days=1)
                            formatted_birth_date = birth_date_plus_one.strftime("%d-%m-%Y")
                        else:
                            # For other types, just convert to string
                            formatted_birth_date = str(birth_date)
                    except (ValueError, TypeError):
                        # If parsing fails, just use the original value
                        formatted_birth_date = str(birth_date)

            if checkin_date:
                # Add one day to the checkout date
                if hasattr(checkin_date, 'strftime'):
                    # If it's a datetime object, add one day
                    checkin_date_plus_one = checkin_date + timedelta(hours=7)
                    formatted_checkin_date = checkin_date_plus_one.strftime("%d-%m-%Y")
                else:
                    # If it's a string or other format, try to convert and add one day
                    try:
                        if isinstance(checkin_date, str):
                            # Try to parse the string as a date
                            parsed_date = datetime.strptime(checkin_date, "%Y-%m-%d")
                            checkin_date_plus_one = parsed_date + timedelta(hours=7)
                            formatted_checkin_date = checkin_date_plus_one.strftime("%d-%m-%Y")
                        else:
                            # For other types, just convert to string
                            formatted_checkin_date = str(checkin_date)
                    except (ValueError, TypeError):
                        # If parsing fails, just use the original value
                        formatted_checkin_date = str(checkin_date)
            
            # Get patient photo URL and normalize it
            patient_photo_url = patient_record[10] if len(patient_record) > 10 else None  # d_day_photo_proof_url
            
            # Normalize photo URL format
            if patient_photo_url:
                if patient_photo_url.startswith("gs://"):
                    # Convert gs:// format to https:// format
                    patient_photo_url = patient_photo_url.replace("gs://", "https://storage.googleapis.com/")
                print(f"Patient photo URL: {patient_photo_url}")
            else:
                print("No patient photo URL found")

            # Build patient data structure
            patient_data_dict = {
                "patient_id": appointment_patient_id,
                "appointment_id": appointment_id,
                "company": company_name,  # Use company name from company_client table
                "patient_photo_url": patient_photo_url,  # Add patient photo URL
                "nik": patient_record[3] or "-",
                "nama": patient_record[2] or "-",
                "tanggal_lahir": formatted_birth_date,
                "jenis_kelamin": patient_record[5] or "-",
                "kelompok": patient_record[6] or "-",
                "checkin_date": formatted_checkin_date,
                "identity": {
                    "basic_info": [
                        [get_text("nik", language), patient_record[3] or "-"],  # nik
                        [get_text("name", language), patient_record[2] or "-"],  # name
                        [get_text("birth_date", language), formatted_birth_date],  # birth_date properly formatted
                        [get_text("checkout_examination_date", language), formatted_checkin_date],  # checkout_examination_date
                    ],
                    "extended_info": [
                        [get_text("gender", language), patient_record[5] or "-"],  # gender
                        [get_text("group", language), patient_record[6] or "-"]  # group
                    ]
                },
                "keluhan_sekarang": prescreening_test,
                "pemeriksaan_fisik": physical_examination,
                "vital_signs": vital_sign,
                "laboratory_results": lab_examination,
                "radiologi": electromedical_examination.get("rontgen", default_exam_structures["rontgen"]),
                "rontgen": electromedical_examination.get("rontgen", default_exam_structures["rontgen"]),
                "audiometri": electromedical_examination.get("audiometri", default_exam_structures["audiometri"]),
                "ekg": electromedical_examination.get("ekg", default_exam_structures["ekg"]),
                "spirometri": electromedical_examination.get("spirometri", default_exam_structures["spirometri"]),
                "treadmill": electromedical_examination.get("treadmill", default_exam_structures["treadmill"]),
                "usg_abdomen": electromedical_examination.get("usg_abdomen", default_exam_structures["usg_abdomen"]),
                "usg_mammae": electromedical_examination.get("usg_mammae", default_exam_structures["usg_mammae"]),
                "conclusions": examination_conclusion,
                "advice": analysis_record[11] or "-",  # examination_advice
                "analysis": analysis_record[12] or "-",  # examination_analysis
                "doctor": {
                    "name": analysis_record[4] or "dr. Specialist",  # doctor_examiner_name
                    "title": "Dokter Pemeriksa"
                },
                "status": analysis_record[3] or "Completed",  # examination_status
                "electromedical_examination": electromedical_examination,  # Add complete electromedical data
            }
            
            # Only add examination types that exist in the data
            exam_types = ["audiometri", "ekg", "spirometri", "treadmill", "usg_abdomen", "usg_mammae"]
            for exam_type in exam_types:
                if exam_type in electromedical_examination:
                    patient_data_dict[exam_type] = electromedical_examination[exam_type]
            
            print("Final patient data structure:")
            for key, value in patient_data_dict.items():
                if key in ["identity", "keluhan_sekarang", "pemeriksaan_fisik", "vital_signs", 
                        "conclusions", "laboratory_results", "radiologi", "rontgen", "audiometri", "ekg", "spirometri", "treadmill", "usg_abdomen", "usg_mammae"]:
                    print(f"{key}: {type(value)}")
                    if isinstance(value, dict):
                        print(f"  Keys: {list(value.keys())}")
                    elif isinstance(value, list):
                        if value and len(value) > 0:
                            print(f"  First item: {value[0]}")
                            if isinstance(value[0], list) and len(value[0]) > 0:
                                print(f"    Item structure: {[type(x) for x in value[0]]}")
                        else:
                            print("  Empty list")
                else:
                    print(f"{key}: {value}")
            
            return patient_data_dict
        except Exception as e:
            logger.error(f"Error in get_patient_data: {str(e)}")
            print(f"Error in get_patient_data: {str(e)}")
            raise
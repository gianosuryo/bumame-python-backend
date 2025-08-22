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
    files: Optional[Dict[str, str]]
    error: Optional[str]
    customize_variable_report: Optional[CustomizeVariableReport]

@singleton
class AgentReportGenerator:
    def __init__(self):
        # Define state schema
        self.state_graph = StateGraph(_ReportGeneratorState)
        
        # Add nodes - removing the reference to _load_patient_data
        self.state_graph.add_node("generate_report", self._generate_report)
        self.state_graph.add_node("cleanup", self._cleanup_files)
        
        # Define edges - starting directly from generate_report
        self.state_graph.add_edge(START, "generate_report")
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

    def _generate_report(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """Generate PDF report and upload directly to GCS"""
        try:
            if state.get("error"):
                return state
            
            return state
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            raise

    def _cleanup_files(self, state: _ReportGeneratorState) -> _ReportGeneratorState:
        """No longer needed as we clean up temporary files immediately"""
        return state
from fastapi import APIRouter, HTTPException, status
from helper.database import db_postgres
from helper.rmq import RabbitMQHelper
from typing import Optional, Dict, Any
from pydantic import BaseModel
from helper.database import DatabaseError
from config.logging import logger
import uuid
from datetime import datetime
from service.patient_service import PatientService
import os
from agent.report_generator_agent import AgentReportGenerator
from schema.base import BaseResponse

router = APIRouter()
rmq_helper = RabbitMQHelper()


class GenerateReportRequest(BaseModel):
    appointment_patient_id: str
    appointment_id: str

class GenerateAppointmentReportRequest(BaseModel):
    appointment_id: str

class ReportURLResponse(BaseModel):
    appointment_patient_id: str
    name: str
    report_url: str

class GenerateReportResponse(BaseModel):
    status: str
    message: str
    batch_id: str

class GetReportByIDResponse(BaseModel):
    status: str
    message: str
    url: str

class LibreOfficeVersionResponse(BaseModel):
    version: str
    status: str
    message: str

class GenerateConclusionRequest(BaseModel):
    appointment_patient_id: str

class GenerateConclusionResponse(BaseModel):
    status: str
    message: str
    conclusion: str

class GenerateAdviceRequest(BaseModel):
    appointment_patient_id: str

class GenerateAdviceResponse(BaseModel):
    status: str
    message: str
    advice: str

class GetReportByIDRequest(BaseModel):
    appointment_patient_id: str
    appointment_id: str

class GetReportByNIKRequest(BaseModel):
    nik: str
    appointment_id: str

class ReportStatusResponse(BaseModel):
    status: str
    message: str
    url: Optional[str] = None

@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report(request: GenerateReportRequest, language: str = "id"):
    """
    Queue report generation request for asynchronous processing.
    Returns immediately with a batch ID that can be used to check status.
    """
    try:
        # Get patient name from database
        patient_query = """
        SELECT p.name as patient_name, cc.name as company_name
        FROM b2b_bumame_appointment_patient p
        JOIN b2b_bumame_appointment a ON p.appointment_id = a.id
        JOIN b2b_bumame_company_client cc ON a.company_client_id = cc.id
        WHERE p.id = %s AND p.appointment_id = %s 
        AND p.is_deleted = 0 AND a.is_deleted = 0 AND cc.is_deleted = 0
        """
        try:
            patient_data = db_postgres.fetch_query(
                patient_query, 
                (request.appointment_patient_id, request.appointment_id)
            )
        except DatabaseError as de:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(de)
            )
        
        if not patient_data:
            raise ValueError(f"Patient not found with ID: {request.appointment_patient_id}")
        
        patient_name = patient_data[0][0]
        company_name = patient_data[0][1]
        
        # Create safe names for filename
        unique_id = str(uuid.uuid4())[:8]
        safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c.isspace()).replace(" ", "_")
        safe_company_name = "".join(c for c in company_name if c.isalnum() or c.isspace()).replace(" ", "_")
        
        # Add timestamp to filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.appointment_id}_{request.appointment_patient_id}_{safe_patient_name}_{safe_company_name}_{timestamp}"
        
        # Get patient data from database with appointment_id
        patient_data = PatientService.get_patient_data(request.appointment_patient_id, request.appointment_id, language)
        
        # Add filename and language to patient data
        patient_data['filename'] = filename
        patient_data['language'] = language
        
        # Generate unique batch ID
        batch_id = str(uuid.uuid4())

        # agent = AgentReportGenerator()
        # agent.run_with_data(patient_data)

        PatientService.update_status_to_generating(request.appointment_patient_id, request.appointment_id)

        queue_name = os.getenv('QUEUE_NAME_REPORT_CONSUMER', 'report_generation')
        await rmq_helper.publish(queue_name, {
            "batch_id": batch_id,
            "patient_data": patient_data
        })
        
        return GenerateReportResponse(
            status="processing",
            message="Report generation has been queued",
            batch_id=batch_id
        )

    except Exception as e:
        logger.error(f"Error queueing report generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
@router.post("/generate-appointment-report", response_model=GenerateReportResponse)
async def generate_appointment_report(request: GenerateAppointmentReportRequest, language: str = "id"):
    """
    Queue report generation request for asynchronous processing.
    Returns immediately with a batch ID that can be used to check status.
    """
    try:
        # Get patient name from database
        patient_query = """
        SELECT p.name as patient_name, cc.name as company_name, p.id as patient_id
        FROM b2b_bumame_appointment_patient p
        JOIN b2b_bumame_appointment a ON p.appointment_id = a.id
        JOIN b2b_bumame_company_client cc ON a.company_client_id = cc.id
        WHERE p.appointment_id = %s AND p.is_deleted = 0 AND a.is_deleted = 0 AND cc.is_deleted = 0 AND p.status = 'check_out_examination'
        """
        try:
            patient_data = db_postgres.fetch_query(
                patient_query, 
                (request.appointment_id,)
            )
        except DatabaseError as de:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(de)
            )
        
        if len(patient_data) == 0:
            raise ValueError(f"Patient not found with Appointment ID: {request.appointment_id}")
        
        for patient in patient_data:
            patient_name = patient[0]
            company_name = patient[1]
            
            # Create safe names for filename
            unique_id = str(uuid.uuid4())[:8]
            safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c.isspace()).replace(" ", "_")
            safe_company_name = "".join(c for c in company_name if c.isalnum() or c.isspace()).replace(" ", "_")
            
            # Add timestamp to filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{request.appointment_id}_{patient[2]}_{safe_patient_name}_{safe_company_name}_{timestamp}"
            
            # Get patient data from database with appointment_id (default to Indonesian)
            patient_data = PatientService.get_patient_data(patient[2], request.appointment_id, language)

            print(patient[2])
            # Add filename to patient data
            patient_data['filename'] = filename
            patient_data['language'] = language
            
            # Generate unique batch ID
            batch_id = str(uuid.uuid4())
            
            # Queue the report generation request
            queue_name = os.getenv('QUEUE_NAME_REPORT_CONSUMER', 'report_generation')
            print(queue_name)
            await rmq_helper.publish(queue_name, {
                "batch_id": batch_id,
                "patient_data": patient_data
            })
        
        return GenerateReportResponse(
            status="processing",
            message="Report generation has been queued",
            batch_id="292"
        )

    except Exception as e:
        logger.error(f"Error queueing report generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
@router.post("/awaited-generate", response_model=BaseResponse[Dict[str, Any]])
async def awaited_generate_report(request: GenerateReportRequest, language: str = "id"):
    """
    Queue report generation request for asynchronous processing.
    Returns immediately with a batch ID that can be used to check status.
    """
    try:
        # Get patient name from database
        patient_query = """
        SELECT p.name as patient_name, cc.name as company_name
        FROM b2b_bumame_appointment_patient p
        JOIN b2b_bumame_appointment a ON p.appointment_id = a.id
        JOIN b2b_bumame_company_client cc ON a.company_client_id = cc.id
        WHERE p.id = %s AND p.appointment_id = %s 
        AND p.is_deleted = 0 AND a.is_deleted = 0 AND cc.is_deleted = 0
        """
        try:
            patient_data = db_postgres.fetch_query(
                patient_query, 
                (request.appointment_patient_id, request.appointment_id)
            )
        except DatabaseError as de:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(de)
            )
        
        if not patient_data:
            raise ValueError(f"Patient not found with ID: {request.appointment_patient_id}")
        
        patient_name = patient_data[0][0]
        company_name = patient_data[0][1]
        
        # Create safe names for filename
        unique_id = str(uuid.uuid4())[:8]
        safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c.isspace()).replace(" ", "_")
        safe_company_name = "".join(c for c in company_name if c.isalnum() or c.isspace()).replace(" ", "_")
        
        # Add timestamp to filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{request.appointment_id}_{request.appointment_patient_id}_{safe_patient_name}_{safe_company_name}_{timestamp}"
        
        # Get patient data from database with appointment_id
        patient_data = PatientService.get_patient_data(request.appointment_patient_id, request.appointment_id, language)
        
        # Add filename and language to patient data
        patient_data['filename'] = filename
        patient_data['language'] = language
        
        # Generate unique batch ID
        batch_id = str(uuid.uuid4())

        agent = AgentReportGenerator()
        file_path = agent.run_with_data(patient_data)

        return BaseResponse(
            message="Report generation has been completed",
            data={
                "file_path": file_path,
            }
        )

    except Exception as e:
        logger.error(f"Error queueing report generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
from dotenv import load_dotenv
import os
import time
from datetime import datetime

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import healthcheck_api, report_generator_api, cloud_run_job_api
from config.logging import logger

# Set timezone to GMT+7 (Asia/Jakarta)
os.environ['TZ'] = 'Asia/Jakarta'
if hasattr(time, 'tzset'):
    time.tzset()

app = FastAPI(
    title="Bumame General ML Service",
    description="API for General ML Service",
    version="1.0.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

app.include_router(healthcheck_api.router, tags=["system"])
app.include_router(report_generator_api.router, prefix="/report-generator", tags=["report-generator"])
app.include_router(cloud_run_job_api.router, prefix="/cloud-run-job", tags=["cloud-run-job"])

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8000))

    logger.info("Starting the server...")
    logger.info(f"Version: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"Swagger UI: http://0.0.0.0:{port}/docs")


    uvicorn.run(
        "run_api_server:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv('DEBUG', 'false').lower() == 'true',
        log_level="info",
        log_config=None
    )

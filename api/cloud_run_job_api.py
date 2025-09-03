from fastapi import APIRouter, HTTPException, status
from helper.rmq import RabbitMQHelper
from typing import Dict, Any
from config.logging import logger
from schema.base import BaseResponse
from helper.cloud_run_job import _run_job
import os
import subprocess

router = APIRouter()
rmq_helper = RabbitMQHelper()

@router.post("/activate", response_model=BaseResponse[Dict[str, Any]])
async def activate_cloud_run_job():
    try:
        queue_name = os.getenv('QUEUE_NAME_REPORT_CONSUMER', 'report_generation')
        
        # Check how many messages in RMQ queue are available
        queueAvailable = await rmq_helper.get_queue_message_count(queue_name)
        logger.info(f"Queue available: {queueAvailable}")


        # Check how many consumers are running for that queue
        consumerRunning = await rmq_helper.get_queue_consumer_count(queue_name)
        logger.info(f"Consumer running: {consumerRunning}")

        # Determine criterion consumer vs queue count
        consumerVsQueueCrit = [
            {
                "queue": 700,
                "consumer": 5
            },
            {
                "queue": 300,
                "consumer": 4
            },
            {
                "queue": 100,
                "consumer": 3
            },
            {
                "queue": 1,
                "consumer": 1
            },
        ]

        consumerNeedToActivate = 0
        for crit in consumerVsQueueCrit:
            if queueAvailable >= crit["queue"] and consumerRunning < crit["consumer"]:
                consumerNeedToActivate = crit["consumer"] - consumerRunning
                logger.info(f"Activating {crit["consumer"]} Cloud Run Job")
                break


        if consumerNeedToActivate > 0:
            logger.info(f"Activating {consumerNeedToActivate} Cloud Run Job")
            # for _ in range(10):
            #     try:
            #         subprocess.Popen(['uv', 'run', 'report_consumer.py'], 
            #                       stdout=subprocess.PIPE, 
            #                       stderr=subprocess.PIPE)
            #         logger.info("Successfully started a report consumer instance")
            #     except Exception as e:
            #         logger.error(f"Failed to start report consumer: {str(e)}")
            #         raise HTTPException(
            #             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            #             detail=f"Failed to start report consumer: {str(e)}"
            #         )
            job = os.getenv('CLOUD_RUN_JOB_NAME', 'report_generation')
            await _run_job(job, task_count=consumerNeedToActivate)

        return BaseResponse(
            message="Cloud Run Job activated successfully",
            data={
                "queueAvailable": queueAvailable,
                "consumerRunning": consumerRunning,
                "consumerNeedToActivate": consumerNeedToActivate
            }
        )
    except Exception as e:
        logger.error(f"Error activating Cloud Run Job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
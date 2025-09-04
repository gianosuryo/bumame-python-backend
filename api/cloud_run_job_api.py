from fastapi import APIRouter, HTTPException, status
from helper.rmq import RabbitMQHelper
from typing import Dict, Any
from config.logging import logger
from schema.base import BaseResponse
from helper.cloud_run_job import _run_job
import os
import math

router = APIRouter()
rmq_helper = RabbitMQHelper()

@router.post("/activate", response_model=BaseResponse[Dict[str, Any]])
async def activate_cloud_run_job():
    try:
        rmq_prefix = os.getenv('RMQ_PREFIX', '')
        # Skip activating cloud run job in dev environment
        if rmq_prefix == 'dev':
            return BaseResponse(
                message="Cloud Run Job activated successfully",
                data={
                    "queueAvailable": 0,
                    "consumerRunning": 0,
                    "consumerNeedToActivate": 0
                }
            )
        
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
                "consumer": 15
            },
            {
                "queue": 300,
                "consumer": 12
            },
            {
                "queue": 100,
                "consumer": 9
            },
            {
                "queue": 50,
                "consumer": 6
            },
            {
                "queue": 1,
                "consumer": 3
            },
        ]

        consumerNeedToActivate = 0
        for crit in consumerVsQueueCrit:
            if queueAvailable >= crit["queue"] and consumerRunning < crit["consumer"]:
                consumerNeedToActivate = crit["consumer"] - consumerRunning
                logger.info(f"Activating {crit["consumer"]} Cloud Run Job")
                break


        if consumerNeedToActivate > 0:
            taskToActivate = math.ceil(consumerNeedToActivate / 3)
            logger.info(f"Activating {consumerNeedToActivate} Cloud Run Job")
            job = os.getenv('CLOUD_RUN_JOB_NAME', 'report_generation')
            for _ in range(taskToActivate):
                await _run_job(job)

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
    
from helper.rmq import RabbitMQHelper
from agent.report_generator_agent import AgentReportGenerator
import asyncio
import json
import logging
from config.logging import logger
from dotenv import load_dotenv
import os
from typing import Optional, Dict, Any
import aio_pika

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize helpers
rmq_helper = RabbitMQHelper()

# Constants
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
REDIS_TIMEOUT = 10  # seconds

async def process_report_generation(message: Dict[str, Any]) -> None:
    """Process report generation request from queue"""
    batch_id = message.get("batch_id")
    if not batch_id:
        logger.error("No batch_id in message")
        return

    try:
        logger.info(f"Starting report generation for batch {batch_id}")
        patient_data = message.get("patient_data")
        
        if not patient_data:
            raise ValueError("No patient data in message")

        # Generate report using the agent
        logger.info(f"Initializing report generator agent for batch {batch_id}")
        agent = AgentReportGenerator()
        
        for attempt in range(MAX_RETRIES):
            try:
                result = agent.run_with_data(patient_data)
                
                if result.get('url'):
                    logger.info(f"Report generated successfully for batch {batch_id}")
                    url = result['url']
                    logger.info(f"Report url: {url}")
                    return
                else:
                    raise ValueError("Failed to get URL from report generation")
                    
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Attempt {attempt + 1} failed, retrying in {RETRY_DELAY} seconds: {str(e)}")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    raise
                    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error processing report generation for batch {batch_id}: {error_msg}")
        logger.exception("Full traceback:")

async def setup_rabbitmq():
    """Setup RabbitMQ connection and queue"""
    while True:
        try:
            logger.info("Connecting to RabbitMQ...")
            await rmq_helper.connect()
            
            channel = rmq_helper.channel
            queue_name = os.getenv('QUEUE_NAME_REPORT_CONSUMER', 'report_generation')
            prefixed_queue_name = rmq_helper.get_prefixed_queue_name(queue_name)
            
            # Declare main queue without additional configurations
            queue = await channel.declare_queue(
                prefixed_queue_name,
                durable=True  # Keep only durability setting
            )
            
            logger.info(f"Queue '{prefixed_queue_name}' declared successfully")
            
            async def process_message(message: aio_pika.IncomingMessage):
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        await process_report_generation(body)
                    except json.JSONDecodeError as je:
                        logger.error(f"Invalid JSON in message: {str(je)}")
                        # Don't requeue invalid messages
                        await message.reject(requeue=False)
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        # Requeue only if not redelivered
                        await message.reject(requeue=not message.redelivered)
            
            # Start consuming
            await queue.consume(process_message)
            logger.info("Consumer setup completed")
            
            return queue
            
        except aio_pika.exceptions.ConnectionClosed:
            logger.error("RabbitMQ connection closed. Retrying...")
            await asyncio.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"Error setting up RabbitMQ: {str(e)}")
            await asyncio.sleep(RETRY_DELAY)

async def main():
    """Main consumer function"""
    while True:
        try:
            logger.info("Starting report generation consumer...")
            queue = await setup_rabbitmq()
            
            # Keep the consumer running
            logger.info("Consumer is now running and waiting for messages...")
            await asyncio.Future()  # run forever
            
        except asyncio.CancelledError:
            logger.info("Consumer was cancelled, shutting down...")
            break
        except Exception as e:
            logger.error(f"Consumer error: {str(e)}")
            logger.info(f"Retrying in {RETRY_DELAY} seconds...")
            await asyncio.sleep(RETRY_DELAY)
        finally:
            try:
                await rmq_helper.close()
                logger.info("RabbitMQ connection closed")
            except Exception as e:
                logger.error(f"Error closing RabbitMQ connection: {str(e)}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Consumer stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        logger.exception("Full traceback:") 
import aio_pika
from typing import Callable, Any
import json
import asyncio
import os
from helper.common import singleton
import logging

from dotenv import load_dotenv
load_dotenv()

@singleton
class RabbitMQHelper:
    def __init__(self):
        self.url = os.getenv('RABBITMQ_URL', 'amqp://guest:guest@localhost/')
        self.prefix = os.getenv('RMQ_PREFIX', '')  # Get prefix from environment variable
        self.connection = None
        self.channel = None
        self.loop = asyncio.get_event_loop()
        self.tasks = []
        self.logger = logging.getLogger(__name__)

    def get_prefixed_queue_name(self, queue_name: str) -> str:
        """Add prefix to queue name if prefix is set"""
        if self.prefix:
            return f"{self.prefix}_{queue_name}"
        return queue_name

    async def connect(self):
        try:
            if not self.connection or self.connection.is_closed:
                self.connection = await aio_pika.connect_robust(
                    self.url,
                    reconnect_interval=5  # Retry connection every 5 seconds
                )
                self.channel = await self.connection.channel()
                await self.channel.set_qos(prefetch_count=1)
                self.logger.info("Successfully connected to RabbitMQ")
        except Exception as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise

    async def close(self):
        try:
            for task in self.tasks:
                if not task.cancelled():
                    task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            if self.connection and not self.connection.is_closed:
                await self.connection.close()
                self.logger.info("RabbitMQ connection closed")
        except Exception as e:
            self.logger.error(f"Error closing RabbitMQ connection: {str(e)}")

    async def publish(self, queue_name: str, message: Any):
        await self.connect()
        try:
            prefixed_queue_name = self.get_prefixed_queue_name(queue_name)
            queue = await self.channel.declare_queue(
                prefixed_queue_name,
                durable=True  # Make queue persistent
            )
            message_body = json.dumps(message).encode()
            await self.channel.default_exchange.publish(
                aio_pika.Message(
                    body=message_body,
                    delivery_mode=aio_pika.DeliveryMode.PERSISTENT  # Make message persistent
                ),
                routing_key=prefixed_queue_name
            )
            self.logger.debug(f"Message published to queue {prefixed_queue_name}")
        except Exception as e:
            self.logger.error(f"Failed to publish message: {str(e)}")
            raise

    def listen(self, queue_name: str):
        def decorator(callback: Callable):
            async def wrapper(message):
                await callback(message)
            task = self.loop.create_task(self._listen(queue_name, wrapper))
            self.tasks.append(task)
            return wrapper
        return decorator

    async def _listen(self, queue_name: str, callback: Callable):
        while True:
            try:
                await self.connect()
                
                prefixed_queue_name = self.get_prefixed_queue_name(queue_name)
                queue = await self.channel.declare_queue(
                    prefixed_queue_name,
                    durable=True  # Make queue persistent
                )

                async def process_message(message: aio_pika.IncomingMessage):
                    try:
                        # Parse message body
                        body = json.loads(message.body.decode())
                        
                        # Process the message
                        await callback(body)
                        
                        # Explicitly acknowledge the message after successful processing
                        await message.ack()
                        self.logger.debug(f"Message processed and acknowledged: {prefixed_queue_name}")
                        
                    except json.JSONDecodeError as je:
                        self.logger.error(f"Invalid JSON in message: {str(je)}")
                        await message.reject(requeue=False)  # Don't requeue invalid messages
                        
                    except Exception as e:
                        self.logger.error(f"Error processing message: {str(e)}")
                        # Requeue the message only if it hasn't been redelivered too many times
                        requeue = message.redelivered is False
                        await message.reject(requeue=requeue)

                await queue.consume(process_message)
                self.logger.info(f"Started consuming from queue: {prefixed_queue_name}")
                
                # Keep the coroutine running
                await asyncio.Future()
                
            except aio_pika.exceptions.ConnectionClosed:
                self.logger.warning("Connection to RabbitMQ closed. Reconnecting...")
                await asyncio.sleep(5)  # Wait before reconnecting
                
            except asyncio.CancelledError:
                self.logger.info(f"Listener for queue {prefixed_queue_name} was cancelled")
                break
                
            except Exception as e:
                self.logger.error(f"Error in RabbitMQ listener: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying

    async def run(self):
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            await self.close()

    def run_sync(self):
        try:
            self.loop.run_until_complete(self.run())
        except KeyboardInterrupt:
            self.loop.run_until_complete(self.close())
        finally:
            self.loop.close()

# Usage example:
# rmq_helper = RabbitMQHelper()
# await rmq_helper.publish("my_queue", {"key": "value"})
# 
# @rmq_helper.listen("my_queue")
# async def my_callback_function(message):
#     print(f"Received message: {message}")
# 
# rmq_helper.run_sync()

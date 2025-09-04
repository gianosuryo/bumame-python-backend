from functools import wraps
import asyncio
import logging
import random
import aiohttp
import json
import threading
import time
from config.logging import logger
from typing import Any, Callable, Optional
from google.cloud import storage
import os



_global_instances = {}

def singleton(cls):
    @wraps(cls)
    def get_instance(*args, **kwargs):
        if cls not in _global_instances:
            _global_instances[cls] = cls(*args, **kwargs)
            print(
                f"Created new global singleton instance of {cls.__name__}")
        else:
            print(
                f"Using existing global singleton instance of {cls.__name__}")
        return _global_instances[cls]
    return get_instance

def convert_to_int(value) -> int:
    try:
        return int(value)
    except ValueError:
        return 0


class TimeoutTimer:
    """A timer class for managing timeouts in async operations"""
    
    def __init__(self, callback: Callable, timeout_duration: float):
        self.callback = callback
        self.timeout_duration = timeout_duration
        self.timer = None
        self._lock = threading.Lock()
    
    def start(self, initial_delay: float = None):
        """Start the timer with an optional initial delay"""
        with self._lock:
            if self.timer:
                self.timer.cancel()
            
            delay = initial_delay if initial_delay is not None else self.timeout_duration
            self.timer = threading.Timer(delay, self.callback)
            self.timer.start()
    
    def stop(self):
        """Stop the timer"""
        with self._lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None


class FatalError(Exception):
    def __init__(self, message="Something went wrong!"):
        self.message = message
        super().__init__(self.message)

def auto_retry(max_retries: int = 3, delay: float = 1.0):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    logger.info(f"Running {func.__name__} | Attempt {attempt + 1}/{max_retries}")
                    return await func(*args, **kwargs)
                except FatalError:
                    raise
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = delay * (2 ** attempt)
                    logger.warning(
                        f"Error in {func.__name__}. Retrying in {wait_time:.2f} seconds. "
                        f"Attempt {attempt + 1}/{max_retries}. Error: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
        return wrapper
    return decorator

def roulete_bomb():
    "generate random error"
    value = [
        False, False, False, False, False,
        False, False, False, False, False
    ]
    random.shuffle(value)
    result = random.choice(value)

    if result:
        raise ValueError("💣💥 BOOM!!!")


async def track_api_call_cost(request_data: Any, response_data: Any, total_price: float, input_price: float, output_price: float, api_call_count: int):
    url = "https://bumame-sarana-ai-daffa-ai-service-laravel-652345969561.asia-southeast2.run.app/api/api-call-cost-tracker/"
    
    payload = {
        "request_data": json.dumps(request_data),
        "response_data": json.dumps(response_data),
        "total_price": total_price,
        "input_price": input_price,
        "output_price": output_price,
        "api_call_count": api_call_count
    }

    headers = {
        "Auth-Secret": "8155Mill4h4mAN@4LLH4M0UliLlAH"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as response:
                if response.status >= 200 and response.status < 300:
                    logger.info("Successfully tracked API call cost")
                else:
                    logger.error(f"Failed to track API call cost. Status: {response.status}")
    except Exception as e:
        logger.error(f"Error tracking API call cost: {str(e)}")

def download_from_gcs(bucket_name: str, source_blob_name: str, destination_file_name: Optional[str] = None) -> str:
    """
    Downloads a file from Google Cloud Storage to the local tmp directory.
    
    Args:
        bucket_name (str): The name of the GCS bucket
        source_blob_name (str): The path to the file in GCS (e.g. 'folder/file.pdf')
        destination_file_name (Optional[str]): The desired local filename. If not provided, 
                                             uses the basename of source_blob_name
    
    Returns:
        str: The full path to the downloaded file
        
    Raises:
        Exception: If the file cannot be downloaded or if the bucket/blob doesn't exist
    """
    try:
        # Initialize the GCS client
        storage_client = storage.Client()
        
        # Get the bucket
        bucket = storage_client.bucket(bucket_name)
        
        # Get the blob (file)
        blob = bucket.blob(source_blob_name)
        
        # If no destination filename is provided, use the source filename
        if not destination_file_name:
            destination_file_name = os.path.basename(source_blob_name)
            
        # Ensure the tmp directory exists
        tmp_dir = os.path.join(os.getcwd(), "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        
        # Create the full destination path
        destination_path = os.path.join(tmp_dir, destination_file_name)
        
        # Download the file
        logger.info(f"Downloading {source_blob_name} from bucket {bucket_name} to {destination_path}")
        blob.download_to_filename(destination_path)
        
        logger.info(f"Downloaded file successfully to {destination_path}")
        return destination_path
        
    except Exception as e:
        error_msg = f"Error downloading file from GCS: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)

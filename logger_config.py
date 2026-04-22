import logging
import os

def setup_logger():
    # File name for logs
    log_file = "project_activity.log"

    # Create a logger object
    logger = logging.getLogger("UpworkBot")
    logger.setLevel(logging.DEBUG)

    # If handlers already exist, clear them to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # 1. File Handler (To save logs in a file)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)

    # 2. Console Handler (To display logs in the terminal)
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)

    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Global instance
log = setup_logger()
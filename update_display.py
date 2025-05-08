#!/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import os
import logging
from waveshare_epd import epd4in0e
import time
from PIL import Image
import traceback

def update_display(image_path):
    try:
        logging.basicConfig(level=logging.DEBUG)
        logging.info("Updating E-ink Display")

        # Initialize the display
        epd = epd4in0e.EPD()
        epd.init()
        
        # Clear the display
        epd.Clear()
        
        # Open and display the image
        image = Image.open(image_path)
        
        # Calculate scaling ratio while maintaining aspect ratio
        ratio = min(epd.width/image.width, epd.height/image.height)
        new_width = int(image.width * ratio)
        new_height = int(image.height * ratio)
        
        # Resize image maintaining aspect ratio
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Rotate the image 180 degrees
        image = image.rotate(180)
        
        # Create new white background image
        background = Image.new('RGB', (epd.width, epd.height), 'white')
        
        # Calculate position to center the image
        x = (epd.width - new_width) // 2
        y = (epd.height - new_height) // 2
        
        # Paste the resized image onto the center of the background
        background.paste(image, (x, y))
        
        epd.display(epd.getbuffer(background))
        
        # Put display to sleep to save power
        time.sleep(2)
        epd.sleep()
        
    except IOError as e:
        logging.error(f"Error updating display: {e}")
        return False
        
    except KeyboardInterrupt:
        logging.info("Update cancelled by user")
        epd4in0e.epdconfig.module_exit(cleanup=True)
        return False
        
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        traceback.print_exc()
        return False
        
    return True

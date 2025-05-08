"""
Music Player Application for Raspberry Pi

This script implements a music player with the following key features:
- OLED display for track information and battery status
- Rotary encoder for track/volume control
- GPIO-based input handling
- Album art extraction and display
- Battery monitoring

Dependencies:
- pygame
- RPi.GPIO
- adafruit_ssd1306
- tinytag
- SMBus

Configuration:
- Music directory: '/home/MusiPi/Music'
- OLED display: 128x32 pixels
- GPIO pins configured for rotary encoder and switch

Main functions:
- load_music(): Scans and loads music files from the configured directory
- play_pause(): Toggles music playback
- skip_track(): Moves to next or previous track
- display_update(): Updates OLED display with current track and status
- check_encoder(): Handles rotary encoder input for track/volume control
"""

import os
import pygame
import time
import RPi.GPIO as GPIO
from smbus2 import SMBus
from PIL import Image, ImageDraw, ImageFont
import board
import busio
import adafruit_ssd1306
from tinytag import TinyTag
import shutil
import update_display

# --- CONFIGURATION ---
MUSIC_DIR = '/home/Music'
OLED_WIDTH = 128
OLED_HEIGHT = 32
PIN_A = 22  # CLK
PIN_B = 27  # DT
SW = 23     # Switch
I2C_ADDR = 0x36
REG_VOLTAGE = 0x02
REG_CAPACITY = 0x04

print("DEBUG: Starting music player initialization...")

# --- INITIALIZATION ---
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 12)
    print("DEBUG: Loaded DejaVuSans font")
except Exception as e:
    font = ImageFont.load_default()
    print(f"DEBUG: Using default font. Error: {e}")

try:
    print("DEBUG: Initializing I2C and OLED...")
    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, i2c, addr=0x3C)
    image = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(image)
    print("DEBUG: OLED initialized successfully")
except Exception as e:
    print(f"DEBUG ERROR: OLED initialization failed: {e}")
    exit(1)

try:
    print("DEBUG: Initializing GPIO...")
    GPIO.setmode(GPIO.BCM)  # Use BCM numbering
    GPIO.setup(PIN_A, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(PIN_B, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(SW, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print("DEBUG: Successfully initialized GPIO")
    print(f"DEBUG: Initial GPIO values - A: {GPIO.input(PIN_A)}, B: {GPIO.input(PIN_B)}, SW: {GPIO.input(SW)}")
except Exception as e:
    print(f"DEBUG ERROR: Failed to initialize GPIO: {repr(e)}")
    exit(1)

# --- GLOBAL VARIABLES ---
selected = 0
playing = False
songs = []
last_battery_update = 0
last_a = GPIO.input(PIN_A)
last_b = GPIO.input(PIN_B)
last_sw = GPIO.input(SW)
current_volume = 0.02
encoder_count = 0
last_press_time = 0
press_count = 0
last_encoder_state = 0
current_song_path = None
last_display_update = 0
last_eink_update = 0
scroll_position = 0
scroll_direction = 1  # 1 for right to left, -1 for left to right
scroll_speed = 1
scroll_pause = 0
last_scroll_time = 0
scroll_update_count = 0




def get_status_symbol(playing):
    try:
        return "▶" if playing else "❚❚"
    except:
        return "> Play" if playing else "|| Pause"

def read_battery():
    #print("DEBUG: Attempting to read battery...")
    try:
        with SMBus(1) as bus:
            raw = bus.read_word_data(I2C_ADDR, REG_VOLTAGE)
            raw = ((raw << 8) & 0xFF00) + (raw >> 8)
            voltage = raw * 1.25 / 1000 / 16
            
            raw = bus.read_word_data(I2C_ADDR, REG_CAPACITY)
            raw = ((raw << 8) & 0xFF00) + (raw >> 8)
            percent = raw / 256
            #print(f"DEBUG: Battery reading successful - Voltage: {voltage:.2f}V, Percent: {percent:.1f}%")
            return voltage, percent
    except Exception as e:
        print(f"DEBUG ERROR: Battery reading failed: {e}")
        return 0.0, 0.0

def load_music():
    global songs
    print(f"DEBUG: Loading music from {MUSIC_DIR}...")
    try:
        songs = [f for f in os.listdir(MUSIC_DIR) if f.endswith(('.flac', '.mp3', '.wav'))]
        songs.sort()
        if not songs:
            print("DEBUG ERROR: No music files found!")
            exit(1)
        print(f"DEBUG: Found {len(songs)} songs")
        for i, song in enumerate(songs[:5]):  # Print first 5 songs
            print(f"DEBUG: Song {i}: {song}")
        if len(songs) > 5:
            print(f"DEBUG: ... and {len(songs)-5} more songs")
    except Exception as e:
        print(f"DEBUG ERROR: Failed to load music: {e}")
        exit(1)
        
def extract_album_art(song_path, output_path="/tmp/current_cover.jpg"):
    """Extract album art and save as JPEG file"""
    try:
        print(f"DEBUG: Attempting to extract album art from {song_path}")
        tag = TinyTag.get(song_path, image=True)
        if tag and tag.images and tag.images.any:
            img_data = tag.images.any.data
            with open(output_path, 'wb') as f:
                f.write(img_data)
            print(f"DEBUG: Saved album art to {output_path}")
            return True
        print("DEBUG: No album art found in file")
        # Copy default image if no art found
        shutil.copyfile('default_cover.jpg', output_path)
        return False
    except Exception as e:
        print(f"DEBUG ERROR: Album art extraction failed: {e}")
        return False

def display_update():
    global last_battery_update, current_song_path, scroll_position, last_scroll_time, scroll_update_count
    
    # Only print debug message occasionally to reduce spam
    scroll_update_count += 1
    if scroll_update_count % 10 == 0:  # Only print every 10th update
        #print("DEBUG: Updating display...")
        scroll_update_count = 0
    
    current_song_path = os.path.join(MUSIC_DIR, songs[selected]) 
    voltage, percent = 0.0, 0.0
    
    if time.time() - last_battery_update > 0:
        voltage, percent = read_battery()
        last_battery_update = time.time()
    
    try:
        draw.rectangle((0, 0, OLED_WIDTH, OLED_HEIGHT), outline=0, fill=0)
        
        # Get the full track name
        track = songs[selected]
        
        # Calculate text width
        text_width = 0
        try:
            text_width = draw.textlength(track, font=font)
        except AttributeError:
            # For older PIL versions
            text_width = font.getsize(track)[0]
        
        # Only scroll if text is longer than display width
        if text_width > OLED_WIDTH - 30:  # Leave space for battery percentage
            # Update scroll position every 0.3 seconds
            current_time = time.time()
            if current_time - last_scroll_time > 0.3:
                scroll_position = (scroll_position + 1) % len(track)
                last_scroll_time = current_time
            
            # Create a circular scrolling text
            # Display characters from current position, wrapping around to the beginning
            display_text = ""
            for i in range(15):  # Show about 15 characters
                char_pos = (scroll_position + i) % len(track)
                display_text += track[char_pos]
            
            draw.text((0, 0), display_text, font=font, fill=255)
        else:
            # If text is short, just display it normally
            draw.text((0, 0), track, font=font, fill=255)
            
        draw.text((OLED_WIDTH-25, 0), f"{percent:.0f}%", font=font, fill=255)
        draw.text((0, 16), get_status_symbol(playing), font=font, fill=255)
        draw.text((OLED_WIDTH-50, 16), f"Vol:{int(current_volume*100)}", font=font, fill=255)
        
        # Flip the image 180 degrees (both horizontally and vertically)
        rotated_image = image.transpose(Image.FLIP_TOP_BOTTOM)
        rotated_image = rotated_image.transpose(Image.FLIP_LEFT_RIGHT)
        
        oled.image(rotated_image)
        oled.show()
        
        # Only print debug message occasionally
        if scroll_update_count == 0:
            #print(f"DEBUG: Display updated - Track: {track[:20]}{'...' if len(track) > 20 else ''}")
            pass
        # Don't extract album art on every display update
        if not hasattr(display_update, 'last_art_update') or time.time() - display_update.last_art_update > 5:
            extract_album_art(current_song_path)
            display_update.last_art_update = time.time()
            
    except Exception as e:
        print(f"DEBUG ERROR: Display update failed: {e}")

# Add this attribute to the function to store the last art update time
display_update.last_art_update = 0

def check_encoder():
    global selected, last_a, last_b, last_sw, current_volume, encoder_count, press_count, last_press_time
    global last_states, scroll_position
    
    # Initialize last_states if it doesn't exist
    if 'last_states' not in globals():
        last_states = []
    
    # Read current encoder values
    a = GPIO.input(PIN_A)
    b = GPIO.input(PIN_B)
    sw = GPIO.input(SW)
    current_time = time.time()
    
    # Detect state changes
    if a != last_a or b != last_b:  # State change detected
        # Record the new state
        current_state = (a, b)
        last_states.append(current_state)
        
        # Keep only the last 4 states (for a full cycle)
        if len(last_states) > 2:
            last_states.pop(0)
        
        print(f"DIAGNOSTIC: State change - Current: A={a}, B={b}, States buffer: {last_states}")
        
        # Check for complete clockwise sequence (right rotation)
        if len(last_states) == 2:
            # Clockwise full cycle: [(1,1), (1,0), (0,0), (1,1)]
            if (last_states[0] == (1,1) and 
                last_states[1] == (1,0)):
                
                encoder_count += 1
                print(f"DEBUG: Encoder change #{encoder_count} - Complete clockwise cycle detected")
                
                if playing:  # Volume control when playing
                    current_volume = min(1.0, current_volume + 0.01)
                    print(f"DEBUG: Volume increased to {int(current_volume*100)}%")
                    pygame.mixer.music.set_volume(current_volume/2)
                else:  # Track selection when not playing
                    scroll_position = 0
                    selected = (selected + 1) % len(songs)
                    print(f"DEBUG: Next track selected: {selected} - {songs[selected]}")
                display_update()
                
                # Clear the states after processing
                last_states = [last_states[-1]]  # Keep the last state for next cycle
            
            # Counter-clockwise full cycle: [(1,1), (0,1), (0,0), (1,1)]
            elif (last_states[0] == (1,1) and 
                  last_states[1] == (0,1)):
                
                encoder_count += 1
                print(f"DEBUG: Encoder change #{encoder_count} - Complete counter-clockwise cycle detected")
                
                if playing:  # Volume control when playing
                    current_volume = max(0.0, current_volume - 0.01)
                    print(f"DEBUG: Volume decreased to {int(current_volume*100)}%")
                    pygame.mixer.music.set_volume(current_volume/2)
                else:  # Track selection when not playing
                    scroll_position = 0
                    selected = (selected - 1) % len(songs)
                    print(f"DEBUG: Previous track selected: {selected} - {songs[selected]}")
                display_update()
                
                # Clear the states after processing
                last_states = [last_states[-1]]  # Keep the last state for next cycle
    
    # Check for button press (active low - 0 when pressed)
    if sw == 0 and last_sw == 1:  # Button just pressed
        print(f"DEBUG: Button press detected at {current_time:.3f}")
        
        if current_time - last_press_time > 1.5:  # Reset counter if more than 1.5 seconds between presses
            press_count = 0
            print("DEBUG: Button press count reset")
        
        press_count += 1
        print(f"DEBUG: Button press detected, count: {press_count}")
        last_press_time = current_time
        
        # For multi-press detection, we need to wait for a short time to collect all presses
        if press_count == 1:
            # Start a timer to wait for more presses
            timer_start = time.time()
            # Wait up to 0.5 seconds for additional presses
            while time.time() - timer_start < 0.8:
                # Check if button is pressed again
                time.sleep(0.18) # Debounce delay
                new_sw = GPIO.input(SW)
                if new_sw == 0 and last_sw == 1:  # New press detected
                    press_count += 1
                    print(f"DEBUG: Additional press detected, count: {press_count}")
                    last_press_time = time.time()
                    # Reset timer to wait for more presses
                    timer_start = time.time()
                last_sw = new_sw
                time.sleep(0.05)  # Small delay to prevent CPU hogging
            
            # After waiting, process the collected presses
            if press_count == 1:
                print("DEBUG: Single press confirmed, triggering play/pause")
                play_pause()
            elif press_count == 2 and playing:
                print("DEBUG: Double press confirmed, skipping forward")
                skip_track(forward=True)
            elif press_count == 3 and playing:
                print("DEBUG: Triple press confirmed, skipping backward")
                skip_track(forward=False)
            
            # Reset press count after processing
            press_count = 0
        
    
    # Update last values
    last_a, last_b, last_sw = a, b, sw

def play_pause():
    global playing, current_song_path
    print("DEBUG: Play/Pause function called")
    try:
        if playing:
            pygame.mixer.music.pause()
            print("DEBUG: Music paused")
        else:
            if not pygame.mixer.music.get_busy():
                current_song_path = os.path.join(MUSIC_DIR, songs[selected]) 
                song_path = os.path.join(MUSIC_DIR, songs[selected])
                print(f"DEBUG: Loading song: {song_path}")
                pygame.mixer.music.load(song_path)
                pygame.mixer.music.play()
                print("DEBUG: Started playing new track")
                extract_album_art(current_song_path)
            else:
                pygame.mixer.music.unpause()
                print("DEBUG: Music unpaused")
        playing = not playing
        display_update()
    except Exception as e:
        print(f"DEBUG ERROR: Play/Pause failed: {e}")

def skip_track(forward=True):
    global selected, playing, current_song_path, scroll_position
    direction = "forward" if forward else "backward"
    print(f"DEBUG: Skip track {direction} called")
    
    try:
        if forward:
            scroll_position = 0
            selected = (selected + 1) % len(songs)
        else:
            scroll_position = 0
            selected = (selected - 1) % len(songs)
        
        print(f"DEBUG: New selected track: {selected} - {songs[selected]}")
        
        if playing:
            current_song_path = os.path.join(MUSIC_DIR, songs[selected]) 
            song_path = os.path.join(MUSIC_DIR, songs[selected])
            print(f"DEBUG: Loading and playing: {song_path}")
            pygame.mixer.music.load(song_path)
            pygame.mixer.music.play()
        display_update()
        extract_album_art(current_song_path)
    except Exception as e:
        print(f"DEBUG ERROR: Skip track failed: {e}")

def main():
    global last_display_update, last_eink_update
    
    print("DEBUG: Entering main function")
    
    try:
        print("DEBUG: Initializing pygame mixer")
        pygame.mixer.init()
        pygame.mixer.music.set_volume(current_volume/2)
        print(f"DEBUG: Mixer initialized, volume set to {int(current_volume*200)}%")
    except Exception as e:
        print(f"DEBUG ERROR: Pygame mixer initialization failed: {e}")
        exit(1)
    
    load_music()
    display_update()
    last_display_update = time.time()
    #update_display.update_display("/tmp/current_cover.jpg")
    last_eink_update = time.time()
    
    print("DEBUG: Entering main loop")
    try:
        while True:
            # Check encoder and button
            check_encoder()
            
            # Auto-advance to next track when current one ends
            if playing and not pygame.mixer.music.get_busy():
                print("DEBUG: Current track ended, auto-advancing to next track")
                skip_track(forward=True)
            
            # Get current time once for both checks
            current_time = time.time()
            
            # Update display at a reasonable rate for scrolling (every 0.1 seconds)
            if current_time - last_display_update >= 0.1:
                display_update()
                last_display_update = current_time
                
            # Check if 180 seconds have passed since last e-ink update
            if current_time - last_eink_update >= 210:
                print("DEBUG: Periodic e-ink update (180-second interval)")
                update_display.update_display("/tmp/current_cover.jpg")
                last_eink_update = current_time
            
            time.sleep(0.01)  # Small sleep to prevent CPU hogging
            
    except KeyboardInterrupt:
        print("DEBUG: KeyboardInterrupt detected, cleaning up...")
        pygame.mixer.music.stop()
        oled.fill(0)
        oled.show()
        GPIO.cleanup()  # Clean up GPIO on exit
        print("DEBUG: Cleanup complete, exiting")
    except Exception as e:
        print(f"DEBUG ERROR: Unexpected error in main loop: {e}")
        GPIO.cleanup()  # Clean up GPIO on exit


if __name__ == "__main__":
    print("DEBUG: Script started")
    main()

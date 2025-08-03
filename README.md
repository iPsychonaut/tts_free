TTS Free
========

A high-quality, cross-platform text-to-speech (TTS) application with a graphical interface.  
Built using Python, Coqui TTS, PyQt5, and Pygame for seamless voice synthesis and audio playback.

----------------------
FEATURES  
----------------------

- Load multi-line .txt files for line-by-line speech synthesis  
- High-quality voice output using Coqui TTS (VITS model)  
- Real-time audio playback using Pygame  
- Simple and intuitive PyQt5 GUI  
- Displays both current and next text lines  
- "Play" and "Next" buttons for precise navigation  
- Cross-platform (Linux, Windows, macOS)

----------------------
INSTALLATION  
----------------------

Make sure Python 3.8 or newer is installed on your system.

Step 1: Clone the repository  
git clone https://github.com/YourUsername/tts-free.git  
cd tts-free

Step 2: Install dependencies

pip install TTS PyQt5 pygame pandas

Also install system requirements:

Ubuntu/Debian:  
sudo apt update  
sudo apt install ffmpeg espeak  

macOS (Homebrew):  
brew install ffmpeg espeak  

Windows:  
Ensure ffmpeg and espeak are installed and added to your PATH.

----------------------
USAGE  
----------------------

Run the application with:

python tts_free.py

Then:
- Click "Load Text File" to select a `.txt` file  
- Click "▶️ Play Current" to hear the selected line  
- Click "⏭️ Next" to move to the next line and play it  
- View both the current and next lines in the interface  
- Change the speaker voice by modifying this line in the script:  
  speaker_id = "p240"  

To list all available speakers:  
print(tts.speakers)

----------------------
BUILDING A STANDALONE EXECUTABLE  
----------------------

Linux/macOS:  
pyinstaller --onefile --windowed tts_free.py  

Windows:  
pyinstaller --onefile --windowed tts_free.py  

The output will be located in the `dist/` folder.

----------------------
LICENSE  
----------------------

This project is licensed under the MIT License. See the LICENSE file for details.

----------------------
AUTHOR  
----------------------

Ian Michael Bollinger  
Email: ian.michael.bollinger@gmail.com  
GitHub: https://github.com/iPsychonaut

----------------------
ISO DOCUMENTATION NOTES  
----------------------

This project is documented in alignment with ISO 9001 traceability:  
- Version: 1.0  
- Created: 2025-08-02  
- Reviewed: ✅ Functionally validated on Linux  
- Dependencies: Coqui TTS, PyQt5, Pygame, pandas, ffmpeg, espeak

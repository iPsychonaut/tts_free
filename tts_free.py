#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS Free (Cross-Platform GUI)

High-Quality Text-to-Speech Tool using Coqui TTS + PyQt5

Created on: 2025-08-02
Version: 1.0
Author: Ian Michael Bollinger (iPsychonaut)
Contact: ian.michael.bollinger@gmail.com
License: MIT

Dependencies:
- TTS
- PyQt5
- pygame
- pandas
- espeak
- ffmpeg
"""

# Standard Library Imports
import sys
import tempfile

# Third-party Imports
import pandas as pd
import pygame
from TTS.api import TTS
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QLabel, QFileDialog, QTextEdit
)

# Initialize global TTS engine and audio playback system
tts = TTS(model_name="tts_models/en/vctk/vits", progress_bar=False, gpu=False)
pygame.mixer.init()


def synthesize_to_file(text):
    """
    Convert input text to a speech audio file using Coqui TTS.

    Parameters
    ----------
    text : str
        The input string to be synthesized into speech.

    Returns
    -------
    str
        Path to the generated temporary WAV file containing spoken audio.

    Raises
    ------
    ValueError
        If synthesis fails or text is empty.
    """
    if not text.strip():
        raise ValueError("Text input is empty.")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')

    # Select a speaker from the available list
    speaker_id = "p240"  # Replace with any ID from tts.speakers
    tts.tts_to_file(text=text, speaker=speaker_id, file_path=temp_file.name)

    return temp_file.name


class AudioBuffer:
    """
    Buffer manager for preloading and sequencing TTS audio playback.

    Attributes
    ----------
    df : pd.DataFrame
        DataFrame containing text lines to be converted.
    index : int
        Current index of the active text/audio.
    buffer : list
        List of two preloaded audio file paths [current, next].
    """

    def __init__(self, dataframe):
        """
        Initialize the buffer with input text DataFrame.

        Parameters
        ----------
        dataframe : pd.DataFrame
            A DataFrame with a 'text' column for TTS processing.
        """
        self.df = dataframe
        self.index = 0
        self.buffer = [None, None]
        self.load_next(0)
        self.load_next(1)

    def load_next(self, slot):
        """
        Preload a text line at index+slot and convert it to audio.

        Parameters
        ----------
        slot : int
            0 for current, 1 for next.

        Returns
        -------
        None
        """
        if self.index + slot < len(self.df):
            text = self.df.iloc[self.index + slot]['text']
            self.buffer[slot] = synthesize_to_file(text)
        else:
            self.buffer[slot] = None

    def play_current(self):
        """
        Play the currently buffered audio clip.

        Returns
        -------
        None
        """
        if self.buffer[0]:
            pygame.mixer.music.load(self.buffer[0])
            pygame.mixer.music.play()

    def advance(self):
        """
        Move to the next audio line, update buffer, and play it.

        Returns
        -------
        None
        """
        if self.index + 1 < len(self.df):
            self.index += 1
            self.buffer[0] = self.buffer[1]
            self.load_next(1)
            self.play_current()

    def current_text(self):
        """
        Get the text of the current line.

        Returns
        -------
        str
            Current text line or an empty string.
        """
        return self.df.iloc[self.index]['text'] if self.index < len(self.df) else ""

    def next_text(self):
        """
        Get the text of the next line.

        Returns
        -------
        str
            Next text line or "(end)" if none left.
        """
        return self.df.iloc[self.index + 1]['text'] if self.index + 1 < len(self.df) else "(end)"


class TTSApp(QWidget):
    """
    Main GUI class for the TTS Free application using PyQt5.

    Features:
    - Load text file
    - Play current line
    - Advance and play next line
    - Display current and next rows of text
    """

    def __init__(self):
        """Initialize the main application window and UI."""
        super().__init__()
        self.setWindowTitle("High-Quality TTS Tool")
        self.resize(600, 300)
        self.buffer = None
        self.setup_ui()

    def setup_ui(self):
        """
        Create and lay out all GUI elements and connect actions.

        Returns
        -------
        None
        """
        self.layout = QVBoxLayout()

        self.load_button = QPushButton("Load Text File")
        self.load_button.clicked.connect(self.load_file)

        self.current_label = QLabel("Current:")
        self.current_text = QTextEdit()
        self.current_text.setReadOnly(True)

        self.next_label = QLabel("Next:")
        self.next_text = QTextEdit()
        self.next_text.setReadOnly(True)

        self.play_button = QPushButton("▶️ Play Current")
        self.play_button.clicked.connect(self.play_current)

        self.next_button = QPushButton("⏭️ Next")
        self.next_button.clicked.connect(self.next_and_play)

        for widget in [
            self.load_button,
            self.current_label, self.current_text,
            self.next_label, self.next_text,
            self.play_button, self.next_button
        ]:
            self.layout.addWidget(widget)

        self.setLayout(self.layout)

    def load_file(self):
        """
        Load a text file into the TTS buffer for playback.

        Returns
        -------
        None
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Text File", "", "Text Files (*.txt)")
        if file_path:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            df = pd.DataFrame(lines, columns=["text"])
            self.buffer = AudioBuffer(df)
            self.update_display()
            self.buffer.play_current()

    def update_display(self):
        """
        Refresh the GUI with current and next text rows.

        Returns
        -------
        None
        """
        if self.buffer:
            self.current_text.setText(self.buffer.current_text())
            self.next_text.setText(self.buffer.next_text())

    def play_current(self):
        """
        Play the audio for the currently selected row.

        Returns
        -------
        None
        """
        if self.buffer:
            self.buffer.play_current()

    def next_and_play(self):
        """
        Advance to the next text line and play its audio.

        Returns
        -------
        None
        """
        if self.buffer:
            self.buffer.advance()
            self.update_display()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TTSApp()
    window.show()
    sys.exit(app.exec_())

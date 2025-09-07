#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS Free — Desktop (PyQt5)

- Prefers Coqui TTS (VCTK, speaker p240 — UK female)
- Second choice: Piper TTS (en_GB-cori-high — UK female, offline, MIT)
- eSpeak NG fallback is OFF by default (enable with a checkbox)
- Spacebar/Next advances exactly one sentence
- Wayland-safe: forces Qt to XCB when EGL/Wayland missing
- Debugging: set TTS_FREE_DEBUG=1 for verbose logs

License: MIT (this app)
Coqui: MPL-2.0 (model from VCTK, CC BY 4.0, requires attribution)
Piper: MIT (models in rhasspy/piper-voices are free)
"""

from __future__ import annotations
import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")  # Wayland/EGL quirks

import re, sys, csv, shutil, tempfile, threading, subprocess, json, platform as pyplat
from dataclasses import dataclass
from typing import List, Optional, Tuple

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl

try:
    from docx import Document
except Exception:
    Document = None

DEBUG = bool(int(os.environ.get("TTS_FREE_DEBUG", "0") or "0"))

# --- Piper UK female voices you have on disk ---
PIPER_VOICES = {
    "Piper (en_GB — Cori, high)": "en_GB-cori-high",
    "Piper (en_GB — Semaine, medium)": "en_GB-semaine-medium",
    "Piper (en_GB — Southern English Female, low)": "en_GB-southern_english_female-low",
}

# ---------- Utils ----------
def log(msg: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {msg}", file=sys.stderr, flush=True)

def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base, *parts)

def read_text(path: str) -> str:
    if path.lower().endswith(".txt"):
        return open(path, "r", encoding="utf-8").read()
    if path.lower().endswith(".docx") and Document:
        return "\n".join(p.text for p in Document(path).paragraphs)
    raise RuntimeError("Please choose a .txt or .docx file")

def split_sentences(text: str) -> List[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
    return [p for p in (s.strip() for s in parts) if p]

def load_pron_csv(path: str) -> List[Tuple[str, str]]:
    rules: List[Tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = (row.get("term") or "").strip()
            rep = (row.get("replacement") or "").strip()
            if t and rep:
                rules.append((t, rep))
    return rules

def apply_pron(text: str, rules: List[Tuple[str, str]]) -> str:
    out = text
    for term, rep in rules:
        out = re.sub(rf"\b{re.escape(term)}\b", rep, out, flags=re.IGNORECASE)
    return out

# ---------- Backends ----------
class _BaseTTS:
    def synth_to_wav(self, text: str) -> str: raise NotImplementedError
    def name(self) -> str: return "Unknown"

# Coqui (VCTK vits) — female UK speakers include p240 (well-regarded)
COQUI_OK = False
TTS = None
try:
    if sys.version_info < (3, 12):
        from TTS.api import TTS as _TTS  # type: ignore
        TTS = _TTS
        COQUI_OK = True
except Exception:
    COQUI_OK = False

class CoquiBackend(_BaseTTS):
    def __init__(self, speaker: str = "p240") -> None:
        if not COQUI_OK or TTS is None:
            raise RuntimeError("Coqui not available (Python >=3.12 or import error).")
        model_dir = resource_path("models", "vctk_vits")
        model_pth = os.path.join(model_dir, "model_file.pth")
        cfg_json = os.path.join(model_dir, "config.json")
        if not (os.path.isfile(model_pth) and os.path.isfile(cfg_json)):
            raise RuntimeError("Coqui model files not found in ./models/vctk_vits")
        log(f"Loading Coqui model from {model_dir}")
        self.tts = TTS(model_path=model_pth, config_path=cfg_json,
                       progress_bar=False, gpu=False)
        self.speaker = speaker

    def synth_to_wav(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty text")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        self.tts.tts_to_file(text=text, speaker=self.speaker, file_path=tmp.name)
        return tmp.name

    def name(self) -> str: return f"Coqui TTS (VCTK, {self.speaker})"

# Piper (MIT) — use en_GB-cori-high by default (female UK)
class PiperBackend(_BaseTTS):
    def __init__(self, model_basename: str = "en_GB-cori-high") -> None:
        env_bin = os.environ.get("PIPER_BIN")
        candidates = []
        if env_bin:
            candidates.append(env_bin)
        candidates.append(resource_path("piper", "piper.exe" if os.name == "nt" else "piper"))

        exe = next((p for p in candidates if p and os.path.isfile(p)), "")
        log(f"Piper probe: candidates={candidates} -> picked={exe!r}")
        if not exe:
            raise RuntimeError("Piper binary not found. Expected env PIPER_BIN or ./piper/piper(.exe)")

        env_model_exact = os.environ.get("PIPER_MODEL")
        env_models_dir = os.environ.get("PIPER_MODEL_DIR")

        model = ""
        cfg = ""

        if env_model_exact and os.path.isfile(env_model_exact):
            model = env_model_exact
            j = env_model_exact + ".json"
            cfg = j if os.path.isfile(j) else ""
        else:
            search_dirs = []
            if env_models_dir:
                search_dirs.append(env_models_dir)
            search_dirs.append(resource_path("piper"))

            for d in search_dirs:
                if d and os.path.isdir(d):
                    m = os.path.join(d, f"{model_basename}.onnx")
                    j = m + ".json"
                    if os.path.isfile(m):
                        model = m
                        cfg = j if os.path.isfile(j) else ""
                        break

        log(f"Piper model probe: model={model!r}, cfg={cfg!r}")
        if not model:
            raise RuntimeError(f"Piper model not found: {model_basename}.onnx (set PIPER_MODEL_DIR or PIPER_MODEL)")

        self.exe = exe
        self.model = model
        self.cfg = (cfg or None)
        self.model_basename = model_basename

    def synth_to_wav(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty text")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav"); tmp.close()
        cmd = [self.exe, "-m", self.model, "--output_file", tmp.name]
        if self.cfg:
            cmd.extend(["-c", self.cfg])
        log(f"Piper synth: {cmd}")
        subprocess.run(cmd, input=text.encode("utf-8"), check=True)
        return tmp.name

    def name(self) -> str:
        return f"Piper ({self.model_basename})"


# eSpeak NG (kept as optional last resort)
class EspeakBackend(_BaseTTS):
    def __init__(self, voice: str = "en-gb+f2", rate: int = 180, pitch: int = 50) -> None:
        exe = shutil.which("espeak-ng") or shutil.which("espeak")
        if not exe:
            raise RuntimeError("eSpeak NG not found in PATH")
        self.exe, self.voice, self.rate, self.pitch = exe, voice, rate, pitch

    def synth_to_wav(self, text: str) -> str:
        text = (text or "").strip()
        if not text:
            raise ValueError("Empty text")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        cmd = [self.exe, "-v", self.voice, "-s", str(self.rate),
               "-p", str(self.pitch), "-w", tmp.name, text]
        log(f"eSpeak synth: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        return tmp.name

    def name(self) -> str: return f"eSpeak NG ({self.voice})"

# Backend chooser: prefer Coqui -> Piper; eSpeak only if allowed
def choose_backend(allow_espeak: bool, coqui_speaker: str, piper_model: str) -> _BaseTTS:
    errors: List[str] = []
    # Try Coqui (female UK p240)
    if COQUI_OK:
        try:
            return CoquiBackend(coqui_speaker)
        except Exception as e:
            errors.append(f"Coqui: {e}")
            log(errors[-1])
    # Try Piper (female UK en_GB-cori-high)
    try:
        return PiperBackend(piper_model)
    except Exception as e:
        errors.append(f"Piper: {e}")
        log(errors[-1])
    # Optional: eSpeak
    if allow_espeak:
        try:
            return EspeakBackend("en-gb+f2")
        except Exception as e:
            errors.append(f"eSpeak: {e}")
            log(errors[-1])
    # If we’re here, nothing worked
    raise RuntimeError("No speech backend available:\n" + "\n".join(errors))

# ---------- GUI ----------
LICENSE_TEXT = """TTS Free — Licensing & Attribution
-----------------------------------
App:
  • TTS Free (MIT)

Speech Engines:
  • Coqui TTS — MPL 2.0 (model code)
    VCTK Corpus — CC BY 4.0 (attribution required)
  • Piper — MIT (binary and voice packs in rhasspy/piper-voices)
  • eSpeak NG — GPLv3 (optional, off by default)
"""

@dataclass
class AudioQueue:
    items: List[str]
    idx: int = 0
    cur_wav: Optional[str] = None
    next_wav: Optional[str] = None

class Main(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.rules: List[Tuple[str, str]] = []
        self.queue = AudioQueue([])
        self.player = QMediaPlayer(self)
        self.player.setVolume(100)

        # Playback flags
        self._end_consumed = False
        self._manual_advance = False
        self.started = False

        # UI
        self.setWindowTitle("TTS Free (Desktop)")
        self.resize(980, 640)

        self.btn_load = QtWidgets.QPushButton("Load .txt/.docx")
        self.btn_pron = QtWidgets.QPushButton("Pronunciation CSV")
        self.btn_next = QtWidgets.QPushButton("▶ Next"); self.btn_next.setEnabled(False)

        # Voice choices
        self.cbo_engine = QtWidgets.QComboBox()
        items = ["Coqui (VCTK p240 — UK female)"] + list(PIPER_VOICES.keys())
        self.cbo_engine.addItems(items)
        self.cbo_engine.setCurrentIndex(0)

        self.chk_allow_espeak = QtWidgets.QCheckBox("Allow eSpeak fallback (robotic)")
        self.chk_allow_espeak.setChecked(False)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.btn_load)
        top.addWidget(self.btn_pron)
        top.addStretch(1)
        top.addWidget(QtWidgets.QLabel("Voice:"))
        top.addWidget(self.cbo_engine)
        top.addWidget(self.chk_allow_espeak)
        top.addWidget(self.btn_next)
        self.txt_cur = QtWidgets.QPlainTextEdit(readOnly=True)
        self.txt_nxt = QtWidgets.QPlainTextEdit(readOnly=True)
        self.status = QtWidgets.QLabel("Ready")
        self.chk_auto = QtWidgets.QCheckBox("Auto")
        self.chk_auto.setChecked(False)

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(top)
        layout.addWidget(QtWidgets.QLabel("<b>Current:</b>"))
        layout.addWidget(self.txt_cur)
        layout.addWidget(QtWidgets.QLabel("<b>Next:</b>"))
        layout.addWidget(self.txt_nxt)
        layout.addWidget(self.status)

        cw = QtWidgets.QWidget(); cw.setLayout(layout)
        self.setCentralWidget(cw)

        # Menu
        about_act = QtWidgets.QAction("About", self)
        about_act.triggered.connect(lambda: QtWidgets.QMessageBox.about(self, "About / Licenses", LICENSE_TEXT))
        menu = self.menuBar().addMenu("Help"); menu.addAction(about_act)

        # Signals
        self.btn_load.clicked.connect(self._choose_file)
        self.btn_pron.clicked.connect(self._choose_pron)
        self.btn_next.clicked.connect(self.next_or_play)
        QtWidgets.QShortcut(QtGui.QKeySequence("Space"), self, activated=self.next_or_play)

        self.player.mediaStatusChanged.connect(self._on_media_status_changed)

        # Backend is constructed lazily after the file is loaded
        self._backend: Optional[_BaseTTS] = None

    # -------- file handling --------
    def _choose_file(self) -> None:
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open", "", "Text/Docx (*.txt *.docx)")
        if not fn: return
        self.status.setText("Loading...")
        self.btn_next.setEnabled(False)
        self.started = False
        threading.Thread(target=self._prepare, args=(fn,), daemon=True).start()

    def _choose_pron(self) -> None:
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Pronunciation CSV", "", "CSV (*.csv)")
        if not fn: return
        try:
            self.rules = load_pron_csv(fn)
            self.status.setText(f"Loaded {len(self.rules)} pronunciation rules")
        except Exception as e:
            self.status.setText(f"CSV error: {e}")

    def _prepare(self, path: str) -> None:
        try:
            sents = split_sentences(read_text(path))
            if not sents:
                raise RuntimeError("No sentences found")
            sents.insert(0, "(start)")
            self.queue = AudioQueue(items=sents)

            # Choose backend now (based on UI selection)
            prefer = self.cbo_engine.currentText()
            allow_espeak = self.chk_allow_espeak.isChecked()
            
            def try_piper_with_fallback(first_choice: str) -> _BaseTTS:
                # Try selected Piper voice, then the other ones, then Coqui, then eSpeak (if allowed)
                piper_order = [first_choice] + [b for b in PIPER_VOICES.values() if b != first_choice]
                for basename in piper_order:
                    try:
                        return PiperBackend(basename)
                    except Exception as e:
                        log(f"Piper ({basename}) failed: {e}")
                # fall back to Coqui -> eSpeak (optional)
                return choose_backend(allow_espeak, coqui_speaker="p240", piper_model=first_choice)
            
            if prefer.startswith("Coqui"):
                # Prefer Coqui, but if not available (e.g., Python 3.12), fall back to Piper (Cori) -> eSpeak
                self._backend = choose_backend(allow_espeak, coqui_speaker="p240", piper_model="en_GB-cori-high")
            else:
                # A Piper voice was selected; map to its basename and try that first
                basename = PIPER_VOICES.get(prefer, "en_GB-cori-high")
                self._backend = try_piper_with_fallback(basename)

            # Synthesize first two
            self.queue.cur_wav = self._synth(self.queue.items[0])
            if len(self.queue.items) > 1:
                self.queue.next_wav = self._synth(self.queue.items[1])

        except Exception as e:
            QtCore.QMetaObject.invokeMethod(self, "_ui_err", QtCore.Qt.QueuedConnection,
                                            QtCore.Q_ARG(str, f"Load error: {e}"))
            return
        QtCore.QMetaObject.invokeMethod(self, "_ui_ready", QtCore.Qt.QueuedConnection)

    @QtCore.pyqtSlot()
    def _ui_ready(self) -> None:
        self.txt_cur.setPlainText(self.queue.items[0])
        self.txt_nxt.setPlainText(self.queue.items[1] if len(self.queue.items) > 1 else "(end)")
        self.status.setText(f"Backend: {self._backend.name() if self._backend else 'None'}")
        self.btn_next.setEnabled(True)

    @QtCore.pyqtSlot(str)
    def _ui_err(self, msg: str) -> None:
        self.status.setText(msg)

    # -------- playback & progression --------
    def next_or_play(self) -> None:
        if not self.queue.items:
            return
        if not self.started:
            self.started = True
            if self.queue.cur_wav:
                self._play(self.queue.cur_wav)
            return

        if self.player.state() == QMediaPlayer.PlayingState:
            # manual single-step: stop current and advance once
            self._manual_advance = True
            self._end_consumed = True   # suppress auto handler for this clip
            self.player.stop()
            self._advance()
            self._manual_advance = False
        else:
            self._advance()

    def _play(self, wav_path: str) -> None:
        self._end_consumed = False  # arm for a single natural end
        url = QUrl.fromLocalFile(os.path.abspath(wav_path))
        self.player.setMedia(QMediaContent(url))
        self.player.play()

    def _advance(self) -> None:
        if self.queue.idx + 1 >= len(self.queue.items):
            return  # end
        self.queue.idx += 1
        # rotate buffers
        self.queue.cur_wav = self.queue.next_wav
        self.queue.next_wav = None
        # update UI texts
        self.txt_cur.setPlainText(self.queue.items[self.queue.idx])
        nxt = self.queue.items[self.queue.idx + 1] if self.queue.idx + 1 < len(self.queue.items) else "(end)"
        self.txt_nxt.setPlainText(nxt)
        # play new current (if we have it), then preload next
        if self.queue.cur_wav:
            self._play(self.queue.cur_wav)
        threading.Thread(target=self._preload_next_async, daemon=True).start()

    def _preload_next_async(self) -> None:
        nxt_i = self.queue.idx + 1
        if nxt_i < len(self.queue.items):
            try:
                wav = self._synth(self.queue.items[nxt_i])
            except Exception:
                wav = None
            if nxt_i == self.queue.idx + 1:
                self.queue.next_wav = wav

    def _on_media_status_changed(self, status) -> None:
        if status != QMediaPlayer.EndOfMedia:
            return
        # mark that this clip naturally ended
        self._end_consumed = True
    
        # Only auto-advance if Auto is checked, and this wasn't a manual skip
        if getattr(self, "chk_auto", None) and self.chk_auto.isChecked():
            if not self._manual_advance and self.started:
                self._advance()
        # else: do nothing; wait for user to press Next/Space

    def _synth(self, text: str) -> str:
        assert self._backend is not None, "Backend not initialized"
        return self._backend.synth_to_wav(apply_pron(text, self.rules))

def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = Main()
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
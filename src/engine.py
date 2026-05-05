import torch
import librosa
import numpy as np
import torch.nn.functional as F
from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
import gc
import os
import json
import wave
import tempfile
import soundfile as sf
import warnings

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from vosk import Model, KaldiRecognizer
    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

class SpeechEngine:
    def __init__(self, phoneme_model_path="./models/phonoscopic", 
                 use_stt=True,
                 vosk_model_path="./models/vosk"):
        
        # Выбор ускорителя
        if torch.cuda.is_available():
            self.device = torch.device("cuda")
            gpu_name = torch.cuda.get_device_name(0)
            print(f"[SpeechEngine] Обнаружен GPU: {gpu_name}")
        else:
            self.device = torch.device("cpu")
            print(f"[SpeechEngine] GPU не найден, используется CPU")
        
        # Загрузка фонемной модели
        try:
            self.processor = Wav2Vec2Processor.from_pretrained(phoneme_model_path)
            self.model = Wav2Vec2ForCTC.from_pretrained(phoneme_model_path)
        except Exception as e:
            raise RuntimeError(f"Ошибка загрузки Wav2Vec2: {e}")
        
        # Оптимизация для GPU
        if self.device.type == "cuda":
            self.model = self.model.half().to(self.device)
            print("[SpeechEngine] Включен режим оптимизации для GPU")
        else:
            self.model = self.model.to(self.device)

        self.model.eval()
        
        self.stt_model = None
        self.use_stt = use_stt and VOSK_AVAILABLE
        self.vosk_model_path = vosk_model_path

    def _unload_stt_model(self):
        if self.stt_model is not None:
            del self.stt_model
            self.stt_model = None
            gc.collect()
            if self.device.type == "cuda":
                torch.cuda.empty_cache()

    def run_alignment(self, audio_path, progress_callback=None):
        self._unload_stt_model()

        if progress_callback:
            progress_callback("Загрузка аудио...", 5)
            
        y, sr = librosa.load(audio_path, sr=16000)
        duration = len(y) / sr
        
        if duration < 60:
            return self._run_direct_alignment(y, sr, progress_callback)
        else:
            return self._run_chunked_alignment(y, sr, progress_callback)

    def _run_direct_alignment(self, y, sr, progress_callback):
        if progress_callback:
            progress_callback("Нейросетевой анализ...", 20)

        inputs = self.processor(y, sampling_rate=16000, return_tensors="pt")
        input_values = inputs.input_values.to(self.device)
        
        if self.device.type == "cuda":
            input_values = input_values.half()

        with torch.no_grad():
            logits = self.model(input_values).logits[0]
            probs = F.softmax(logits.float(), dim=-1).cpu().numpy()
        
        return self._extract_segments(probs, offset_sec=0)

    def _run_chunked_alignment(self, y, sr, progress_callback):
        chunk_len_sec = 30  
        chunk_samples = chunk_len_sec * sr
        total_chunks = int(np.ceil(len(y) / chunk_samples))
        all_segments = []
        
        for i in range(total_chunks):
            start_s = i * chunk_samples
            end_s = min((i + 1) * chunk_samples, len(y))
            y_chunk = y[start_s:end_s]
            
            offset_sec = i * chunk_len_sec 
            if progress_callback:
                p = 10 + int((i / total_chunks) * 85)
                progress_callback(f"Анализ фрагмента {i+1}/{total_chunks}...", p)

            inputs = self.processor(y_chunk, sampling_rate=16000, return_tensors="pt")
            input_values = inputs.input_values.to(self.device)

            if self.device.type == "cuda":
                input_values = input_values.half()

            with torch.no_grad():
                logits = self.model(input_values).logits[0].detach().cpu()
                probs = F.softmax(logits.float(), dim=-1).numpy()
            
            del input_values
            chunk_segments = self._extract_segments(probs, offset_sec=offset_sec)
            all_segments.extend(chunk_segments)
            if self.device.type == "cuda": 
                torch.cuda.empty_cache()
            gc.collect()
        return all_segments

    def _extract_segments(self, probs, offset_sec):
        time_per_frame = self.model.config.inputs_to_logits_ratio / 16000
        pad_token = self.processor.tokenizer.pad_token_id
        predicted_ids = np.argmax(probs, axis=-1)
        segments = []
        last_label = None
        start_frame = 0
        for j, token_id in enumerate(predicted_ids):
            if token_id != pad_token and token_id != last_label:
                if last_label is not None:
                    label_text = self.processor.decode([last_label])
                    if label_text.strip():
                        segments.append({
                            "label": label_text,
                            "start": round(offset_sec + start_frame * time_per_frame, 3),
                            "end": round(offset_sec + j * time_per_frame, 3)
                        })
                last_label, start_frame = token_id, j
        
        if last_label is not None:
            label_text = self.processor.decode([last_label])
            if label_text.strip():
                segments.append({
                    "label": label_text,
                    "start": round(offset_sec + start_frame * time_per_frame, 3),
                    "end": round(offset_sec + len(predicted_ids) * time_per_frame, 3)
                })

        return segments

    def get_text_transcription(self, audio_path, progress_callback=None):
        if not self.use_stt: return ""
        if self.stt_model is None:
            try:
                self.stt_model = Model(self.vosk_model_path)
            except Exception as e:
                raise RuntimeError("МОДЕЛЬ_ПОВРЕЖДЕНА_VOSK")

        try:
            wav_path = self._convert_to_wav_pcm(audio_path)
            wf = wave.open(wav_path, "rb")
            rec = KaldiRecognizer(self.stt_model, wf.getframerate())
            full_text = []
            total_frames = wf.getnframes()
            frames_processed = 0
            buffer_size = 16000 
            
            while True:
                data = wf.readframes(buffer_size)
                if len(data) == 0: break
                frames_processed += buffer_size
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    if res.get('text'): 
                        full_text.append(res['text'])
                if progress_callback:
                    p = 80 + int((min(frames_processed, total_frames) / total_frames) * 15)
                    progress_callback(f"Распознавание текста...", p)
            
            # Забираем остатки
            final = json.loads(rec.FinalResult())
            if final.get('text'):
                full_text.append(final['text'])
            
            wf.close()
            if os.path.exists(wav_path): os.unlink(wav_path)
            return " ".join(full_text).strip()
        except: return ""

    def _convert_to_wav_pcm(self, audio_path):
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        temp_wav = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        sf.write(temp_wav.name, y, sr, subtype='PCM_16')
        temp_wav.close()
        return temp_wav.name

    def check_audio_quality(self, audio_path):
        try:
            y, sr = librosa.load(audio_path, sr=16000, duration=30)
            if len(y) == 0: return "empty"
            rms = np.mean(librosa.feature.rms(y=y))
            flatness = np.mean(librosa.feature.spectral_flatness(y=y))
            zcr = np.mean(librosa.feature.zero_crossing_rate(y=y))
            if rms < 0.005: return "quiet"
            if zcr > 0.15 or flatness > 0.06: return "noisy"
            return "ok"
        except: return "error"
import io
import time
import random
import requests
import re
from flask import Flask, request, send_file, jsonify, render_template
from flask_cors import CORS
from pydub import AudioSegment
import logging
import urllib.parse

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# ---------- Translation Function ----------
def translate_text(text, target_lang='am', source_lang='en'):
    """
    Translate text using Google Translate (unofficial API).
    Returns translated string or raises exception.
    """
    url = "https://translate.googleapis.com/translate_a/single"
    params = {
        'client': 'gtx',
        'sl': source_lang,
        'tl': target_lang,
        'dt': 't',
        'q': text
    }
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Extract translated text from the nested array
        translated = ''.join([part[0] for part in data[0] if part[0]])
        return translated
    except Exception as e:
        app.logger.error(f"Translation error: {e}")
        raise

# ---------- TTS Functions (unchanged) ----------
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

def split_text_into_chunks(text, max_chars=100):
    # ... (same as before)
    sentence_pattern = r'[^.!?።]+[.!?።]+|\S+$'
    sentences = re.findall(sentence_pattern, text)
    if not sentences:
        sentences = [text]

    chunks = []
    current_chunk = ''

    for sentence in sentences:
        trimmed = sentence.strip()
        if not trimmed:
            continue

        test_chunk = f"{current_chunk} {trimmed}".strip() if current_chunk else trimmed
        if len(test_chunk) <= max_chars:
            current_chunk = test_chunk
        else:
            if current_chunk:
                chunks.append(current_chunk)
            if len(trimmed) > max_chars:
                words = trimmed.split(' ')
                word_chunk = ''
                for word in words:
                    test_word = f"{word_chunk} {word}".strip() if word_chunk else word
                    if len(test_word) <= max_chars:
                        word_chunk = test_word
                    else:
                        if word_chunk:
                            chunks.append(word_chunk)
                        word_chunk = word
                if word_chunk:
                    chunks.append(word_chunk)
                current_chunk = ''
            else:
                current_chunk = trimmed
    if current_chunk:
        chunks.append(current_chunk)

    app.logger.info(f"Split into {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        app.logger.info(f"Chunk {i+1}: {chunk[:50]}...")
    return chunks

def fetch_audio_chunk(text, lang, retries=3):
    # ... (same as before)
    url = "https://translate.google.com/translate_tts"
    params = {'ie': 'UTF-8', 'q': text, 'tl': lang, 'client': 'tw-ob'}
    for attempt in range(retries):
        headers = {'User-Agent': random.choice(USER_AGENTS)}
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                return resp.content
            elif resp.status_code == 429:
                wait = (2 ** attempt) + random.random()
                app.logger.warning(f"Rate limited, waiting {wait:.2f}s")
                time.sleep(wait)
            else:
                resp.raise_for_status()
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1)
    raise Exception("Max retries exceeded")

def generate_speech(text, lang):
    """Internal function to generate combined MP3 from text (any length)."""
    chunks = split_text_into_chunks(text, max_chars=100)
    if not chunks:
        raise ValueError("No valid chunks generated")
    audio_segments = []
    for i, chunk in enumerate(chunks):
        mp3_data = fetch_audio_chunk(chunk, lang)
        seg = AudioSegment.from_mp3(io.BytesIO(mp3_data))
        audio_segments.append(seg)
        if i < len(chunks) - 1:
            time.sleep(1.5)
    combined = audio_segments[0]
    for seg in audio_segments[1:]:
        combined += seg
    return combined

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    """Standard TTS (expects Amharic text)."""
    if request.is_json:
        data = request.get_json()
        text = data.get('text', '')
        lang = data.get('lang', 'am')
    else:
        text = request.form.get('text', '')
        lang = request.form.get('lang', 'am')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        combined_audio = generate_speech(text, lang)
        buf = io.BytesIO()
        combined_audio.export(buf, format='mp3')
        buf.seek(0)
        return send_file(buf, mimetype='audio/mpeg', as_attachment=False, download_name='speech.mp3')
    except Exception as e:
        app.logger.error(f"TTS error: {e}")
        return jsonify({'error': f'TTS failed: {str(e)}'}), 500

@app.route('/api/translate', methods=['POST'])
def translate():
    """Translate English text to Amharic."""
    if request.is_json:
        data = request.get_json()
        text = data.get('text', '')
        target_lang = data.get('target_lang', 'am')
        source_lang = data.get('source_lang', 'en')
    else:
        text = request.form.get('text', '')
        target_lang = request.form.get('target_lang', 'am')
        source_lang = request.form.get('source_lang', 'en')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        translated = translate_text(text, target_lang, source_lang)
        return jsonify({
            'original': text,
            'translated': translated,
            'source_lang': source_lang,
            'target_lang': target_lang
        })
    except Exception as e:
        app.logger.error(f"Translation error: {e}")
        return jsonify({'error': f'Translation failed: {str(e)}'}), 500

@app.route('/api/translate_tts', methods=['POST'])
def translate_and_speak():
    """Translate English to Amharic, then generate speech."""
    if request.is_json:
        data = request.get_json()
        text = data.get('text', '')
        # Optionally allow overriding target language (default Amharic)
        target_lang = data.get('target_lang', 'am')
        source_lang = data.get('source_lang', 'en')
    else:
        text = request.form.get('text', '')
        target_lang = request.form.get('target_lang', 'am')
        source_lang = request.form.get('source_lang', 'en')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    try:
        # Step 1: Translate
        translated = translate_text(text, target_lang, source_lang)
        # Step 2: Generate speech from translated text
        combined_audio = generate_speech(translated, target_lang)
        buf = io.BytesIO()
        combined_audio.export(buf, format='mp3')
        buf.seek(0)
        return send_file(buf, mimetype='audio/mpeg', as_attachment=False, download_name='translated_speech.mp3')
    except Exception as e:
        app.logger.error(f"Translate+TTS error: {e}")
        return jsonify({'error': f'Translate+TTS failed: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)

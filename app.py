import io
import time
import random
import requests
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from pydub import AudioSegment
import logging

app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)

# User-Agent rotation to reduce blocking
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
]

def split_text_into_chunks(text, max_chars=100):
    """Split text into chunks ≤ max_chars, respecting sentences and words."""
    # Include Amharic full stop (።) in sentence splitting
    sentence_regex = /[^.!?።]+[.!?።]+|\S+$/g
    sentences = text.match(sentence_regex) || [text]
    
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
            # Split long sentence by words
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
    return chunks

def fetch_audio_chunk(text, lang, retries=3):
    """Fetch MP3 for a single chunk with retry logic."""
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

@app.route('/api/tts', methods=['POST'])
def text_to_speech():
    # Get parameters
    if request.is_json:
        data = request.get_json()
        text = data.get('text', '')
        lang = data.get('lang', 'am')
    else:
        text = request.form.get('text', '')
        lang = request.form.get('lang', 'am')

    if not text:
        return jsonify({'error': 'No text provided'}), 400

    # Split into chunks
    chunks = split_text_into_chunks(text, max_chars=100)
    app.logger.info(f"Split into {len(chunks)} chunks")

    if not chunks:
        return jsonify({'error': 'No valid chunks generated'}), 500

    # Fetch audio for each chunk
    audio_segments = []
    for i, chunk in enumerate(chunks):
        app.logger.info(f"Fetching chunk {i+1}/{len(chunks)}: {chunk[:50]}...")
        try:
            mp3_data = fetch_audio_chunk(chunk, lang)
            # Load into pydub segment (from bytes)
            seg = AudioSegment.from_mp3(io.BytesIO(mp3_data))
            audio_segments.append(seg)
        except Exception as e:
            app.logger.error(f"Failed to fetch chunk {i}: {e}")
            return jsonify({'error': f'Failed to generate speech for part {i+1}'}), 500
        # Small delay between requests to avoid rate limiting
        if i < len(chunks) - 1:
            time.sleep(1.5)

    # Combine all segments
    if not audio_segments:
        return jsonify({'error': 'No audio generated'}), 500

    combined = audio_segments[0]
    for seg in audio_segments[1:]:
        combined += seg

    # Export combined audio to bytes
    buf = io.BytesIO()
    combined.export(buf, format='mp3')
    buf.seek(0)

    return send_file(
        buf,
        mimetype='audio/mpeg',
        as_attachment=False,
        download_name='speech.mp3'
    )

if __name__ == '__main__':
    app.run(debug=True)

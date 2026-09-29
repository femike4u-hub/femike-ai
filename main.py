import os
import subprocess
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import requests

app = FastAPI(title="femike AI Engine")

# Enable CORS so the web app can talk to the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "/tmp/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def read_root():
    return {"status": "femike AI backend operational", "ffmpeg": "enabled"}

@app.post("/api/process-link")
def process_link(url: str = Form(...)):
    ydl_opts = {
        'format': 'best',
        'outtmpl': f'{UPLOAD_DIR}/%(id)s.%(ext)s',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            return {"status": "success", "file_path": filename, "title": info.get('title')}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/transcribe")
async def transcribe_media(file: UploadFile = File(...)):
    deepgram_key = os.getenv("DEEPGRAM_API_KEY")
    if not deepgram_key:
        raise HTTPException(status_code=500, detail="DEEPGRAM_API_KEY environment variable missing")

    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        f.write(await file.read())
    
    audio_path = os.path.join(UPLOAD_DIR, f"{file.filename}.mp3")
    ffmpeg_cmd = ["ffmpeg", "-y", "-i", file_location, "-vn", "-ar", "16000", "-ac", "1", "-b:a", "96k", audio_path]
    subprocess.run(ffmpeg_cmd, check=True)

    headers = {
        "Authorization": f"Token {deepgram_key}",
        "Content-Type": "audio/mp3"
    }
    url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true"
    
    with open(audio_path, "rb") as audio_file:
        response = requests.post(url, headers=headers, data=audio_file)
    
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {response.text}")

    dg_data = response.json()
    words = dg_data['results']['channels'][0]['alternatives'][0]['words']
    transcript_text = dg_data['results']['channels'][0]['alternatives'][0]['transcript']

    return {
        "status": "completed",
        "transcript": transcript_text,
        "words": words
    }

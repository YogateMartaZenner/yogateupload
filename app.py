import streamlit as st
from moviepy.editor import VideoFileClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from oauth2client.tools import run_flow
from feedgen.feed import FeedGenerator
import os
import json
import pytz
from datetime import datetime

# ======================
# CREAR archivos JSON desde variables de entorno
# ======================
yt_json_str = os.getenv("YOUTUBE_JSON")
if not yt_json_str:
    st.error("Variable de entorno YOUTUBE_JSON no encontrada")
    st.stop()
with open("client_secret.json", "w") as f:
    f.write(yt_json_str)

drive_json_str = os.getenv("DRIVE_JSON")
if not drive_json_str:
    st.error("Variable de entorno DRIVE_JSON no encontrada")
    st.stop()
with open("client_secret_drive.json", "w") as f:
    f.write(drive_json_str)

# ======================
# CONFIGURACIÓN APIs
# ======================
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def get_drive_service():
    flow = flow_from_clientsecrets("client_secret_drive.json", DRIVE_SCOPES)
    storage = Storage("drive_credentials.json")
    creds = storage.get()
    if not creds or creds.invalid:
        creds = run_flow(flow, storage)
    return build("drive", "v3", credentials=creds)

def upload_to_drive(filepath):
    service = get_drive_service()
    metadata = {"name": os.path.basename(filepath)}
    media = MediaFileUpload(filepath, mimetype="audio/mpeg", resumable=True)
    file = service.files().create(body=metadata, media_body=media, fields="id, webViewLink, webContentLink").execute()
    file_id = file["id"]
    # Poner permisos públicos
    service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
    # Generar enlace de descarga directa
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def get_youtube_service():
    flow = flow_from_clientsecrets("client_secret.json", YT_SCOPES)
    storage = Storage("yt_credentials.json")
    creds = storage.get()
    if not creds or creds.invalid:
        creds = run_flow(flow, storage)
    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(video_path, title, description, schedule_time=None):
    youtube = get_youtube_service()
    body = {
        "snippet": {"title": title, "description": description},
        "status": {"privacyStatus": "private" if schedule_time else "public"},
    }
    if schedule_time:
        body["status"]["publishAt"] = schedule_time.isoformat()
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(video_path)
    )
    return request.execute()

# ======================
# STREAMLIT APP
# ======================
st.title("📢 Publicador Automático a YouTube + iVoox + Spotify")

video = st.file_uploader("🎥 Sube tu vídeo", type=["mp4", "mov"])
title = st.text_input("📝 Título")
description = st.text_area("📄 Descripción")
programar = st.checkbox("Programar publicación en YouTube")
schedule_time_utc = None
if programar:
    schedule_time_local = st.datetime_input("📅 Fecha y hora de publicación (hora española)")
    
    # Convertir a UTC automáticamente considerando CET/CEST
    tz = pytz.timezone("Europe/Madrid")
    schedule_time_localized = tz.localize(schedule_time_local)
    schedule_time_utc = schedule_time_localized.astimezone(pytz.utc)

if st.button("🚀 Publicar en todas las plataformas"):
    if not video or not title:
        st.error("Por favor, sube un vídeo y escribe un título.")
    else:
        with open("temp_video.mp4", "wb") as f:
            f.write(video.getbuffer())

        st.info("🎧 Extrayendo audio...")
        clip = VideoFileClip("temp_video.mp4")
        audio_path = "episode.mp3"
        clip.audio.write_audiofile(audio_path)
        clip.close()

        st.info("📤 Subiendo vídeo a YouTube...")
        yt_resp = upload_to_youtube("temp_video.mp4", title, description, schedule_time_utc)
        st.success(f"✅ Subido a YouTube: https://youtu.be/{yt_resp.get('id')}")

        st.info("☁️ Subiendo audio a Google Drive...")
        audio_url = upload_to_drive(audio_path)
        st.success(f"✅ Audio disponible en Drive: {audio_url}")

        st.info("🪶 Generando feed RSS...")
        fg = FeedGenerator()
        fg.load_extension("podcast")
        fg.title("Mi Podcast Automatizado")
        fg.link(href="https://tusitio.com/feed.xml", rel="self")
        fg.description("Podcast generado automáticamente desde Streamlit")
        fg.language("es")

        entry = fg.add_entry()
        entry.id(audio_url)
        entry.title(title)
        entry.description(description)
        entry.enclosure(audio_url, 0, "audio/mpeg")

        fg.rss_file("feed.xml")
        st.success("📰 RSS generado correctamente (feed.xml)")

        st.info("🛡️ Modo seguro activado: los archivos MP3 permanecen en Google Drive.")
        st.balloons()

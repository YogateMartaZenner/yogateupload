import streamlit as st
from moviepy.editor import VideoFileClip
import os
import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from oauth2client.tools import run_flow
from feedgen.feed import FeedGenerator
from datetime import datetime, timezone

# ---------------- Interfaz ----------------
st.title("📺🎙️ Subida automática a YouTube, iVoox y Spotify")

uploaded_file = st.file_uploader("🎥 Sube tu video", type=["mp4", "mov", "avi"])
title = st.text_input("Título del contenido")
description = st.text_area("Descripción del contenido")

# Programación de publicación en YouTube
schedule = st.checkbox("¿Programar publicación en YouTube?")
publish_time = None
if schedule:
    publish_time = st.datetime_input("Fecha y hora de publicación", datetime.now())

ivoox_token = st.text_input("🔑 Token iVoox", type="password")  # Token API de iVoox

if uploaded_file and st.button("🚀 Subir a todas las plataformas"):

    try:
        # --- Guardar video temporal ---
        video_path = f"temp_{uploaded_file.name}"
        with open(video_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.progress(10)
        st.info("✅ Video guardado temporalmente.")

        # --- Extraer audio ---
        st.info("🎵 Extrayendo audio...")
        clip = VideoFileClip(video_path)
        audio_path = video_path.split('.')[0] + ".mp3"
        clip.audio.write_audiofile(audio_path)
        st.success("🎵 Audio extraído correctamente.")
        st.progress(30)

        # --- Subida a YouTube ---
        st.info("📺 Subiendo a YouTube...")
        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        flow = flow_from_clientsecrets("client_secret.json", scope=SCOPES)
        storage = Storage("credentials.json")
        creds = storage.get()
        if not creds or creds.invalid:
            creds = run_flow(flow, storage)

        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {
                "privacyStatus": "private" if schedule else "public",
            }
        }

        # Programación si el usuario lo activó
        if schedule and publish_time:
            publish_time_utc = publish_time.astimezone(timezone.utc).isoformat()
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = publish_time_utc

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=MediaFileUpload(video_path)
        )
        response_youtube = request.execute()
        st.success(f"📺 Video subido a YouTube correctamente. ID: {response_youtube['id']}")
        st.progress(60)

        # --- Subida a iVoox ---
        st.info("🎙️ Subiendo audio a iVoox...")
        url_ivoox = "https://api.ivoox.com/1.0/upload/audio"
        files = {'file': open(audio_path, 'rb')}
        data = {'title': title, 'description': description, 'token': ivoox_token}
        response_ivoox = requests.post(url_ivoox, files=files, data=data)

        if response_ivoox.status_code == 200:
            audio_url = response_ivoox.json().get("url")
            st.success("🎙️ Audio subido a iVoox correctamente")
        else:
            st.error(f"❌ Error subiendo a iVoox: {response_ivoox.text}")
            audio_url = None
        st.progress(80)

        # --- Generar feed RSS para Spotify ---
        if audio_url:
            st.info("🔗 Generando feed RSS para Spotify...")
            fg = FeedGenerator()
            fg.title("Mi Podcast")
            fg.description("Podcast publicado automáticamente desde mi app")
            fg.link(href="https://tusitio.com/feed")
            fg.language("es")

            fe = fg.add_entry()
            fe.title(title)
            fe.description(description)
            fe.enclosure(audio_url, 0, "audio/mpeg")

            rss_file = f"{title.replace(' ','_')}.xml"
            fg.rss_file(rss_file)
            st.success(f"🔗 Feed RSS generado: {rss_file} (añádelo en Spotify for Podcasters)")
        st.progress(100)

    finally:
        # --- Limpiar archivos temporales ---
        if os.path.exists(video_path):
            os.remove(video_path)
        if os.path.exists(audio_path):
            os.remove(audio_path)
        st.info("🧹 Archivos temporales eliminados.")

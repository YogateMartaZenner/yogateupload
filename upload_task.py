import os
import json
from datetime import datetime
from moviepy.editor import VideoFileClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from feedgen.feed import FeedGenerator

# ============
# CONFIGURACIÓN
# ============
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Cargar credenciales desde variables de entorno (como en tu app)
yt_json_str = os.getenv("YOUTUBE_JSON")
drive_json_str = os.getenv("DRIVE_JSON")

with open("client_secret.json", "w") as f:
    f.write(yt_json_str)
with open("client_secret_drive.json", "w") as f:
    f.write(drive_json_str)

def get_drive_service():
    flow = flow_from_clientsecrets("client_secret_drive.json", DRIVE_SCOPES)
    storage = Storage("drive_credentials.json")
    creds = storage.get()
    if not creds or creds.invalid:
        raise RuntimeError("Credenciales de Drive inválidas")
    return build("drive", "v3", credentials=creds)

def upload_or_update_file(filepath, file_id=None):
    service = get_drive_service()
    folder_name = "Podcast"
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces='drive',
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    folder_id = items[0]['id'] if items else service.files().create(
        body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}, fields='id'
    ).execute()['id']

    media = MediaFileUpload(filepath, resumable=True)
    if file_id:
        file = service.files().update(fileId=file_id, media_body=media).execute()
    else:
        file_metadata = {"name": os.path.basename(filepath), "parents": [folder_id]}
        file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = file["id"]
        service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
    return f"https://drive.google.com/uc?export=download&id={file_id}", file_id

# ============
# PROCESAR SIGUIENTE TAREA
# ============
if not os.path.exists("schedule.json"):
    print("❌ No existe el archivo schedule.json")
    exit(0)

with open("schedule.json") as f:
    plan = json.load(f)

pendiente = None
for tarea in plan:
    fecha = datetime.fromisoformat(tarea["scheduled_date"])
    if not tarea["uploaded"] and datetime.now() >= fecha:
        pendiente = tarea
        break

if not pendiente:
    print("🕒 No hay publicaciones pendientes por fecha.")
    exit(0)

print(f"📤 Procesando tarea: {pendiente['name']}")

# Descargar vídeo desde Drive
service = get_drive_service()
request = service.files().get_media(fileId=pendiente["file_id"])
with open("temp_video.mp4", "wb") as f:
    downloader = service._http.request(request.uri)
    f.write(downloader[1])

# Extraer audio
clip = VideoFileClip("temp_video.mp4")
clip.audio.write_audiofile("episode.mp3")
clip.close()

# Subir audio a Drive
audio_url, _ = upload_or_update_file("episode.mp3")

# Actualizar feed RSS
fg = FeedGenerator()
fg.load_extension("podcast")
fg.title("Mi Podcast Automatizado")
fg.link(href="https://tusitio.com/feed.xml", rel="self")
fg.description("Podcast generado automáticamente desde GitHub Actions")
fg.language("es")

entry = fg.add_entry()
entry.id(audio_url)
entry.title(pendiente["name"])
entry.enclosure(audio_url, 0, "audio/mpeg")
fg.rss_file("feed.xml")

feed_url, _ = upload_or_update_file("feed.xml")

# Marcar como completado
pendiente["uploaded"] = True
with open("schedule.json", "w") as f:
    json.dump(plan, f, indent=2)

print(f"✅ Publicación completada y feed actualizado: {feed_url}")

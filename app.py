import os
import json
import streamlit as st
from datetime import datetime, timedelta
import pytz
from moviepy.editor import VideoFileClip
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.file import Storage
from oauth2client.client import flow_from_clientsecrets
from feedgen.feed import FeedGenerator
import tempfile
import shutil

# ============
# CONFIGURACIÓN
# ============
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file", "https://www.googleapis.com/auth/drive"]
YT_SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.readonly"]

# Configuración de Streamlit
st.set_page_config(
    page_title="YogaTe Upload - Gestor de Podcast",
    page_icon="🧘",
    layout="wide"
)

# Zona horaria española
SPAIN_TZ = pytz.timezone('Europe/Madrid')

# Verificar que los archivos de credenciales existan
def verificar_credenciales():
    """Verifica que los archivos de credenciales existan"""
    if not os.path.exists("client_secret_drive.json"):
        st.error("❌ No se encontró el archivo client_secret_drive.json")
        st.info("Por favor, coloca el archivo client_secret_drive.json en el directorio raíz de la aplicación")
        return False
    
    if not os.path.exists("client_secret_youtube.json"):
        st.error("❌ No se encontró el archivo client_secret_youtube.json")
        st.info("Por favor, coloca el archivo client_secret_youtube.json en el directorio raíz de la aplicación")
        return False
    
    return True

def authenticate_google_service(service_name, credentials_file, scopes, storage_file):
    """Función genérica para autenticar servicios de Google"""
    try:
        # Configurar el flujo OAuth2 con redirect_uri
        flow = flow_from_clientsecrets(
            credentials_file, 
            scopes,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'  # Para aplicaciones de escritorio
        )
        storage = Storage(storage_file)
        creds = storage.get()
        
        if not creds or creds.invalid:
            # Crear clave única para el estado de autenticación
            auth_key = f"auth_{service_name.lower().replace(' ', '_')}"
            
            if auth_key not in st.session_state:
                st.session_state[auth_key] = False
            
            if not st.session_state[auth_key]:
                # Mostrar instrucciones de autenticación
                st.warning(f"🔐 Autenticación requerida para {service_name}")
                
                auth_uri = flow.step1_get_authorize_url()
                
                st.markdown("### Pasos para autenticarse:")
                st.markdown("1. Haz clic en el enlace de abajo")
                st.markdown("2. Inicia sesión con tu cuenta de Google")
                st.markdown("3. Autoriza la aplicación")
                st.markdown("4. Copia el código de autorización que aparece en la pantalla")
                
                st.markdown(f"**[🔗 Autenticar con {service_name}]({auth_uri})**")
                
                st.info("💡 **Importante:** Después de autorizar, Google te mostrará un código. Cópialo y pégalo abajo.")
                
                auth_code = st.text_input(
                    f"Código de autorización para {service_name}:",
                    placeholder="Pega aquí el código que te muestra Google",
                    key=f"auth_code_{service_name.lower().replace(' ', '_')}"
                )
                
                if auth_code:
                    try:
                        creds = flow.step2_exchange(auth_code)
                        storage.put(creds)
                        st.session_state[auth_key] = True
                        st.success(f"✅ Autenticación con {service_name} completada")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en la autenticación: {str(e)}")
                        return None
                else:
                    return None
            else:
                # Re-autenticar si las credenciales son inválidas
                creds = storage.get()
                if not creds or creds.invalid:
                    st.session_state[auth_key] = False
                    st.rerun()
        
        return creds
    except Exception as e:
        st.error(f"Error al autenticar {service_name}: {str(e)}")
        return None

def get_drive_service():
    """Obtiene el servicio de Google Drive usando credenciales locales"""
    creds = authenticate_google_service(
        "Google Drive", 
        "client_secret_drive.json", 
        DRIVE_SCOPES, 
        "drive_credentials.json"
    )
    if creds:
        return build("drive", "v3", credentials=creds)
    return None

def get_youtube_service():
    """Obtiene el servicio de YouTube usando credenciales locales"""
    creds = authenticate_google_service(
        "YouTube", 
        "client_secret_youtube.json", 
        YT_SCOPES, 
        "youtube_credentials.json"
    )
    if creds:
        return build("youtube", "v3", credentials=creds)
    return None

def upload_to_drive(filepath, folder_name="Podcast"):
    """Sube un archivo a Google Drive en la carpeta especificada"""
    service = get_drive_service()
    if not service:
        return None, None
    
    # Buscar o crear carpeta
    results = service.files().list(
        q=f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false",
        spaces='drive',
        fields="files(id, name)"
    ).execute()
    items = results.get('files', [])
    
    if items:
        folder_id = items[0]['id']
    else:
        folder = service.files().create(
            body={'name': folder_name, 'mimeType': 'application/vnd.google-apps.folder'}, 
            fields='id'
        ).execute()
        folder_id = folder['id']
    
    # Subir archivo
    media = MediaFileUpload(filepath, resumable=True)
    file_metadata = {"name": os.path.basename(filepath), "parents": [folder_id]}
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file["id"]
    
    # Hacer público
    service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()
    
    return f"https://drive.google.com/uc?export=download&id={file_id}", file_id

def upload_to_youtube(video_path, title, description, tags, privacy_status="private", scheduled_time=None):
    """Sube un video a YouTube"""
    service = get_youtube_service()
    if not service:
        return None
    
    # Preparar metadata del video
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': '22'  # People & Blogs
        },
        'status': {
            'privacyStatus': privacy_status
        }
    }
    
    # Si hay fecha programada, configurarla
    if scheduled_time and privacy_status == "private":
        body['status']['publishAt'] = scheduled_time.isoformat() + 'Z'
    
    # Subir video
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    insert_request = service.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = insert_request.next_chunk()
        if status:
            st.progress(status.progress())
    
    return response['id']

def extract_audio_from_video(video_path, output_path):
    """Extrae audio de un video"""
    try:
        clip = VideoFileClip(video_path)
        clip.audio.write_audiofile(output_path, verbose=False, logger=None)
        clip.close()
        return True
    except Exception as e:
        st.error(f"Error al extraer audio: {str(e)}")
        return False

def create_rss_feed(episodes, feed_url):
    """Crea o actualiza el feed RSS"""
    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title("YogaTe Podcast")
    fg.link(href=feed_url, rel="self")
    fg.description("Podcast de YogaTe - Episodios de yoga y bienestar")
    fg.language("es")
    fg.podcast.itunes_category("Health & Fitness", "Fitness")
    
    for episode in episodes:
        entry = fg.add_entry()
        entry.id(episode['audio_url'])
        entry.title(episode['title'])
        entry.description(episode['description'])
        entry.enclosure(episode['audio_url'], 0, "audio/mpeg")
        entry.pubDate(episode['pub_date'])
    
    fg.rss_file("feed.xml")
    return "feed.xml"

def get_youtube_videos():
    """Obtiene la lista de videos del canal de YouTube"""
    service = get_youtube_service()
    if not service:
        return []
    
    try:
        # Obtener canal del usuario autenticado
        channels_response = service.channels().list(part="contentDetails", mine=True).execute()
        if not channels_response['items']:
            st.error("No se encontró canal de YouTube")
            return []
        
        channel_id = channels_response['items'][0]['id']
        uploads_playlist_id = channels_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        # Obtener videos de la playlist de uploads
        videos = []
        next_page_token = None
        
        while True:
            playlist_response = service.playlistItems().list(
                part="snippet",
                playlistId=uploads_playlist_id,
                maxResults=50,
                pageToken=next_page_token
            ).execute()
            
            for item in playlist_response['items']:
                video_id = item['snippet']['resourceId']['videoId']
                video_details = service.videos().list(
                    part="snippet,statistics",
                    id=video_id
                ).execute()
                
                if video_details['items']:
                    video = video_details['items'][0]
                    videos.append({
                        'id': video_id,
                        'title': video['snippet']['title'],
                        'description': video['snippet']['description'],
                        'published_at': video['snippet']['publishedAt'],
                        'view_count': video['statistics'].get('viewCount', 0),
                        'url': f"https://www.youtube.com/watch?v={video_id}"
                    })
            
            next_page_token = playlist_response.get('nextPageToken')
            if not next_page_token:
                break
        
        return videos
    except Exception as e:
        st.error(f"Error al obtener videos de YouTube: {str(e)}")
        return []

def cargar_tareas_automaticas():
    """Carga las tareas automáticas desde el archivo JSON"""
    if not os.path.exists("tareas_automaticas.json"):
        return []
    
    try:
        with open("tareas_automaticas.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error al cargar tareas automáticas: {str(e)}")
        return []

def guardar_tareas_automaticas(tareas):
    """Guarda las tareas automáticas en el archivo JSON"""
    try:
        with open("tareas_automaticas.json", "w", encoding="utf-8") as f:
            json.dump(tareas, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        st.error(f"Error al guardar tareas automáticas: {str(e)}")
        return False

# ============
# PESTAÑA 1: SUBIR VIDEO Y CREAR PODCAST
# ============

def pestaña_subir_video():
    st.header("📹 Subir Video a YouTube y Crear Podcast")
    
    # Formulario de subida
    with st.form("form_subir_video"):
        st.subheader("Seleccionar Video")
        uploaded_file = st.file_uploader(
            "Selecciona un archivo de video",
            type=['mp4', 'avi', 'mov', 'mkv'],
            help="Formatos soportados: MP4, AVI, MOV, MKV"
        )
        
        st.subheader("Información del Video")
        col1, col2 = st.columns(2)
        
        with col1:
            titulo = st.text_input("Título del video", placeholder="Ej: Clase de Yoga Matutina")
            descripcion = st.text_area("Descripción", placeholder="Describe el contenido del video...")
        
        with col2:
            tags_input = st.text_input("Tags (separados por comas)", placeholder="yoga, meditación, bienestar")
            privacidad_opciones = ["privado", "oculto", "público"]
            privacidad_display = st.selectbox("Privacidad", privacidad_opciones)
            
            # Mapear opciones en español a valores de la API
            privacidad_map = {
                "privado": "private",
                "oculto": "unlisted", 
                "público": "public"
            }
            privacidad = privacidad_map[privacidad_display]
        
        st.subheader("Programación")
        programar = st.checkbox("Programar publicación")
        
        if programar:
            col1, col2 = st.columns(2)
            with col1:
                fecha = st.date_input("Fecha de publicación", value=datetime.now().date())
            with col2:
                hora = st.time_input("Hora de publicación", value=datetime.now().time())
        
        subir = st.form_submit_button("🚀 Subir Video y Crear Podcast", type="primary")
    
    if subir and uploaded_file:
        if not titulo or not descripcion:
            st.error("Por favor, completa el título y la descripción")
            return
        
        # Procesar tags
        tags = [tag.strip() for tag in tags_input.split(',') if tag.strip()] if tags_input else []
        
        # Calcular fecha de publicación si está programada
        scheduled_time = None
        if programar and privacidad == "private":  # Solo se puede programar videos privados
            scheduled_time = SPAIN_TZ.localize(datetime.combine(fecha, hora))
        elif programar and privacidad != "private":
            st.warning("⚠️ Solo se pueden programar videos privados. Cambia la privacidad a 'privado' para programar.")
        
        # Guardar archivo temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_path = tmp_file.name
        
        try:
            # Subir a YouTube
            with st.spinner("Subiendo video a YouTube..."):
                video_id = upload_to_youtube(tmp_path, titulo, descripcion, tags, privacidad, scheduled_time)
            
            if video_id:
                st.success(f"✅ Video subido a YouTube: https://www.youtube.com/watch?v={video_id}")

# Extraer audio
                with st.spinner("Extrayendo audio del video..."):
                    audio_path = tempfile.mktemp(suffix='.mp3')
                    if extract_audio_from_video(tmp_path, audio_path):

# Subir audio a Drive
                        with st.spinner("Subiendo audio a Google Drive..."):
                            audio_url, audio_file_id = upload_to_drive(audio_path, "Podcast")
                        
                        if audio_url:
                            # Crear/actualizar feed RSS
                            with st.spinner("Creando feed RSS..."):
                                # Cargar episodios existentes
                                episodios = []
                                if os.path.exists("episodios.json"):
                                    with open("episodios.json", "r", encoding="utf-8") as f:
                                        episodios = json.load(f)
                                
                                # Agregar nuevo episodio
                                nuevo_episodio = {
                                    'title': titulo,
                                    'description': descripcion,
                                    'audio_url': audio_url,
                                    'pub_date': datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000'),
                                    'youtube_id': video_id
                                }
                                episodios.append(nuevo_episodio)
                                
                                # Guardar episodios
                                with open("episodios.json", "w", encoding="utf-8") as f:
                                    json.dump(episodios, f, indent=2, ensure_ascii=False)
                                
                                # Crear feed RSS
                                feed_file = create_rss_feed(episodios, audio_url)
                                
                                # Subir feed a Drive
                                feed_url, feed_file_id = upload_to_drive(feed_file, "Podcast")
                            
                            if feed_url:
                                st.success("✅ Podcast creado exitosamente!")
                                
                                # Mostrar URLs importantes
                                st.subheader("🔗 Enlaces Importantes")
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.info(f"**Feed RSS:**\n{feed_url}")
                                    st.code(feed_url, language=None)
                                
                                with col2:
                                    st.info(f"**Video YouTube:**\nhttps://www.youtube.com/watch?v={video_id}")
                                    st.code(f"https://www.youtube.com/watch?v={video_id}", language=None)
                                
                                st.success("📋 Copia la URL del feed RSS y pégala en Spotify e Ivoox para sincronizar tu podcast")
                            else:
                                st.error("Error al crear el feed RSS")
                        else:
                            st.error("Error al subir el audio a Google Drive")
                    else:
                        st.error("Error al extraer el audio del video")
            else:
                st.error("Error al subir el video a YouTube")
        
        finally:
            # Limpiar archivos temporales
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            if 'audio_path' in locals() and os.path.exists(audio_path):
                os.remove(audio_path)

# ============
# PESTAÑA 2: GESTIÓN AUTOMÁTICA DE VIDEOS
# ============

def pestaña_gestion_automatica():
    st.header("🤖 Gestión Automática de Videos")
    
    # Obtener videos de YouTube
    if st.button("🔄 Actualizar Lista de Videos"):
        with st.spinner("Obteniendo videos de YouTube..."):
            videos = get_youtube_videos()
            st.session_state.youtube_videos = videos
    
    if 'youtube_videos' not in st.session_state:
        st.info("Haz clic en 'Actualizar Lista de Videos' para cargar tus videos de YouTube")
        return
    
    videos = st.session_state.youtube_videos
    
    if not videos:
        st.warning("No se encontraron videos en tu canal de YouTube")
        return
    
    st.subheader(f"📺 Videos Encontrados ({len(videos)})")
    
    # Cargar tareas automáticas existentes
    tareas_automaticas = cargar_tareas_automaticas()
    video_ids_programados = {tarea['video_id'] for tarea in tareas_automaticas}
    
    # Mostrar videos con opción de selección
    videos_seleccionados = []
    
    for i, video in enumerate(videos):
        col1, col2, col3, col4 = st.columns([1, 4, 2, 1])
        
        with col1:
            if video['id'] not in video_ids_programados:
                seleccionado = st.checkbox("", key=f"select_{i}")
                if seleccionado:
                    videos_seleccionados.append(video)
            else:
                st.success("✅")
        
        with col2:
            st.write(f"**{video['title']}**")
            st.caption(f"Publicado: {video['published_at'][:10]}")
            st.caption(f"Vistas: {video['view_count']}")
        
        with col3:
            if video['id'] in video_ids_programados:
                st.info("Ya programado")
            else:
                st.write("Disponible")
        
        with col4:
            if st.button("Ver", key=f"view_{i}"):
                st.write(f"[Ver en YouTube]({video['url']})")
        
        st.markdown("---")
    
    # Formulario para programar tareas
    if videos_seleccionados:
        st.subheader("📅 Programar Tareas Automáticas")
        
        with st.form("form_programar_tareas"):
            st.write(f"**Videos seleccionados:** {len(videos_seleccionados)}")
            
            col1, col2 = st.columns(2)
            with col1:
                intervalo_horas = st.number_input("Intervalo entre tareas (horas)", min_value=1, value=48, help="Tiempo entre cada procesamiento de audio")
            with col2:
                fecha_inicio = st.date_input("Fecha de inicio", value=datetime.now().date())
            
            programar = st.form_submit_button("🚀 Programar Tareas Automáticas", type="primary")
        
        if programar:
            # Crear tareas para cada video seleccionado
            nuevas_tareas = []
            fecha_actual = datetime.combine(fecha_inicio, datetime.min.time())
            
            for i, video in enumerate(videos_seleccionados):
                tarea = {
                    'video_id': video['id'],
                    'title': video['title'],
                    'description': video['description'],
                    'youtube_url': video['url'],
                    'scheduled_date': (fecha_actual + timedelta(hours=i * intervalo_horas)).isoformat(),
                    'intervalo_horas': intervalo_horas,
                    'processed': False,
                    'created_at': datetime.now().isoformat()
                }
                nuevas_tareas.append(tarea)
            
            # Agregar a las tareas existentes
            tareas_automaticas.extend(nuevas_tareas)
            
            if guardar_tareas_automaticas(tareas_automaticas):
                st.success(f"✅ {len(nuevas_tareas)} tareas programadas exitosamente!")
                st.info(f"Las tareas se ejecutarán cada {intervalo_horas} horas a partir del {fecha_inicio}")
            else:
                st.error("Error al guardar las tareas")
    
    # Mostrar tareas programadas
    if tareas_automaticas:
        st.subheader("📋 Tareas Programadas")
        
        for i, tarea in enumerate(tareas_automaticas):
            fecha = datetime.fromisoformat(tarea['scheduled_date'])
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            
            with col1:
                st.write(f"**{tarea['title']}**")
            
            with col2:
                st.write(fecha.strftime("%d/%m/%Y %H:%M"))
            
            with col3:
                if tarea['processed']:
                    st.success("✅ Procesado")
                else:
                    st.warning("⏳ Pendiente")
            
            with col4:
                if not tarea['processed'] and datetime.now() >= fecha:
                    if st.button("Procesar", key=f"process_{i}"):
                        procesar_tarea_automatica(tarea, i)
        
        # Botón para procesar todas las tareas pendientes
        tareas_pendientes = [t for t in tareas_automaticas if not t['processed'] and datetime.now() >= datetime.fromisoformat(t['scheduled_date'])]
        
        if tareas_pendientes:
            st.markdown("---")
            if st.button("🚀 Procesar Todas las Tareas Pendientes", type="primary"):
                progress_bar = st.progress(0)
                for i, tarea in enumerate(tareas_pendientes):
                    idx = tareas_automaticas.index(tarea)
                    st.write(f"Procesando: {tarea['title']}")
                    if procesar_tarea_automatica(tarea, idx):
                        progress_bar.progress((i + 1) / len(tareas_pendientes))
                
                st.success("¡Todas las tareas han sido procesadas!")

def procesar_tarea_automatica(tarea, index):
    """Procesa una tarea automática: descarga video de YouTube, extrae audio y actualiza feed"""
    try:
        st.info(f"📤 Procesando: {tarea['title']}")
        
        # Descargar video de YouTube (esto requeriría youtube-dl o similar)
        # Por ahora, simularemos el proceso
        with st.spinner("Descargando video de YouTube..."):
            # En una implementación real, aquí usarías youtube-dl o yt-dlp
            st.warning("⚠️ Funcionalidad de descarga de YouTube requiere youtube-dl instalado")
            return False
        
        # El resto del proceso sería similar al de la pestaña 1
        # Extraer audio, subir a Drive, actualizar feed RSS
        
        # Marcar como procesado
        tareas_automaticas = cargar_tareas_automaticas()
        tareas_automaticas[index]['processed'] = True
        guardar_tareas_automaticas(tareas_automaticas)
        
        return True
        
    except Exception as e:
        st.error(f"Error al procesar la tarea: {str(e)}")
        return False

# ============
# FUNCIÓN PRINCIPAL
# ============

def main():
    st.title("🧘 YogaTe Upload - Gestor de Podcast")
    st.markdown("---")
    
    # Verificar credenciales
    if not verificar_credenciales():
        st.stop()
    
    # Crear pestañas
    tab1, tab2 = st.tabs(["📹 Subir Video y Crear Podcast", "🤖 Gestión Automática"])
    
    with tab1:
        pestaña_subir_video()
    
    with tab2:
        pestaña_gestion_automatica()

if __name__ == "__main__":
    main()
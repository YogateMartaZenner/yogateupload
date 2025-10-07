# YogaTe Upload - Gestor de Podcast

Una aplicación de Streamlit con dos funcionalidades principales para gestionar tu podcast de yoga de manera automatizada.

## Características

### 📹 Pestaña 1: Subir Video y Crear Podcast
- 🎥 Subida de videos directamente desde tu disco duro a YouTube
- ⏰ Programación de publicación con hora española
- 🎵 Extracción automática de audio del video
- 📁 Subida del audio a Google Drive (carpeta "Podcast")
- 📡 Generación automática de feed RSS
- 🔗 URLs listas para copiar a Spotify e Ivoox

### 🤖 Pestaña 2: Gestión Automática
- 📺 Listado automático de todos tus videos de YouTube
- 📅 Programación de tareas automáticas cada 48h
- 🎯 Selección múltiple de videos para procesar
- 🔄 Sincronización automática con plataformas de podcast

## Instalación

1. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configurar credenciales:**
   - Coloca `client_secret_drive.json` en el directorio raíz
   - Coloca `client_secret_youtube.json` en el directorio raíz
   - Estos archivos se obtienen desde Google Cloud Console

## Uso

1. **Ejecutar la aplicación:**
   ```bash
   streamlit run app.py
   ```

2. **Pestaña 1 - Subir Video:**
   - Selecciona un archivo de video desde tu disco
   - Completa título, descripción y tags
   - Opcionalmente programa la publicación
   - El sistema automáticamente:
     - Sube el video a YouTube
     - Extrae el audio
     - Lo sube a Google Drive
     - Crea/actualiza el feed RSS
     - Te proporciona las URLs para Spotify e Ivoox

3. **Pestaña 2 - Gestión Automática:**
   - Actualiza la lista de videos de tu canal
   - Selecciona videos para procesar automáticamente
   - Programa el intervalo (por defecto 48h)
   - El sistema procesará los videos seleccionados automáticamente

## Archivos Generados

- `drive_credentials.json` - Credenciales de Google Drive (automático)
- `youtube_credentials.json` - Credenciales de YouTube (automático)
- `episodios.json` - Base de datos de episodios del podcast
- `tareas_automaticas.json` - Tareas programadas para procesamiento
- `feed.xml` - Feed RSS del podcast (se actualiza automáticamente)

## Configuración de APIs

### Google Drive API
1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Crea un nuevo proyecto o selecciona uno existente
3. Habilita la Google Drive API
4. Crea credenciales OAuth 2.0
5. Descarga el archivo JSON como `client_secret_drive.json`

### YouTube Data API
1. En el mismo proyecto de Google Cloud Console
2. Habilita la YouTube Data API v3
3. Crea credenciales OAuth 2.0
4. Descarga el archivo JSON como `client_secret_youtube.json`

## Flujo de Trabajo Recomendado

1. **Para nuevos episodios:** Usa la Pestaña 1 para subir videos nuevos
2. **Para sincronizar contenido existente:** Usa la Pestaña 2 para procesar videos ya publicados
3. **Copia la URL del feed RSS** a Spotify e Ivoox para sincronización automática

## Proceso de Autenticación

La primera vez que uses la aplicación, necesitarás autenticarte con Google:

### Para Google Drive y YouTube:
1. **Haz clic en el enlace de autenticación** que aparece en la aplicación
2. **Inicia sesión** con tu cuenta de Google
3. **Autoriza la aplicación** cuando te lo solicite
4. **Copia el código** que aparece en la pantalla de Google (no de la URL)
5. **Pega el código** en el campo de texto de la aplicación

### ⚠️ Importante:
- El código aparece en la **pantalla de Google**, no en la URL
- Es un código largo que empieza con algo como `4/0AX4XfWh...`
- Una vez autenticado, no necesitarás volver a hacerlo

## Notas Importantes

- La autenticación se guarda automáticamente para futuras sesiones
- Los archivos temporales se eliminan automáticamente
- El feed RSS se actualiza con cada nuevo episodio
- Las tareas automáticas respetan el intervalo de 48h para dar tiempo a la propagación
- La aplicación usa la zona horaria española (Europe/Madrid)
- Si tienes problemas de autenticación, elimina los archivos `*_credentials.json` y vuelve a autenticarte

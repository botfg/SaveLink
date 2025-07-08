import os.path
import io
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# Области доступа. Если меняете их, удалите файл token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_drive_service():
    """Аутентифицируется и возвращает сервис для работы с Google Drive API."""
    creds = None
    # Файл token.json хранит токены доступа и обновления пользователя.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # Если нет валидных данных, запускаем процесс аутентификации.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            try:
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            except FileNotFoundError:
                logging.error("Файл credentials.json не найден. Убедитесь, что он находится в корневой папке проекта.")
                return None
        # Сохраняем данные для следующего запуска
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)
        return service
    except HttpError as error:
        logging.error(f'Произошла ошибка при создании сервиса Google Drive: {error}')
        return None

def find_or_create_backup_folder(service):
    """Находит или создает папку для бекапов и возвращает ее ID."""
    try:
        folder_id = None
        response = service.files().list(
            q="name='TelegramBotBackups' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            spaces='drive',
            fields='files(id, name)'
        ).execute()
        
        if not response.get('files', []):
            logging.info("Папка 'TelegramBotBackups' не найдена, создаю новую.")
            folder_metadata = {
                'name': 'TelegramBotBackups',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = service.files().create(body=folder_metadata, fields='id').execute()
            folder_id = folder.get('id')
        else:
            folder_id = response['files'][0].get('id')
        return folder_id
    except HttpError as error:
        logging.error(f"Ошибка при поиске или создании папки для бекапов: {error}")
        return None

def upload_database_backup(file_path, file_name):
    """Загружает файл на Google Drive и возвращает ссылку на него или None."""
    service = get_drive_service()
    if not service:
        return None

    try:
        folder_id = find_or_create_backup_folder(service)
        if not folder_id:
            return None

        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        # Указываем правильный mimetype для SQL/текстовых файлов
        media = MediaFileUpload(file_path, mimetype='text/plain', resumable=True)
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        logging.info(f"Файл '{file_name}' успешно загружен.")
        return file.get('webViewLink')

    except HttpError as error:
        logging.error(f'Произошла ошибка во время загрузки файла: {error}')
        return None

def download_latest_backup(destination_path):
    """Находит последний бекап, скачивает его и возвращает True в случае успеха."""
    service = get_drive_service()
    if not service:
        return False

    try:
        folder_id = find_or_create_backup_folder(service)
        if not folder_id:
            return False

        # Ищем последний файл .sql или .db в папке, сортируя по дате создания
        response = service.files().list(
            q=f"'{folder_id}' in parents and (name contains '.db' or name contains '.sql') and trashed=false",
            orderBy='createdTime desc',
            pageSize=1,
            fields='files(id, name)'
        ).execute()

        files = response.get('files', [])
        if not files:
            logging.warning("В папке на Google Drive не найдено файлов для восстановления.")
            return False

        latest_file = files[0]
        file_id = latest_file.get('id')
        file_name = latest_file.get('name')
        logging.info(f"Найден последний бекап: {file_name} (ID: {file_id})")

        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(destination_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            logging.info(f"Скачивание {int(status.progress() * 100)}%.")
        
        logging.info(f"Файл '{file_name}' успешно скачан в '{destination_path}'.")
        return True

    except HttpError as error:
        logging.error(f'Произошла ошибка во время скачивания файла: {error}')
        return False

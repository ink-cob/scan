import os
import re
import cv2
import easyocr
import pandas as pd
import requests
import numpy as np
import time

# =====================================================================
# НАСТРОЙКА ТОКЕНА И ЧАТА (Вставьте те же данные, что и в index.html)
# =====================================================================
TG_TOKEN = "СЮДА_ВСТАВЬТЕ_ТОКЕН_ВАШЕГО_БОТА"

# Включаем поддержку цветных сообщений в консоли Windows
os.system("")

print("\033[94m[ИИ] Инициализация EasyOCR на CPU... Пожалуйста, подождите.\033[0m")
reader = easyocr.Reader(['en']) 

def parse_text_from_lines(extracted_lines):
    """ Ищет модель и серийный номер в массиве найденных строк """
    detected_model = None
    detected_sn = None
    
    for line in extracted_lines:
        line_upper = line.upper().strip()
        if not line_upper: continue
        
        # Поиск модели (MODEL, MOD, MODEL NO)
        if "MODEL" in line_upper or "MOD" in line_upper:
            match = re.search(r'(?:MODEL|MOD|NO|№|[:.\s]+)+(.*)', line, re.IGNORECASE)
            if match and len(match.group(1).strip()) >= 3: 
                detected_model = match.group(1).strip()
                
        # Поиск серийного номера (S/N, SERIAL, SER. NO, SN)
        if "S/N" in line_upper or "SERIAL" in line_upper or "SER" in line_upper or "SN" in line_upper:
            match = re.search(r'(?:S/N|SERIAL|SER|NO|№|[:.\s\-/]+)+(.*)', line, re.IGNORECASE)
            if match and len(match.group(1).strip()) >= 3: 
                detected_sn = match.group(1).strip()
                
    return detected_model, detected_sn

def save_to_excel(row_data):
    """ Дописывает строку в Excel файл """
    excel_file = "final_monitors_archive.xlsx"
    if os.path.exists(excel_file):
        try:
            existing_df = pd.read_excel(excel_file)
            row_data["№"] = len(existing_df) + 1
            new_df = pd.concat([existing_df, pd.DataFrame([row_data])], ignore_index=True)
            new_df.to_excel(excel_file, index=False)
        except Exception as e: 
            print(f"❌ Ошибка записи в Excel: {e}")
    else:
        df = pd.DataFrame([row_data])
        df.to_excel(excel_file, index=False)
    print(f"\033[92m💾 Данные успешно записаны в '{excel_file}'!\033[0m")

def check_exit_command(user_input):
    """ Проверяет команду закрытия программы на ПК """
    if user_input.strip().lower() in ['q', 'й', 'quit', 'exit']:
        print("\n\033[91m👋 Завершаю работу программы. До свидания!\033[0m")
        return True
    return False

def get_telegram_updates(offset=None):
    """ Быстрый запрос к серверам Telegram для поиска новых фото """
    url = f"https://telegram.org{TG_TOKEN}/getUpdates"
    params = {"timeout": 10, "offset": offset}
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def download_file(file_id):
    """ Скачивает фото по его идентификатору из Telegram """
    try:
        # Получаем прямую ссылку на файл
        get_file_url = f"https://telegram.org{TG_TOKEN}/getFile"
        res = requests.get(get_file_url, params={"file_id": file_id}, timeout=10).json()
        if res.get("ok"):
            file_path = res["result"]["file_path"]
            file_download_url = f"https://telegram.org{TG_TOKEN}/{file_path}"
            
            # Скачиваем файл в бинарном режиме
            file_res = requests.get(file_download_url, timeout=15)
            if file_res.status_code == 200:
                return file_res.content
    except Exception as e:
        print(f"❌ Не удалось скачать фото: {e}")
    return None

def main_processing_loop():
    print("\033[94m┌──────────────────────────────────────────────────────────┐\033[0m")
    print("\033[94m│📱        ОБЛАЧНЫЙ ИИ-СКАНЕР ЧЕРЕЗ GITHUB И TELEGRAM       │\033[0m")
    print("\033[94m└──────────────────────────────────────────────────────────┘\033[0m")
    print(" 🛠 СИСТЕМА ГОТОВА К РАБОТЕ:")
    print(" 1. Откройте ваш сайт на GitHub Pages со смартфона.")
    print(" 2. Сделайте фото, выделите область и нажмите отправить.")
    print("\n 🛑 ДЛЯ ВЫХОДА ИЗ ПРОГРАММЫ:")
    print(" Введите латинскую \033[1;31mQ\033[0m (или русскую \033[1;31mЙ\033[0m) в консоль при вводе данных.")
    print("\033[94m───────────────────────────────────────────────────────────\033[0m")
    print("⏳ Слушаю облако. Ожидание снимков с телефона...")

    last_update_id = None
    
    # Очищаем старые сообщения при запуске скрипта, чтобы они не обрабатывались повторно
    initial_updates = get_telegram_updates()
    if initial_updates and initial_updates.get("result"):
        last_update_id = initial_updates["result"][-1]["update_id"] + 1

    while True:
        updates = get_telegram_updates(offset=last_update_id)
        
        if updates and updates.get("result"):
            for update in updates["result"]:
                last_update_id = update["update_id"] + 1
                
                # Ищем, прислали ли нам фото
                if "message" in update and "photo" in update["message"]:
                    print("\n\033[96m📸 Из облака получен новый вырезанный снимок! Передаю в ИИ...\033[0m")
                    
                    # Берем самое последнее фото из массива (оно в максимальном разрешении)
                    file_id = update["message"]["photo"][-1]["file_id"]
                    photo_bytes = download_file(file_id)
                    
                    if not photo_bytes:
                        print("❌ Ошибка: Не удалось загрузить картинку.")
                        continue

                    # Превращаем байты в формат картинки OpenCV
                    nparr = np.frombuffer(photo_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is None:
                        print("❌ Ошибка: Сбой декодирования изображения.")
                        continue

                    # Улучшаем снимок фильтрами
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    cleaned_photo = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 4)
                    
                    # Запускаем распознавание EasyOCR
                    ocr_results = reader.readtext(cleaned_photo)
                    
                    current_lines = []
                    for item in ocr_results:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            text_candidate = item[1]
                            if isinstance(text_candidate, str) and text_candidate.strip():
                                current_lines.append(text_candidate.strip())

                    # Подстраховочный проход по оригиналу
                    if not current_lines:
                        ocr_results_raw = reader.readtext(frame)
                        for item in ocr_results_raw:
                            if isinstance(item, (list, tuple)) and len(item) >= 2:
                                text_candidate = item[1]
                                if isinstance(text_candidate, str) and text_candidate.strip():
                                    current_lines.append(text_candidate.strip())

                    # Извлекаем модель и серийник
                    model, sn = parse_text_from_lines(current_lines)
                    detected_model = model if model else "Не найдена"
                    detected_sn = sn if sn else "Не указан"

                    print("\n\033[92m🎯 Данные успешно извлечены ИИ из рамки:\033[0m")
                    print(f"🤖 Модель устройства: \033[1;36m{detected_model}\033[0m")
                    print(f"🤖 Серийный номер (с\\н): \033[1;36m{detected_sn}\033[0m")
                    
                    # Ввод сопутствующих полей на ПК
                    print("\n\033[93m📝 Введите дополнительные данные за ПК (или 'Q' для выхода):\033[0m")
                    
                    user_brand = input("🖊 Производитель монитора: ").strip()
                    if check_exit_command(user_brand): return
                        
                    user_pc_num = input("🖊 № компьютера: ").strip()
                    if check_exit_command(user_pc_num): return

                    # Запись в Excel
                    new_row = {
                        "№": 1,
                        "Производитель": user_brand if user_brand else "Не указан",
                        "№ компьютера": user_pc_num if user_pc_num else "Не указан",
                        "Модель устройства": detected_model,
                        "с\\н": detected_sn
                    }
                    save_to_excel(new_row)
                    print("\n\033[94m───────────────────────────────────────────────────────────\033[0m")
                    print("⏳ Ожидание нового снимка с телефона...")
                    
        time.sleep(1)

if __name__ == "__main__":
    main_processing_loop()

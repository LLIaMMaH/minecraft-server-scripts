#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для архивирования старых папок со сборкой
"""

import os
import sys
import zipfile
import shutil
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Цвета для вывода
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

# Эмодзи
class Emoji:
    FOLDER = "📁"
    ARCHIVE = "📦"
    CHECK = "✅"
    ERROR = "❌"
    INFO = "ℹ️"
    SETTINGS = "⚙️"
    TRASH = "🗑️"
    LIST = "📋"
    EXIT = "🚪"
    BACK = "↩️"

# Константы
PREFIX = "GTNH"
DEFAULT_SETTINGS = {
    'archive_path': str(Path.home() / "archives"),
    'default_delete': True,
    'show_hidden': False,
    'compression_level': 6,  # 0-9, где 9 - максимальное сжатие
    'prefix': 'GTNH',  # Динамический префикс
    'backup_count': 5  # Количество сохраняемых архивов
}
SETTINGS_FILE = Path.home() / ".gtnh_archiver.json"

def load_settings() -> Dict[str, Any]:
    """Загрузка настроек из JSON файла"""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Объединяем с дефолтными настройками на случай добавления новых полей
                return {**DEFAULT_SETTINGS, **settings}
        except json.JSONDecodeError as e:
            print(f"{Colors.YELLOW}⚠️ Ошибка чтения JSON настроек: {e}")
            print(f"Используются настройки по умолчанию{Colors.END}")
        except Exception as e:
            print(f"{Colors.YELLOW}⚠️ Ошибка загрузки настроек: {e}{Colors.END}")
    
    # Возвращаем копию дефолтных настроек
    return DEFAULT_SETTINGS.copy()

def save_settings(settings: Dict[str, Any]) -> bool:
    """Сохранение настроек в JSON файл"""
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        print(f"{Colors.GREEN}{Emoji.CHECK} Настройки сохранены в JSON!{Colors.END}")
        return True
    except Exception as e:
        print(f"{Colors.RED}{Emoji.ERROR} Ошибка сохранения настроек: {e}{Colors.END}")
        return False

def clear_screen():
    """Очистка экрана"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    """Вывод заголовка"""
    clear_screen()
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.MAGENTA}{Colors.BOLD}        GTNH АРХИВАТОР ПАПОК СО СБОРКОЙ{Colors.END}")
    print(f"{Colors.CYAN}{Colors.BOLD}{'='*60}{Colors.END}")
    print(f"{Colors.YELLOW}Текущий префикс: {Colors.BOLD}{PREFIX}{Colors.END}{Colors.YELLOW}")
    print(f"Директория: {Path.cwd()}{Colors.END}")
    print()

def find_gtnh_folders(prefix: str = None) -> list:
    """Поиск папок с указанным префиксом в текущей директории"""
    if prefix is None:
        prefix = PREFIX
    
    folders = []
    current_dir = Path.cwd()
    
    try:
        for item in current_dir.iterdir():
            if item.is_dir() and item.name.startswith(prefix):
                folders.append(item)
    except PermissionError:
        print(f"{Colors.RED}Ошибка доступа к директории{Colors.END}")
    
    return sorted(folders, key=lambda x: x.name)

def print_folders_list(folders: list, settings: Dict[str, Any]):
    """Вывод списка папок"""
    if not folders:
        print(f"{Colors.YELLOW}{Emoji.INFO} Папки с префиксом '{settings.get('prefix', PREFIX)}' не найдены.{Colors.END}")
        print(f"{Colors.YELLOW}Текущая директория: {Path.cwd()}{Colors.END}")
        return
    
    print(f"{Colors.GREEN}{Emoji.LIST} Найдено папок: {len(folders)}{Colors.END}")
    print(f"{Colors.CYAN}{'─'*60}{Colors.END}")
    
    for i, folder in enumerate(folders, 1):
        try:
            size = get_folder_size(folder)
            mod_time = datetime.fromtimestamp(folder.stat().st_mtime).strftime('%d.%m.%Y %H:%M')
            print(f"{Colors.BOLD}{i:3}.{Colors.END} {Emoji.FOLDER} {folder.name}")
            print(f"     📏 Размер: {format_size(size)}")
            print(f"     📅 Изменен: {mod_time}")
            print(f"     📍 Путь: {folder}")
            
            # Проверка на существование архива
            archive_dir = Path(settings['archive_path'])
            if archive_dir.exists():
                archives = list(archive_dir.glob(f"{folder.name}_*.zip"))
                if archives:
                    latest = max(archives, key=lambda x: x.stat().st_mtime)
                    print(f"     📦 Последний архив: {latest.name}")
            
            print()
        except (PermissionError, OSError) as e:
            print(f"{Colors.RED}{i:3}. {Emoji.ERROR} {folder.name} - ошибка доступа{Colors.END}")
            print()

def get_folder_size(path: Path) -> int:
    """Получение размера папки в байтах"""
    total = 0
    try:
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = Path(dirpath) / f
                if fp.exists():
                    total += fp.stat().st_size
    except (PermissionError, OSError):
        pass
    return total

def format_size(size_bytes: int) -> str:
    """Форматирование размера в читаемый вид"""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB']
    for unit in units:
        if size_bytes < 1024.0 or unit == 'GB':
            break
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} {unit}"

def create_archive(folder_path: Path, settings: Dict[str, Any]) -> bool:
    """Создание архива с проверкой целостности"""
    archive_dir = Path(settings['archive_path'])
    
    # Создаем директорию для архивов, если не существует
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Формируем имя архива
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_name = f"{folder_path.name}_{timestamp}.zip"
    archive_full_path = archive_dir / archive_name
    
    print(f"{Colors.BLUE}{Emoji.ARCHIVE} Создание архива...{Colors.END}")
    print(f"{Colors.CYAN}Папка: {folder_path}{Colors.END}")
    print(f"{Colors.CYAN}Архив: {archive_full_path}{Colors.END}")
    print(f"{Colors.CYAN}Уровень сжатия: {settings.get('compression_level', 6)}{Colors.END}")
    
    try:
        # Создаем архив с указанным уровнем сжатия
        compression = zipfile.ZIP_DEFLATED
        compresslevel = settings.get('compression_level', 6)
        
        with zipfile.ZipFile(archive_full_path, 'w', compression, compresslevel=compresslevel) as zipf:
            for root, dirs, files in os.walk(folder_path):
                # Пропускаем скрытые файлы, если не включена настройка
                if not settings.get('show_hidden', False):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    files = [f for f in files if not f.startswith('.')]
                
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(folder_path.parent)
                    zipf.write(file_path, arcname)
        
        archive_size = archive_full_path.stat().st_size
        print(f"{Colors.GREEN}{Emoji.CHECK} Архив создан успешно!")
        print(f"Размер архива: {format_size(archive_size)}{Colors.END}")
        
        # Проверка целостности архива
        print(f"{Colors.BLUE}🔍 Проверка целостности архива...{Colors.END}")
        if verify_archive(archive_full_path):
            print(f"{Colors.GREEN}{Emoji.CHECK} Архив проверен, повреждений нет!{Colors.END}")
            
            # Управление количеством резервных копий
            manage_backups(folder_path.name, archive_dir, settings.get('backup_count', 5))
            
            # Запрос на удаление исходной папки
            default_text = "Y" if settings['default_delete'] else "N"
            response = input(f"\n{Colors.YELLOW}🗑️ Удалить исходную папку '{folder_path.name}'? [{default_text}]: {Colors.END}").strip().upper()
            
            if response == '':
                response = default_text
            
            if response == 'Y':
                try:
                    shutil.rmtree(folder_path)
                    print(f"{Colors.GREEN}{Emoji.TRASH} Папка '{folder_path.name}' удалена!{Colors.END}")
                except Exception as e:
                    print(f"{Colors.RED}{Emoji.ERROR} Ошибка удаления папки: {e}{Colors.END}")
            else:
                print(f"{Colors.YELLOW}Папка сохранена.{Colors.END}")
        else:
            print(f"{Colors.RED}{Emoji.ERROR} Архив поврежден! Исходная папка не будет удалена.{Colors.END}")
            
    except Exception as e:
        print(f"{Colors.RED}{Emoji.ERROR} Ошибка создания архива: {e}{Colors.END}")
        return False
    
    return True

def verify_archive(archive_path: Path) -> bool:
    """Проверка целостности архива"""
    try:
        with zipfile.ZipFile(archive_path, 'r') as zipf:
            return zipf.testzip() is None
    except Exception as e:
        print(f"{Colors.RED}{Emoji.ERROR} Ошибка проверки архива: {e}{Colors.END}")
        return False

def manage_backups(folder_name: str, archive_dir: Path, max_backups: int):
    """Управление количеством резервных копий"""
    if max_backups <= 0:
        return
    
    archives = sorted(archive_dir.glob(f"{folder_name}_*.zip"), 
                     key=lambda x: x.stat().st_mtime, 
                     reverse=True)
    
    if len(archives) > max_backups:
        print(f"{Colors.YELLOW}Очистка старых архивов (сохраняется {max_backups} копий)...{Colors.END}")
        for archive in archives[max_backups:]:
            try:
                archive.unlink()
                print(f"{Colors.YELLOW}  Удален: {archive.name}{Colors.END}")
            except Exception as e:
                print(f"{Colors.RED}  Ошибка удаления {archive.name}: {e}{Colors.END}")

def show_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Отображение и изменение настроек"""
    while True:
        print_header()
        print(f"{Colors.MAGENTA}{Emoji.SETTINGS} НАСТРОЙКИ{Colors.END}")
        print(f"{Colors.CYAN}{'─'*60}{Colors.END}")
        
        print(f"1. {Colors.BOLD}Путь для сохранения архивов:{Colors.END}")
        print(f"   {settings['archive_path']}")
        print()
        
        print(f"2. {Colors.BOLD}Удалять папку после архивации по умолчанию:{Colors.END}")
        print(f"   {'✅ Да' if settings['default_delete'] else '❌ Нет'}")
        print()
        
        print(f"3. {Colors.BOLD}Уровень сжатия (0-9):{Colors.END}")
        print(f"   {settings.get('compression_level', 6)} (0 - без сжатия, 9 - максимальное)")
        print()
        
        print(f"4. {Colors.BOLD}Префикс для поиска папок:{Colors.END}")
        print(f"   {settings.get('prefix', PREFIX)}")
        print()
        
        print(f"5. {Colors.BOLD}Количество хранимых архивов:{Colors.END}")
        print(f"   {settings.get('backup_count', 5)} (0 - хранить все)")
        print()
        
        print(f"6. {Colors.BOLD}Показывать скрытые файлы:{Colors.END}")
        print(f"   {'✅ Да' if settings.get('show_hidden', False) else '❌ Нет'}")
        print()
        
        print(f"{Colors.CYAN}{'─'*60}{Colors.END}")
        print(f"{Colors.YELLOW}1-6 - Изменить настройку")
        print(f"0 - {Emoji.BACK} Назад в главное меню{Colors.END}")
        print()
        
        choice = input(f"{Colors.GREEN}Выберите настройку для изменения [0-6]: {Colors.END}").strip()
        
        if choice == '0':
            return settings
            
        elif choice == '1':
            new_path = input(f"{Colors.CYAN}Введите новый путь для архивов: {Colors.END}").strip()
            if new_path:
                settings['archive_path'] = new_path
                save_settings(settings)
                input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
                
        elif choice == '2':
            current = "Да" if settings['default_delete'] else "Нет"
            print(f"\n{Colors.CYAN}Текущее значение: {current}{Colors.END}")
            new_value = input(f"{Colors.CYAN}Удалять после архивации? (Y/N) [{current[0]}]: {Colors.END}").strip().upper()
            if new_value in ['Y', 'N']:
                settings['default_delete'] = (new_value == 'Y')
                save_settings(settings)
            elif new_value == '':
                pass
            else:
                print(f"{Colors.RED}{Emoji.ERROR} Неверное значение!{Colors.END}")
            input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
            
        elif choice == '3':
            current = settings.get('compression_level', 6)
            print(f"\n{Colors.CYAN}Текущее значение: {current}{Colors.END}")
            try:
                new_value = int(input(f"{Colors.CYAN}Новый уровень сжатия (0-9) [{current}]: {Colors.END}").strip())
                if 0 <= new_value <= 9:
                    settings['compression_level'] = new_value
                    save_settings(settings)
                else:
                    print(f"{Colors.RED}{Emoji.ERROR} Значение должно быть от 0 до 9!{Colors.END}")
            except ValueError:
                print(f"{Colors.RED}{Emoji.ERROR} Введите число!{Colors.END}")
            input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
            
        elif choice == '4':
            current = settings.get('prefix', PREFIX)
            print(f"\n{Colors.CYAN}Текущее значение: {current}{Colors.END}")
            new_value = input(f"{Colors.CYAN}Новый префикс для поиска [{current}]: {Colors.END}").strip()
            if new_value:
                settings['prefix'] = new_value
                save_settings(settings)
            input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
            
        elif choice == '5':
            current = settings.get('backup_count', 5)
            print(f"\n{Colors.CYAN}Текущее значение: {current}{Colors.END}")
            try:
                new_value = int(input(f"{Colors.CYAN}Количество хранимых архивов (0 - все) [{current}]: {Colors.END}").strip())
                if new_value >= 0:
                    settings['backup_count'] = new_value
                    save_settings(settings)
                else:
                    print(f"{Colors.RED}{Emoji.ERROR} Значение должно быть >= 0!{Colors.END}")
            except ValueError:
                print(f"{Colors.RED}{Emoji.ERROR} Введите число!{Colors.END}")
            input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
            
        elif choice == '6':
            current = settings.get('show_hidden', False)
            status = "Да" if current else "Нет"
            print(f"\n{Colors.CYAN}Текущее значение: {status}{Colors.END}")
            new_value = input(f"{Colors.CYAN}Показывать скрытые файлы? (Y/N) [{status[0]}]: {Colors.END}").strip().upper()
            if new_value in ['Y', 'N']:
                settings['show_hidden'] = (new_value == 'Y')
                save_settings(settings)
            elif new_value == '':
                pass
            else:
                print(f"{Colors.RED}{Emoji.ERROR} Неверное значение!{Colors.END}")
            input(f"\n{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
            
        else:
            print(f"{Colors.RED}{Emoji.ERROR} Неверный выбор!{Colors.END}")
            input(f"{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")

def main():
    """Главная функция"""
    settings = load_settings()
    
    # Обновляем глобальный префикс из настроек
    global PREFIX
    PREFIX = settings.get('prefix', PREFIX)
    
    while True:
        print_header()
        
        print(f"{Colors.GREEN}{Colors.BOLD}ГЛАВНОЕ МЕНЮ{Colors.END}")
        print(f"{Colors.CYAN}{'─'*60}{Colors.END}")
        print(f"{Colors.BOLD}1{Colors.END} {Emoji.LIST} Посмотреть список папок с префиксом '{PREFIX}'")
        print(f"{Colors.BOLD}2{Colors.END} {Emoji.ARCHIVE} Заархивировать папку")
        print(f"{Colors.BOLD}3{Colors.END} {Emoji.SETTINGS} Настройки")
        print(f"{Colors.BOLD}0{Colors.END} {Emoji.EXIT} Выход")
        print(f"{Colors.CYAN}{'─'*60}{Colors.END}")
        
        choice = input(f"\n{Colors.GREEN}Выберите действие [0-3]: {Colors.END}").strip()
        
        if choice == '0':
            print(f"\n{Colors.MAGENTA}До свидания! {Emoji.CHECK}{Colors.END}")
            sys.exit(0)
            
        elif choice == '1':
            folders = find_gtnh_folders(PREFIX)
            print_header()
            print_folders_list(folders, settings)
            input(f"\n{Colors.YELLOW}Нажмите Enter для возврата в меню...{Colors.END}")
            
        elif choice == '2':
            folders = find_gtnh_folders(PREFIX)
            
            if not folders:
                print(f"\n{Colors.YELLOW}{Emoji.INFO} Папки с префиксом '{PREFIX}' не найдены.{Colors.END}")
                input(f"{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")
                continue
            
            print_header()
            print(f"{Colors.MAGENTA}{Emoji.ARCHIVE} АРХИВАЦИЯ ПАПКИ{Colors.END}")
            print(f"{Colors.CYAN}{'─'*60}{Colors.END}")
            print_folders_list(folders, settings)
            
            try:
                folder_num = int(input(f"\n{Colors.GREEN}Выберите номер папки для архивации [1-{len(folders)}]: {Colors.END}").strip())
                
                if 1 <= folder_num <= len(folders):
                    selected_folder = folders[folder_num - 1]
                    create_archive(selected_folder, settings)
                else:
                    print(f"{Colors.RED}{Emoji.ERROR} Неверный номер папки!{Colors.END}")
            except ValueError:
                print(f"{Colors.RED}{Emoji.ERROR} Введите число!{Colors.END}")
            
            input(f"\n{Colors.YELLOW}Нажмите Enter для возврата в меню...{Colors.END}")
            
        elif choice == '3':
            settings = show_settings(settings)
            # Обновляем префикс после изменения настроек
            PREFIX = settings.get('prefix', PREFIX)
            
        else:
            print(f"{Colors.RED}{Emoji.ERROR} Неверный выбор!{Colors.END}")
            input(f"{Colors.YELLOW}Нажмите Enter для продолжения...{Colors.END}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Прервано пользователем. {Emoji.EXIT}{Colors.END}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}{Emoji.ERROR} Критическая ошибка: {e}{Colors.END}")
        sys.exit(1)


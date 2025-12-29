#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
BellSoft Java Universal Installer
Скрипт для загрузки и установки Java от BellSoft
"""

import os
import sys
import json
import time
import shutil
import hashlib
import tarfile
import zipfile
import argparse
import tempfile
import subprocess
import glob
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ========== КОНСТАНТЫ И НАСТРОЙКИ ==========
API_URL = "https://api.bell-sw.com/v1/liberica/releases"
DEFAULT_CACHE_DIR = os.path.join(tempfile.gettempdir(), "bellsoft-java")

# Умное определение директории установки по умолчанию
def get_default_install_dir():
    """Определяет директорию установки по умолчанию"""
    try:
        # Получаем директорию скрипта
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Проверяем, можем ли писать в директорию скрипта
        test_file = os.path.join(script_dir, ".write_test")
        try:
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            return os.path.join(script_dir, "Java")
        except (PermissionError, OSError):
            # Если нет прав, используем домашнюю директорию
            return os.path.expanduser("~/Java")
    except Exception:
        # В случае ошибки используем домашнюю директорию
        return os.path.expanduser("~/Java")

DEFAULT_INSTALL_DIR = get_default_install_dir()
CACHE_FILE_PREFIX = "api-cache-"
CACHE_MAX_AGE_HOURS = 24  # Обновлять кэш раз в сутки
REQUEST_TIMEOUT = 300  # 5 минут
SETTINGS_FILE = "settings.json"  # Имя файла настроек (будет в папке кэша)

# Эмодзи для отображения
EMOJI = {
    "check": "✅",
    "warn": "⚠️ ",
    "error": "❌",
    "info": "ℹ️ ",
    "download": "📥",
    "folder": "📁",
    "computer": "💻",
    "package": "📦",
    "version": "🔢",
    "select": "🎯",
    "chart": "📊",
    "rocket": "🚀",
    "globe": "🌐",
    "offline": "🛜",
    "clock": "⏱️ ",
    "disk": "💾",
    "network": "🌍",
    "search": "🔍",
    "hammer": "🛠️ ",
    "trash": "🗑️ ",
    "gear": "⚙️ ",
    "save": "💾",
    "reset": "🔄",
}

# Цвета для терминала
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    NC = '\033[0m'  # No Color

# Проверяем, поддерживает ли терминал цвета
HAS_COLOR = sys.stdout.isatty()

# ========== УТИЛИТЫ ==========
def colorize(text, color):
    """Добавляет цвет к тексту, если терминал поддерживает цвета"""
    if HAS_COLOR:
        return f"{color}{text}{Colors.NC}"
    return text

def print_success(msg):
    print(f"{colorize(EMOJI['check'], Colors.GREEN)} {msg}")

def print_warning(msg):
    print(f"{colorize(EMOJI['warn'], Colors.YELLOW)} {msg}")

def print_error(msg):
    print(f"{colorize(EMOJI['error'], Colors.RED)} {msg}")

def print_info(msg):
    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {msg}")

def print_download(msg):
    print(f"{colorize(EMOJI['download'], Colors.BLUE)} {msg}")

def print_separator(length=60, char="="):
    print(colorize(char * length, Colors.DIM))

def human_size(size_bytes):
    """Конвертирует байты в читаемый формат"""
    if size_bytes == 0:
        return "0 Б"
    
    units = ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']
    unit = 0
    
    while size_bytes >= 1024 and unit < len(units) - 1:
        size_bytes /= 1024
        unit += 1
    
    return f"{size_bytes:.1f} {units[unit]}"

def clear_screen():
    """Очищает экран терминала"""
    os.system('cls' if os.name == 'nt' else 'clear')

def select_option(prompt, options, allow_back=True, columns=None, trim_long_lines=True):
    """
    Выбор опции из списка.
    Возвращает выбранный элемент или None для выхода
    
    Args:
        prompt: заголовок меню
        options: список опций
        allow_back: разрешить выход по 0
        columns: количество колонок (None для автовыбора)
        trim_long_lines: обрезать длинные строки
    """
    if not options:
        print_error("Нет доступных вариантов")
        return None
    
    print()
    print_separator()
    print(f"{colorize(EMOJI['select'], Colors.MAGENTA)} {prompt}")
    print_separator()
    
    # Автоматически определяем количество колонок на основе количества элементов
    if columns is None:
        if len(options) <= 5:
            columns = 1
        elif len(options) <= 15:
            columns = 2
        elif len(options) <= 30:
            columns = 3
        else:
            columns = 4
    
    # Определяем ширину номера по максимальному значению
    max_number = len(options)
    num_width = len(str(max_number))
    
    # Если нужно, показываем в несколько колонок
    if columns > 1 and len(options) > 10:
        # Выводим опции в несколько колонок
        display_columns(options, columns=columns, show_numbers=True)
    else:
        # Выводим в один столбец с номерами
        for i, option in enumerate(options, 1):
            num_str = colorize(str(i).rjust(num_width), Colors.YELLOW)
            option_str = str(option)
            
            # Обрезаем только если включено И строка действительно очень длинная
            if trim_long_lines and len(option_str) > 100:
                option_str = option_str[:97] + "..."
            
            print(f"{num_str} │ {option_str}")
    
    if allow_back:
        zero_str = colorize('0'.rjust(num_width), Colors.YELLOW)
        print(f"{zero_str} │ {colorize('Назад/Выход', Colors.BOLD)}")
    print_separator()
    
    # Получаем выбор пользователя
    while True:
        try:
            max_choice = len(options)
            choice_prompt = f"Выберите номер [{'0-' if allow_back else ''}{max_choice}]: "
            choice = input(colorize(choice_prompt, Colors.BOLD))
            
            if choice == "0" and allow_back:
                return None
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(options):
                    return options[idx]
            
            print_error(f"Неверный выбор. Введите число от {0 if allow_back else 1} до {max_choice}")
        
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        except Exception as e:
            print_error(f"Ошибка: {e}")
            return None

def select_release(prompt, releases):
    """
    Специальная функция для выбора релиза.
    Не обрезает строки, так как они уже отформатированы.
    """
    if not releases:
        print_error("Нет доступных релизов")
        return None
    
    print()
    print_separator()
    print(f"{colorize(EMOJI['select'], Colors.MAGENTA)} {prompt}")
    print_separator()
    
    # Определяем ширину номера
    max_number = len(releases)
    num_width = len(str(max_number))
    
    # Выводим релизы с номерами (без обрезки строк)
    for i, release in enumerate(releases, 1):
        num_str = colorize(str(i).rjust(num_width), Colors.YELLOW)
        print(f"{num_str} │ {release}")
    
    # Добавляем опцию "Назад/Выход"
    zero_str = colorize('0'.rjust(num_width), Colors.YELLOW)
    print(f"{zero_str} │ {colorize('Назад/Выход', Colors.BOLD)}")
    
    print_separator()
    
    # Получаем выбор пользователя
    while True:
        try:
            max_choice = len(releases)
            choice_prompt = f"Выберите номер [0-{max_choice}]: "
            choice = input(colorize(choice_prompt, Colors.BOLD))
            
            if choice == "0":
                return None
            
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(releases):
                    return releases[idx]
            
            print_error(f"Неверный выбор. Введите число от 0 до {max_choice}")
        
        except (KeyboardInterrupt, EOFError):
            print()
            return None
        except Exception as e:
            print_error(f"Ошибка: {e}")
            return None

def display_columns(items, columns=3, max_width=80, indent=0, show_numbers=True, 
                   already_formatted=False):
    """
    Выводит список элементов в несколько колонок с нумерацией.
    
    Args:
        items: список элементов для отображения
        columns: количество колонок
        max_width: максимальная ширина вывода
        indent: отступ слева
        show_numbers: показывать номера перед элементами
        already_formatted: элементы уже содержат форматирование (цвета, выравнивание)
    """
    if not items:
        return
    
    # Рассчитываем ширину номера
    max_number = len(items)
    num_width = len(str(max_number)) if show_numbers else 0
    
    if already_formatted:
        # Если элементы уже отформатированы, просто выводим их как есть
        rows = (len(items) + columns - 1) // columns
        
        # Создаем строки для вывода
        for row in range(rows):
            line_parts = []
            for col in range(columns):
                # Индекс элемента в исходном списке
                index = row + col * rows
                if index < len(items):
                    if show_numbers:
                        # Добавляем номер
                        num_str = colorize(str(index + 1).rjust(num_width), Colors.YELLOW)
                        formatted_item = f"{num_str} │ {items[index]}"
                    else:
                        formatted_item = items[index]
                    line_parts.append(formatted_item)
                else:
                    # Пустая ячейка
                    line_parts.append("")
            
            # Выводим строку с отступом
            if any(line_parts):
                # Фильтруем пустые части и соединяем
                non_empty_parts = [part for part in line_parts if part]
                print(" " * indent + "   ".join(non_empty_parts))
    else:
        # Оригинальная логика для неформатированных элементов
        # Находим максимальную длину текста элементов (без цветовых кодов)
        max_text_width = 0
        clean_items = []
        for item in items:
            item_str = str(item)
            # Удаляем цветовые коды для вычисления реальной длины
            clean_str = item_str
            if HAS_COLOR:
                # Удаляем ANSI escape коды
                import re
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                clean_str = ansi_escape.sub('', item_str)
            
            clean_items.append(clean_str)
            max_text_width = max(max_text_width, len(clean_str))
        
        # Фиксируем ширину текста (добавляем немного места)
        text_width = max_text_width + 2  # +2 для отступов
        
        # Общая ширина одной колонки
        column_width = num_width + text_width + 3  # +3 для " │ "
        
        # Проверяем, поместится ли всё в max_width
        total_width = column_width * columns + (columns - 1) * 3  # 3 пробела между колонками
        if total_width > max_width and columns > 1:
            # Уменьшаем количество колонок
            columns = max_width // (column_width + 3)
            if columns < 1:
                columns = 1
        
        # Рассчитываем количество строк (равномерно распределяем по столбцам)
        rows = (len(items) + columns - 1) // columns
        
        # Создаем строки для вывода
        for row in range(rows):
            line_parts = []
            for col in range(columns):
                # Индекс элемента в исходном списке
                index = row + col * rows
                if index < len(items):
                    item_text = str(items[index])
                    clean_text = clean_items[index]
                    
                    # Выравниваем чистый текст, затем добавляем обратно цвета
                    aligned_clean_text = clean_text.ljust(text_width)
                    
                    # Заменяем выровненный текст в исходной строке (сохраняя цвета)
                    if HAS_COLOR and clean_text != item_text:
                        # Если были цвета, нужно аккуратно их сохранить
                        aligned_text = item_text.replace(clean_text, aligned_clean_text)
                    else:
                        aligned_text = colorize(aligned_clean_text, Colors.CYAN)
                    
                    # Форматируем элемент
                    if show_numbers:
                        # Добавляем номер
                        num_str = colorize(str(index + 1).rjust(num_width), Colors.YELLOW)
                        formatted_item = f"{num_str} │ {aligned_text}"
                    else:
                        formatted_item = aligned_text
                    
                    line_parts.append(formatted_item)
                else:
                    # Пустая ячейка для выравнивания
                    empty_text = "".ljust(text_width)
                    if show_numbers:
                        empty_num = "".rjust(num_width)
                        formatted_item = f"{empty_num} │ {colorize(empty_text, Colors.CYAN)}"
                    else:
                        formatted_item = colorize(empty_text, Colors.CYAN)
                    line_parts.append(formatted_item)
            
            # Выводим строку с отступом
            if line_parts:
                # Убираем пробелы в конце каждой колонки
                cleaned_parts = []
                for part in line_parts:
                    # Убираем пробелы только в конце текста (не трогая цветовые коды)
                    if HAS_COLOR and part.endswith(Colors.NC):
                        # Если заканчивается цветовым кодом, удаляем пробелы перед ним
                        part = part.rstrip()
                        if not part.endswith(Colors.NC):
                            part += Colors.NC
                    else:
                        part = part.rstrip()
                    cleaned_parts.append(part)
                
                print(" " * indent + "   ".join(cleaned_parts))

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ФОРМАТИРОВАНИЯ КОМАНД ==========
def format_export_cmd(variable, value, color=Colors.GREEN):
    """Форматирует команду export для вывода"""
    cmd = f'export {variable}="{value}"'
    return colorize(cmd, color)

def format_path_cmd(path_var, color=Colors.GREEN):
    """Форматирует команду PATH для вывода"""
    cmd = f'export PATH="{path_var}:$PATH"'
    return colorize(cmd, color)

def format_java_home_cmd(java_home_path, color=Colors.GREEN):
    """Форматирует команду JAVA_HOME для вывода"""
    return format_export_cmd('JAVA_HOME', java_home_path, color)

def format_java_path_cmd(java_bin_path=None, color=Colors.GREEN):
    """Форматирует команду PATH для Java"""
    if java_bin_path:
        return format_path_cmd(java_bin_path, color)
    else:
        return format_path_cmd('$JAVA_HOME/bin', color)

def format_java_env_config(java_home_path, use_latest_link=None):
    """Форматирует полную конфигурацию окружения Java"""
    config_lines = []
    config_lines.append(f"# Java from BellSoft Installer ({datetime.now().strftime('%Y-%m-%d')})")
    
    if use_latest_link and os.path.exists(use_latest_link):
        config_lines.append(f'export JAVA_HOME="{use_latest_link}"')
    else:
        config_lines.append(f'export JAVA_HOME="{java_home_path}"')
    
    config_lines.append('export PATH="$JAVA_HOME/bin:$PATH"')
    return '\n'.join(config_lines)

# ========== КЛАСС НАСТРОЕК ==========
class Settings:
    """Класс для управления настройками с сохранением в файл"""
    
    # Дефолтные настройки
    DEFAULT_SETTINGS = {
        'install_dir': DEFAULT_INSTALL_DIR,
        'cache_dir': DEFAULT_CACHE_DIR,
        'timeout': REQUEST_TIMEOUT,
        'offline_mode': False,
        'show_colors': True,
        'keep_old_cache': 3,
        'cleanup_days': 7,
        'auto_update_cache': True,
        'prefer_latest_link': True,
        'check_sha1': True,
        'download_resume': True,
        'show_progress': True,
        'max_releases_display': 20,
        'cache_max_age_hours': CACHE_MAX_AGE_HOURS,
    }
    
    # Отображаемые имена настроек
    SETTING_NAMES = {
        'install_dir': 'Директория установки',
        'cache_dir': 'Директория кэша',
        'timeout': 'Таймаут запросов (сек)',
        'offline_mode': 'Офлайн режим',
        'show_colors': 'Цветной вывод',
        'keep_old_cache': 'Хранить старых кэшей',
        'cleanup_days': 'Удалять файлы старше (дней)',
        'auto_update_cache': 'Автообновление кэша',
        'prefer_latest_link': 'Использовать ссылку latest',
        'check_sha1': 'Проверять SHA1',
        'download_resume': 'Возобновлять загрузку',
        'show_progress': 'Показывать прогресс',
        'max_releases_display': 'Макс. релизов для показа',
        'cache_max_age_hours': 'Возраст кэша для обновления (часов)',
    }
    
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.settings_file = os.path.join(cache_dir, SETTINGS_FILE)
        self.settings = self.load_settings()
    
    def load_settings(self):
        """Загружает настройки из файла или использует дефолтные"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                # Объединяем с дефолтными значениями
                settings = self.DEFAULT_SETTINGS.copy()
                settings.update(loaded_settings)
                return settings
            except Exception as e:
                print_warning(f"Не удалось загрузить настройки: {e}. Использую настройки по умолчанию.")
                return self.DEFAULT_SETTINGS.copy()
        else:
            return self.DEFAULT_SETTINGS.copy()
    
    def save_settings(self):
        """Сохраняет настройки в файл"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print_error(f"Не удалось сохранить настройки: {e}")
            return False
    
    def get(self, key, default=None):
        """Получает значение настройки"""
        return self.settings.get(key, default)
    
    def set(self, key, value):
        """Устанавливает значение настройки и сохраняет"""
        if key in self.settings:
            self.settings[key] = value
            self.save_settings()
            return True
        return False
    
    def reset_to_defaults(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.save_settings()
        return True
    
    def get_all(self):
        """Возвращает все настройки"""
        return self.settings.copy()
    
    def get_display_name(self, key):
        """Возвращает отображаемое имя настройки"""
        return self.SETTING_NAMES.get(key, key)
    
    def format_value(self, key, value):
        """Форматирует значение настройки для отображения"""
        if isinstance(value, bool):
            return "✅ Вкл" if value else "❌ Выкл"
        elif key in ['install_dir', 'cache_dir']:
            # Сокращаем длинные пути
            if len(str(value)) > 40:
                return "..." + str(value)[-37:]
            return str(value)
        else:
            return str(value)

# ========== КЛАСС ЛОГГЕРА ==========
class Logger:
    """Простой логгер для записи в файл"""
    
    def __init__(self, log_file):
        self.log_file = log_file
        self._ensure_log_dir()
    
    def _ensure_log_dir(self):
        """Создаёт директорию для логов если её нет"""
        log_dir = os.path.dirname(self.log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
    
    def _clean_message(self, msg):
        """Очищает сообщение от цветовых кодов и эмодзи для лога"""
        # Удаляем ANSI коды цветов
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        msg = ansi_escape.sub('', msg)
        
        # Заменяем эмодзи на текстовые аналоги
        emoji_replacements = {
            "✅": "[OK]",
            "⚠️ ": "[WARN]",
            "❌": "[ERR]",
            "ℹ️ ": "[INFO]",
            "📥": "[DL]",
            "📁": "[DIR]",
            "💻": "[CPU]",
            "📦": "[PKG]",
            "🔢": "[VER]",
            "🎯": "[SEL]",
            "📊": "[STAT]",
            "🚀": "[START]",
            "🌐": "[OS]",
            "🛜": "[OFFLINE]",
            "⏱️ ": "[TIME]",
            "💾": "[DISK]",
            "🌍": "[NET]",
            "🔍": "[SEARCH]",
            "🛠️ ": "[TOOL]",
            "🗑️ ": "[TRASH]",
            "⚙️ ": "[GEAR]",
            "💾": "[SAVE]",
            "🔄": "[RESET]",
        }
        
        for emoji, text in emoji_replacements.items():
            msg = msg.replace(emoji, text)
        
        return msg
    
    def log(self, msg):
        """Записывает сообщение в лог"""
        try:
            clean_msg = self._clean_message(msg)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {clean_msg}\n")
        except Exception as e:
            print_error(f"Не удалось записать в лог: {e}")

# ========== КЛАСС УСТАНОВЩИКА ==========
class JavaInstaller:
    """Основной класс установщика Java"""
    
    def __init__(self, args):
        self.args = args
        
        # Инициализируем настройки
        self.settings = Settings(args.work_dir)
        
        # Переопределяем настройки аргументами командной строки
        if args.work_dir != DEFAULT_CACHE_DIR:
            self.settings.set('cache_dir', args.work_dir)
        if args.install_dir != DEFAULT_INSTALL_DIR:
            self.settings.set('install_dir', args.install_dir)
        if args.timeout != REQUEST_TIMEOUT:
            self.settings.set('timeout', args.timeout)
        if args.offline:
            self.settings.set('offline_mode', True)
        if args.no_color:
            self.settings.set('show_colors', False)
        
        # Обновляем глобальные переменные
        # Используем globals() вместо global declaration
        globals()['HAS_COLOR'] = self.settings.get('show_colors') and sys.stdout.isatty()
        
        # Создаём необходимые директории
        os.makedirs(self.settings.get('cache_dir'), exist_ok=True)
        os.makedirs(self.settings.get('install_dir'), exist_ok=True)
        
        # Настройка логгера
        log_file = os.path.join(self.settings.get('cache_dir'), "installer.log")
        self.logger = Logger(log_file)
        
        # Кэш данных
        self.cache_file = None
        self.api_data = None
    
    def log(self, msg):
        """Логирует сообщение"""
        print(msg)
        self.logger.log(msg)

    def fetch_api_data(self, force=False):
        """Получает данные с API или из кэша"""
        cache_dir = self.settings.get('cache_dir')
        
        # Ищем самый свежий кэш
        cache_files = []
        for f in os.listdir(cache_dir):
            if f.startswith(CACHE_FILE_PREFIX) and f.endswith('.json'):
                cache_files.append(f)

        if cache_files:
            # Сортируем по дате в имени файла
            cache_files.sort(reverse=True)
            latest_cache = os.path.join(cache_dir, cache_files[0])

            # Проверяем возраст кэша
            cache_time = datetime.fromtimestamp(os.path.getmtime(latest_cache))
            cache_age = datetime.now() - cache_time
            cache_max_age = self.settings.get('cache_max_age_hours', CACHE_MAX_AGE_HOURS)

            if not force and cache_age.total_seconds() < cache_max_age * 3600:
                self.log(f"{EMOJI['info']} Использую кэшированные данные "
                        f"({int(cache_age.total_seconds() / 60)} минут назад)")
                self.cache_file = latest_cache
                return True

        # Если офлайн режим
        if self.settings.get('offline_mode'):
            if cache_files:
                self.cache_file = os.path.join(cache_dir, cache_files[0])
                self.log(f"{EMOJI['offline']} Офлайн режим: использую кэш от "
                        f"{cache_files[0][len(CACHE_FILE_PREFIX):-5]}")
                return True
            else:
                self.log(f"{EMOJI['error']} Офлайн режим: нет кэшированных данных")
                return False

        # Загружаем новые данные
        self.log(f"{colorize(EMOJI['network'], Colors.BLUE)} {colorize('Запрашиваю данные с API BellSoft...', Colors.BOLD)}")
        self.log(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('URL:', Colors.BOLD)} {colorize(API_URL, Colors.DIM)}")
        
        try:
            start_time = time.time()
            req = Request(API_URL, headers={'User-Agent': 'Mozilla/5.0'})
            timeout = self.settings.get('timeout', REQUEST_TIMEOUT)
            
            with urlopen(req, timeout=timeout) as response:
                total_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                chunks = []
                chunk_size = 8192
                
                self.log(f"{colorize(EMOJI['download'], Colors.BLUE)} {colorize('Начинаю загрузку...', Colors.BOLD)}")
                
                # Создаём прогресс-бар
                if total_size > 0 and HAS_COLOR and self.settings.get('show_progress', True):
                    print(f"\r{colorize(EMOJI['download'], Colors.BLUE)} {colorize('Загрузка:', Colors.BOLD)} [{' ' * 50}] 0%", end='')
                
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    
                    chunks.append(chunk)
                    downloaded += len(chunk)
                    
                    # Обновляем прогресс-бар
                    if total_size > 0 and HAS_COLOR and self.settings.get('show_progress', True):
                        percent = (downloaded / total_size) * 100
                        filled = int(50 * downloaded // total_size)
                        bar = colorize('█' * filled, Colors.GREEN) + colorize('░' * (50 - filled), Colors.DIM)
                        
                        # Форматируем размеры
                        downloaded_str = colorize(human_size(downloaded), Colors.CYAN)
                        total_str = colorize(human_size(total_size), Colors.CYAN)
                        
                        print(f"\r{colorize(EMOJI['download'], Colors.BLUE)} {colorize('Загрузка:', Colors.BOLD)} [{bar}] {colorize(f'{percent:.1f}%', Colors.YELLOW)} ({downloaded_str}/{total_str})", end='')
                
                data = b''.join(chunks)
                
                if total_size > 0 and HAS_COLOR and self.settings.get('show_progress', True):
                    print()  # Новая строка после прогресс-бара
                
                download_time = time.time() - start_time
                self.log(f"{colorize(EMOJI['download'], Colors.BLUE)} {colorize('Загружено', Colors.BOLD)} {colorize(human_size(len(data)), Colors.GREEN)} "
                        f"{colorize('за', Colors.BOLD)} {colorize(f'{download_time:.1f} сек', Colors.CYAN)}")
                
                # Парсим JSON для проверки
                json_data = json.loads(data.decode('utf-8'))
                
                # Сохраняем в файл с текущей датой
                cache_filename = f"{CACHE_FILE_PREFIX}{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                self.cache_file = os.path.join(cache_dir, cache_filename)
                
                with open(self.cache_file, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=2)
                
                self.api_data = json_data
                self.log(f"{colorize(EMOJI['check'], Colors.GREEN)} {colorize('Получено', Colors.BOLD)} {colorize(str(len(json_data)), Colors.GREEN)} {colorize('записей', Colors.BOLD)}")
                self.log(f"{colorize(EMOJI['disk'], Colors.BLUE)} {colorize('Кэш сохранен:', Colors.BOLD)} {colorize(cache_filename, Colors.CYAN)}")
                
                # Удаляем старые кэш-файлы
                keep_old = self.settings.get('keep_old_cache', 3)
                if len(cache_files) > keep_old:
                    for old_cache in cache_files[keep_old:]:
                        try:
                            os.remove(os.path.join(cache_dir, old_cache))
                        except:
                            pass
                
                return True
                
        except URLError as e:
            self.log(f"{colorize(EMOJI['error'], Colors.RED)} {colorize('Ошибка сети:', Colors.BOLD)} {colorize(str(e), Colors.RED)}")
            if cache_files:
                self.cache_file = os.path.join(cache_dir, cache_files[0])
                self.log(f"{colorize(EMOJI['warn'], Colors.YELLOW)} {colorize('Использую устаревший кэш', Colors.BOLD)}")
                return True
            return False
            
        except Exception as e:
            self.log(f"{colorize(EMOJI['error'], Colors.RED)} {colorize('Ошибка при загрузке данных:', Colors.BOLD)} {colorize(str(e), Colors.RED)}")
            return False
    
    def load_cached_data(self):
        """Загружает данные из кэш-файла"""
        if not self.cache_file or not os.path.exists(self.cache_file):
            return False
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.api_data = json.load(f)
            return True
        except Exception as e:
            self.log(f"{EMOJI['error']} Ошибка загрузки кэша: {e}")
            return False
    
    def show_cache_info(self):
        """Показывает информацию о кэше"""
        cache_dir = self.settings.get('cache_dir')
        
        print()
        print_separator()
        print(f"{colorize(EMOJI['chart'], Colors.MAGENTA)} {colorize('Информация о кэше:', Colors.BOLD + Colors.CYAN)}")
        print_separator()

        # Ищем самый свежий кэш
        cache_files = []
        for f in os.listdir(cache_dir):
            if f.startswith(CACHE_FILE_PREFIX) and f.endswith('.json'):
                cache_files.append(f)

        if cache_files:
            # Сортируем по дате в имени файла
            cache_files.sort(reverse=True)
            latest_cache = os.path.join(cache_dir, cache_files[0])

            try:
                file_size = os.path.getsize(latest_cache)
                file_mtime = os.path.getmtime(latest_cache)
                cache_age = datetime.now() - datetime.fromtimestamp(file_mtime)

                with open(latest_cache, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Получаем уникальные ОС
                os_list = sorted(set(item.get('os', '') for item in data))

                # Выводим с цветами
                print(f"{colorize('Файл:', Colors.BOLD)}        {colorize(os.path.basename(latest_cache), Colors.GREEN)}")
                print(f"{colorize('Размер:', Colors.BOLD)}      {colorize(human_size(file_size), Colors.CYAN)}")
                print(f"{colorize('Возраст:', Colors.BOLD)}     {colorize(f'{int(cache_age.total_seconds() / 3600)} ч {int((cache_age.total_seconds() % 3600) / 60)} мин', Colors.YELLOW)}")
                print(f"{colorize('Записей:', Colors.BOLD)}     {colorize(str(len(data)), Colors.GREEN)}")
                print(f"{colorize('Доступные ОС:', Colors.BOLD)} {colorize(', '.join(os_list), Colors.MAGENTA)}")
                print(f"{colorize('Хранится кэшей:', Colors.BOLD)} {colorize(str(len(cache_files)), Colors.CYAN)}")

            except Exception as e:
                print(f"{colorize(EMOJI['error'], Colors.RED)} {colorize('Ошибка чтения кэша:', Colors.BOLD)} {colorize(str(e), Colors.RED)}")
        else:
            print(f"{colorize(EMOJI['error'], Colors.RED)} {colorize('Кэш не найден', Colors.BOLD)}")

        print_separator()
    
    def get_unique_values(self, field, filters=None, show_progress=False):
        """Получает уникальные значения поля с фильтрацией"""
        if not self.api_data:
            return []

        values = set()
        total_items = len(self.api_data)

        for i, item in enumerate(self.api_data, 1):  # Начинаем с 1 для корректного процента
            # Применяем фильтры
            if filters:
                match = True
                for key, value in filters.items():
                    if item.get(key) != value:
                        match = False
                        break
                if not match:
                    continue

            value = item.get(field)
            if value:
                values.add(value)

            # Показываем прогресс если нужно
            if show_progress and HAS_COLOR and self.settings.get('show_progress', True) and (i % 100 == 0 or i == total_items):
                percent = (i / total_items) * 100
                filled = int(30 * i // total_items)
                bar = '█' * filled + '░' * (30 - filled)
                print(f"\r{colorize(EMOJI['search'], Colors.CYAN)} {colorize('Фильтрация:', Colors.BOLD)} [{colorize(bar, Colors.GREEN)}] {colorize(f'{percent:.1f}%', Colors.YELLOW)}", end='')

        if show_progress and HAS_COLOR and self.settings.get('show_progress', True):
            print()  # Новая строка после прогресс-бара

        return sorted(values)

    def interactive_setup(self):
        """Интерактивный выбор параметров установки"""
        print()
        print_separator()
        print(f"{colorize(EMOJI['rocket'], Colors.MAGENTA)} {colorize('Начинаем интерактивную установку', Colors.BOLD + Colors.CYAN)}")
        print_separator()
        
        # Шаг 1: Выбор ОС
        print_info("Получаю список операционных систем...")
        os_list = self.get_unique_values('os', show_progress=True)
        if not os_list:
            print_error("Нет данных об операционных системах")
            return None
        
        selected_os = select_option("Выберите операционную систему:", os_list)
        if not selected_os:
            print_info("Установка отменена")
            return None
        
        # Шаг 2: Выбор архитектуры
        print_info(f"Получаю список архитектур для {selected_os}...")
        arch_list = self.get_unique_values('architecture', {'os': selected_os})
        if not arch_list:
            print_error(f"Нет данных об архитектурах для {selected_os}")
            return None
        
        selected_arch = select_option(f"Выберите архитектуру для {selected_os}:", arch_list)
        if not selected_arch:
            print_info("Установка отменена")
            return None
        
        # Шаг 3: Выбор типа пакета
        print_info(f"Получаю список типов пакетов для {selected_os} {selected_arch}...")
        package_list = self.get_unique_values('packageType', 
                                            {'os': selected_os, 'architecture': selected_arch})
        if not package_list:
            print_error(f"Нет данных о типах пакетов")
            return None
        
        selected_package = select_option("Выберите тип пакета:", package_list)
        if not selected_package:
            print_info("Установка отменена")
            return None
        
        # Шаг 4: Выбор версии Java
        print_info(f"Получаю список версий Java для {selected_os} {selected_arch} {selected_package}...")
        version_list = self.get_unique_values('featureVersion',
                                            {'os': selected_os,
                                             'architecture': selected_arch,
                                             'packageType': selected_package})
        if not version_list:
            print_error("Нет доступных версий Java")
            return None
        
        # Форматируем для отображения
        version_display = [f"Java {v}" for v in version_list]
        
        print()
        print_separator()
        print(f"{colorize(EMOJI['select'], Colors.MAGENTA)} {colorize('Выберите версию Java:', Colors.BOLD + Colors.CYAN)}")
        print_separator()
        
        # Используем многоколоночный вывод для версий (если их много)
        if len(version_display) > 10:
            # Автоматически определяем количество колонок
            if len(version_display) <= 20:
                columns_for_versions = 2
            elif len(version_display) <= 40:
                columns_for_versions = 3
            else:
                columns_for_versions = 4
            
            # Выводим в колонках с номерами
            display_columns(version_display, columns=columns_for_versions, show_numbers=True)
        else:
            # Обычный вывод с номерами
            max_number = len(version_display)
            num_width = len(str(max_number))
            
            for i, version in enumerate(version_display, 1):
                num_str = colorize(str(i).rjust(num_width), Colors.YELLOW)
                print(f"{num_str} │ {colorize(version, Colors.CYAN)}")
        
        # Добавляем строку "Назад/Выход"
        max_number = len(version_display)
        num_width = len(str(max_number))
        zero_str = colorize('0'.rjust(num_width), Colors.YELLOW)
        print(f"{zero_str} │ {colorize('Назад/Выход', Colors.BOLD)}")
        
        print_separator()
        
        # Получаем выбор пользователя
        while True:
            try:
                max_choice = len(version_display)
                choice_prompt = f"Выберите номер [0-{max_choice}]: "
                choice = input(colorize(choice_prompt, Colors.BOLD))
                
                if choice == "0":
                    print_info("Установка отменена")
                    return None
                
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(version_display):
                        selected_version_display = version_display[idx]
                        break
                
                print_error(f"Неверный выбор. Введите число от 0 до {max_choice}")
            
            except (KeyboardInterrupt, EOFError):
                print()
                print_info("Установка отменена")
                return None
            except Exception as e:
                print_error(f"Ошибка: {e}")
                return None
        
        selected_version = selected_version_display.replace("Java ", "")
        
        # Шаг 5: Выбор типа бандла (lite, standard, full)
        print_info(f"Получаю список типов бандлов...")
        bundle_list = self.get_unique_values('bundleType',
                                           {'os': selected_os,
                                            'architecture': selected_arch,
                                            'packageType': selected_package,
                                            'featureVersion': int(selected_version)})
        if not bundle_list:
            # Если тип бандла не указан, используем "standard"
            bundle_list = ["standard"]
        
        selected_bundle = select_option("Выберите тип бандла:", bundle_list)
        if not selected_bundle:
            print_info("Установка отменена")
            return None
        
        # Шаг 6: Фильтруем релизы по всем критериям
        print_info(f"Получаю список релизов для Java {selected_version} {selected_bundle}...")
        releases = []
        for item in self.api_data:
            if (item.get('os') == selected_os and
                item.get('architecture') == selected_arch and
                item.get('packageType') == selected_package and
                item.get('featureVersion') == int(selected_version) and
                item.get('bundleType') == selected_bundle):
                
                releases.append(item)
        
        if not releases:
            print_error("Нет доступных релизов")
            return None
        
        # Сортируем релизы по версии (новые сначала)
        releases.sort(key=lambda x: x.get('version', ''), reverse=True)

        # Подготавливаем список для отображения
        max_releases = self.settings.get('max_releases_display', 20)
        release_options = []
        for release in releases[:max_releases]:
            version = release.get('version', '')
            filename = release.get('filename', '')
            size = release.get('size', 0)

            # Статус релиза
            status = []
            if release.get('LTS'):
                status.append(colorize("LTS", Colors.GREEN))
            if release.get('GA'):
                status.append(colorize("GA", Colors.BLUE))
            status_str = colorize(" | ".join(status), Colors.MAGENTA) if status else colorize("Stable", Colors.YELLOW)

            # Форматируем строку с фиксированными ширинами
            version_str = colorize(f"{version:<15}", Colors.CYAN)
            size_str = colorize(f"{human_size(size):>10}", Colors.YELLOW)
            file_str = colorize(filename, Colors.DIM)

            release_options.append(
                f"{version_str} | {size_str} | {status_str} | {file_str}"
            )

        selected_release_display = select_option("Выберите релиз:", release_options, trim_long_lines=False)
#        selected_release_display = select_release("Выберите релиз:", release_options)
        if not selected_release_display:
            print_info("Установка отменена")
            return None

        # Находим выбранный релиз
        selected_idx = release_options.index(selected_release_display)
        selected_release = releases[selected_idx]

        # Показываем выбранные параметры
        install_dir = self.settings.get('install_dir')
        print()
        print_separator()
        print(f"{colorize(EMOJI['select'], Colors.MAGENTA)} {colorize('Выбранные параметры:', Colors.BOLD + Colors.CYAN)}")
        print_separator()

        install_path = os.path.join(install_dir, 
                                  selected_release.get('filename', '').replace('.tar.gz', '').replace('.tgz', '').replace('.zip', ''))

        print(f"{colorize('ОС:', Colors.BOLD)}           {colorize(selected_os, Colors.GREEN)}")
        print(f"{colorize('Архитектура:', Colors.BOLD)}  {colorize(selected_arch, Colors.GREEN)}")
        print(f"{colorize('Тип пакета:', Colors.BOLD)}   {colorize(selected_package, Colors.GREEN)}")
        print(f"{colorize('Версия Java:', Colors.BOLD)}  {colorize(f'Java {selected_version}', Colors.CYAN)}")
        print(f"{colorize('Тип бандла:', Colors.BOLD)}   {colorize(selected_bundle, Colors.GREEN)}")
        print(f"{colorize('Релиз:', Colors.BOLD)}        {colorize(selected_release.get('version'), Colors.CYAN)}")
        print(f"{colorize('Файл:', Colors.BOLD)}         {colorize(selected_release.get('filename'), Colors.DIM)}")
        print(f"{colorize('Размер:', Colors.BOLD)}       {colorize(human_size(selected_release.get('size', 0)), Colors.YELLOW)}")
        print(f"{colorize('LTS:', Colors.BOLD)}          {colorize('✅ Да', Colors.GREEN) if selected_release.get('LTS') else colorize('❌ Нет', Colors.RED)}")
        print(f"{colorize('GA:', Colors.BOLD)}           {colorize('✅ Да', Colors.GREEN) if selected_release.get('GA') else colorize('❌ Нет', Colors.RED)}")

        sha1 = selected_release.get('sha1', '')
        if sha1:
            print(f"{colorize('SHA1:', Colors.BOLD)}         {colorize(sha1, Colors.MAGENTA)}")
        else:
            print(f"{colorize('SHA1:', Colors.BOLD)}         {colorize('Не указан', Colors.YELLOW)}")

        print(f"{colorize('Установка в:', Colors.BOLD)}  {colorize(install_path, Colors.BLUE)}")
        print_separator()

        return {
            'os': selected_os,
            'arch': selected_arch,
            'package_type': selected_package,
            'java_version': selected_version,
            'bundle_type': selected_bundle,
            'release': selected_release,
        }
    
    def download_file(self, url, filename, expected_size=None, expected_sha1=None):
        """Скачивает файл с прогресс-баром"""
        cache_dir = self.settings.get('cache_dir')
        download_path = os.path.join(cache_dir, "downloads", filename)
        os.makedirs(os.path.dirname(download_path), exist_ok=True)
        
        # Проверяем, существует ли уже файл
        if os.path.exists(download_path) and self.settings.get('download_resume', True):
            file_size = os.path.getsize(download_path)
            
            # Проверяем размер файла
            if expected_size and file_size == expected_size:
                self.log(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Файл уже существует:', Colors.BOLD)} {colorize(filename, Colors.GREEN)}")
                
                # Проверяем контрольную сумму если указана и включена проверка
                if expected_sha1 and self.settings.get('check_sha1', True):
                    self.log(f"{colorize(EMOJI['search'], Colors.CYAN)} {colorize('Проверяю контрольную сумму существующего файла...', Colors.BOLD)}")
                    sha1_hash = hashlib.sha1()
                    with open(download_path, 'rb') as f:
                        while True:
                            data = f.read(65536)
                            if not data:
                                break
                            sha1_hash.update(data)
                    
                    actual_sha1 = sha1_hash.hexdigest()
                    if actual_sha1.lower() == expected_sha1.lower():
                        self.log(f"{colorize(EMOJI['check'], Colors.GREEN)} {colorize('Контрольная сумма совпадает! Использую существующий файл.', Colors.BOLD)}")
                        self.log(f"{colorize(EMOJI['disk'], Colors.BLUE)} {colorize('Размер:', Colors.BOLD)} {colorize(human_size(file_size), Colors.GREEN)}")
                        return download_path
                    else:
                        self.log(f"{colorize(EMOJI['warn'], Colors.YELLOW)} {colorize('Контрольная сумма не совпадает. Перезаписываю файл.', Colors.BOLD)}")
                else:
                    # Если контрольная сумма не указана или проверка отключена, используем существующий файл
                    self.log(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Использую существующий файл.', Colors.BOLD)}")
                    self.log(f"{colorize(EMOJI['disk'], Colors.BLUE)} {colorize('Размер:', Colors.BOLD)} {colorize(human_size(file_size), Colors.GREEN)}")
                    return download_path
        
        self.log(f"{colorize(EMOJI['download'], Colors.BLUE)} {colorize('Скачиваю:', Colors.BOLD)} {colorize(filename, Colors.CYAN)}")
        self.log(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Источник:', Colors.BOLD)} {colorize(url, Colors.DIM)}")
        self.log(f"{colorize(EMOJI['folder'], Colors.BLUE)} {colorize('Сохраняю в:', Colors.BOLD)} {colorize(download_path, Colors.GREEN)}")

        try:
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            timeout = self.settings.get('timeout', REQUEST_TIMEOUT)

            with urlopen(req, timeout=timeout) as response:
                file_size = int(response.headers.get('Content-Length', 0))
                downloaded = 0
                start_time = time.time()
                last_update = 0

                with open(download_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        # Обновляем прогресс-бар
                        current_time = time.time()
                        show_progress = self.settings.get('show_progress', True)
                        if file_size > 0 and show_progress and (current_time - last_update > 0.1 or downloaded == file_size):
                            percent = (downloaded / file_size) * 100

                            # Создаём строковый прогресс-бар с цветами
                            if HAS_COLOR:
                                filled = int(30 * downloaded // file_size)
                                bar = colorize('█' * filled, Colors.GREEN) + colorize('░' * (30 - filled), Colors.DIM)

                                downloaded_str = colorize(human_size(downloaded), Colors.CYAN)
                                total_str = colorize(human_size(file_size), Colors.CYAN)

                                # Рассчитываем скорость
                                elapsed = current_time - start_time
                                if elapsed > 0:
                                    speed = downloaded / elapsed
                                    speed_str = colorize(human_size(speed), Colors.YELLOW)

                                    # Оставшееся время
                                    if downloaded > 0 and percent < 100:
                                        remaining = (file_size - downloaded) / speed
                                        if remaining < 60:
                                            eta = colorize(f"{remaining:.0f}сек", Colors.MAGENTA)
                                        elif remaining < 3600:
                                            eta = colorize(f"{remaining/60:.0f}мин", Colors.MAGENTA)
                                        else:
                                            eta = colorize(f"{remaining/3600:.1f}ч", Colors.MAGENTA)
                                    else:
                                        eta = ""

                                    percent_str = colorize(f"{percent:.1f}%", 
                                                         Colors.GREEN if percent > 50 else 
                                                         Colors.YELLOW if percent > 20 else 
                                                         Colors.RED)

                                    print(f"\r{colorize(EMOJI['download'], Colors.BLUE)} [{bar}] {percent_str} | {downloaded_str}/{total_str} | {speed_str}/сек {eta}", end='')

                            last_update = current_time

                if file_size > 0 and HAS_COLOR and show_progress:
                    print()  # Новая строка после прогресс-бара

                download_time = time.time() - start_time

                # Проверяем размер
                actual_size = os.path.getsize(download_path)
                if expected_size and actual_size != expected_size:
                    self.log(f"{colorize(EMOJI['warn'], Colors.YELLOW)} {colorize('Размер файла не совпадает:', Colors.BOLD)} "
                            f"ожидалось {colorize(human_size(expected_size), Colors.CYAN)}, "
                            f"получено {colorize(human_size(actual_size), Colors.CYAN)}")

                # Проверяем SHA1 если включено
                if expected_sha1 and self.settings.get('check_sha1', True):
                    self.log(f"{colorize(EMOJI['search'], Colors.CYAN)} {colorize('Проверяю контрольную сумму...', Colors.BOLD)}")
                    sha1_hash = hashlib.sha1()
                    with open(download_path, 'rb') as f:
                        while True:
                            data = f.read(65536)
                            if not data:
                                break
                            sha1_hash.update(data)

                    actual_sha1 = sha1_hash.hexdigest()
                    if actual_sha1.lower() != expected_sha1.lower():
                        self.log(f"{colorize(EMOJI['error'], Colors.RED)} {colorize('Контрольная сумма не совпадает!', Colors.BOLD)}")
                        self.log(f"  {colorize('Ожидалось:', Colors.BOLD)} {colorize(expected_sha1, Colors.RED)}")
                        self.log(f"  {colorize('Получено:', Colors.BOLD)}  {colorize(actual_sha1, Colors.RED)}")
                        os.remove(download_path)
                        return None

                self.log(f"{colorize(EMOJI['check'], Colors.GREEN)} {colorize('Файл успешно скачан:', Colors.BOLD)} {colorize(filename, Colors.CYAN)}")
                self.log(f"{colorize(EMOJI['clock'], Colors.YELLOW)} {colorize('Время загрузки:', Colors.BOLD)} {colorize(f'{download_time:.1f} сек', Colors.CYAN)}")
                self.log(f"{colorize(EMOJI['disk'], Colors.BLUE)} {colorize('Размер:', Colors.BOLD)} {colorize(human_size(actual_size), Colors.GREEN)}")

                return download_path

        except Exception as e:
            self.log(f"{colorize(EMOJI['error'], Colors.RED)} {colorize('Ошибка загрузки:', Colors.BOLD)} {colorize(str(e), Colors.RED)}")
            if os.path.exists(download_path):
                os.remove(download_path)
            return None

    def add_to_shell_config(self, install_path, latest_link=None):
        """Предлагает автоматически добавить Java в конфигурацию shell"""
        print()
        print_separator()
        print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Автоматическая настройка shell:', Colors.BOLD + Colors.BLUE)}")
        print_separator()
        
        shell_configs = []
        
        # Проверяем существующие конфиги
        bashrc = os.path.expanduser("~/.bashrc")
        zshrc = os.path.expanduser("~/.zshrc")
        profile = os.path.expanduser("~/.profile")
        
        if os.path.exists(bashrc):
            shell_configs.append(("Bash", bashrc))
        if os.path.exists(zshrc):
            shell_configs.append(("Zsh", zshrc))
        if os.path.exists(profile):
            shell_configs.append(("Profile", profile))
        
        if shell_configs:
            print(f"{colorize('Найдены конфигурационные файлы:', Colors.BOLD)}")
            for name, path in shell_configs:
                print(f"  {colorize(name + ':', Colors.GREEN)} {colorize(path, Colors.CYAN)}")
            
            print()
            # Предлагаем добавить во все найденные конфиги
            for name, config_path in shell_configs:
                choice = input(f"{colorize(f'Добавить Java в {name} ({os.path.basename(config_path)})? [y/N]: ', Colors.BOLD)}").lower()
                
                if choice == 'y':
                    # Определяем, использовать ли ссылку latest
                    use_latest = self.settings.get('prefer_latest_link', True)
                    java_home_path = latest_link if use_latest and latest_link and os.path.exists(latest_link) else install_path
                    
                    # Проверяем, не добавлена ли уже Java
                    try:
                        with open(config_path, 'r') as f:
                            content = f.read()
                            
                        if f'JAVA_HOME="{install_path}"' in content or (latest_link and f'JAVA_HOME="{latest_link}"' in content):
                            print_info(f"Java уже настроена в {config_path}")
                            continue
                    except:
                        pass
                    
                    # Добавляем настройки
                    java_config = '\n' + format_java_env_config(install_path, latest_link if use_latest else None) + '\n'
                    
                    try:
                        with open(config_path, 'a') as f:
                            f.write(java_config)
                        print_success(f"Java добавлена в {config_path}")
                        print_info(f"Перезагрузите терминал или выполните:")
                        print(f"  {colorize('source ' + config_path, Colors.YELLOW)}")
                    except Exception as e:
                        print_error(f"Не удалось записать в {config_path}: {e}")
        else:
            print_info("Конфигурационные файлы shell не найдены")
            print_info(f"Создайте ~/.bashrc или ~/.zshrc и добавьте строки:")
            print(f"  {format_java_home_cmd(install_path, Colors.GREEN)}")
            print(f"  {format_java_path_cmd(None, Colors.GREEN)}")
        
        print_separator()

    def install_package(self, selection):
        """Устанавливает выбранный пакет"""
        release = selection['release']
        filename = release.get('filename')
        url = release.get('downloadUrl')
        size = release.get('size')
        sha1 = release.get('sha1')
        
        if not url or not filename:
            print_error("Некорректные данные релиза")
            return False
        
        # Скачиваем файл
        downloaded_file = self.download_file(url, filename, size, sha1)
        if not downloaded_file:
            return False
        
        # Определяем тип установки
        package_type = selection['package_type']
        os_type = selection['os']
        
        print()
        print_separator()
        print(f"{colorize(EMOJI['hammer'], Colors.MAGENTA)} {colorize('Установка Java', Colors.BOLD + Colors.CYAN)}")
        print_separator()
        
        try:
            if package_type == 'tar.gz':
                # Распаковка tar.gz
                print_info(f"Распаковываю {filename}...")
                
                install_dir = self.settings.get('install_dir')
                # Убеждаемся, что директория установки существует
                os.makedirs(install_dir, exist_ok=True)
                
                # Определяем базовое имя папки из архива
                with tarfile.open(downloaded_file, 'r:gz') as tar:
                    # Получаем первую директорию в архиве
                    first_member = tar.next()
                    while first_member and not first_member.isdir():
                        first_member = tar.next()
                    
                    if first_member:
                        archive_root_dir = first_member.name.split('/')[0]
                        install_path = os.path.join(install_dir, archive_root_dir)
                    else:
                        # Если не удалось определить корневую папку, используем имя файла
                        base_name = filename.replace('.tar.gz', '').replace('.tgz', '')
                        install_path = os.path.join(install_dir, base_name)
                
                # Если папка уже существует, удаляем её рекурсивно
                if os.path.exists(install_path):
                    print_warning(f"Папка {os.path.basename(install_path)} уже существует. Удаляю...")
                    try:
                        shutil.rmtree(install_path)
                        print_success(f"Папка удалена: {install_path}")
                    except PermissionError as e:
                        print_error(f"Не удалось удалить папку: {e}")
                        print_info("Попробуйте удалить её вручную:")
                        print_info(f"  rm -rf {install_path}")
                        return False
                    except Exception as e:
                        print_error(f"Ошибка при удалении папки: {e}")
                        return False
                
                # Теперь распаковываем архив
                with tarfile.open(downloaded_file, 'r:gz') as tar:
                    # Извлекаем все файлы
                    tar.extractall(install_dir)
                    print_success(f"Java распакована в: {colorize(install_path, Colors.GREEN)}")
                
                # Проверяем, что извлечение прошло успешно
                if os.path.exists(install_path):
                    # Считаем количество файлов
                    file_count = 0
                    for root, dirs, files in os.walk(install_path):
                        file_count += len(files)
                    
                    print_info(f"Установлено файлов: {colorize(str(file_count), Colors.CYAN)}")
                else:
                    print_error(f"Папка не найдена после распаковки: {install_path}")
                    return False
                
                # Создаём символическую ссылку на последнюю версию
                latest_link = os.path.join(install_dir, "latest")
                
                # Если ссылка уже существует, удаляем её
                if os.path.exists(latest_link):
                    try:
                        if os.path.islink(latest_link):
                            os.unlink(latest_link)
                            print_info(f"Удалена старая символическая ссылка: {latest_link}")
                        elif os.path.isdir(latest_link):
                            shutil.rmtree(latest_link)
                            print_info(f"Удалена старая директория: {latest_link}")
                        else:
                            os.remove(latest_link)
                            print_info(f"Удалён старый файл: {latest_link}")
                    except Exception as e:
                        print_warning(f"Не удалось удалить старую ссылку {latest_link}: {e}")
                
                try:
                    # Создаём относительную ссылку
                    rel_path = os.path.relpath(install_path, os.path.dirname(latest_link))
                    os.symlink(rel_path, latest_link)
                    print_info(f"Создана ссылка: {colorize('latest', Colors.BLUE)} → {colorize(rel_path, Colors.CYAN)}")
                except Exception as e:
                    print_warning(f"Не удалось создать символическую ссылку: {e}")
                
                # Добавляем команду для PATH
                print()
                print_separator()
                print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Настройка окружения Java:', Colors.BOLD + Colors.BLUE)}")
                print_separator()
                
                java_bin_path = os.path.join(install_path, 'bin')
                
                # Инструкции для bash (~/.bashrc)
                print(f"{colorize('🐚 Для Bash (~/.bashrc):', Colors.BOLD)}")
                print(f"  {colorize('# Добавьте эти строки в конец файла', Colors.DIM)}")
                print(f"  {format_java_home_cmd(install_path, Colors.GREEN)}")
                print(f"  {format_java_path_cmd(None, Colors.GREEN)}")
                
                # Инструкции для zsh (~/.zshrc)
                print()
                print(f"{colorize('🐚 Для Zsh (~/.zshrc):', Colors.BOLD)}")
                print(f"  {colorize('# Добавьте эти строки в конец файла', Colors.DIM)}")
                print(f"  {format_java_home_cmd(install_path, Colors.GREEN)}")
                print(f"  {format_java_path_cmd(None, Colors.GREEN)}")
                
                if os.path.exists(latest_link):
                    print()
                    print(f"{colorize('🎯 Использование ссылки latest (рекомендуется):', Colors.BOLD)}")
                    print(f"  {format_java_home_cmd(latest_link, Colors.CYAN)}")
                    print(f"  {format_java_path_cmd(None, Colors.CYAN)}")
                    print(f"  {colorize('# Это автоматически переключится при обновлении Java', Colors.DIM)}")
                
                # Для текущей сессии
                print()
                print_separator()
                print(f"{colorize('⚡ Для использования в текущей сессии:', Colors.BOLD)}")
                print(f"{colorize('Выполните команды:', Colors.DIM)}")
                print(f"  {format_java_home_cmd(install_path, Colors.YELLOW)}")
                print(f"  {format_java_path_cmd(None, Colors.YELLOW)}")
                
                # Команда для быстрой активации
                print()
                print(f"{colorize('🚀 Быстрая активация (Bash/Zsh):', Colors.BOLD)}")
                # Используем format для избежания проблем с кавычками
                cmd = 'eval "$(echo \'export JAVA_HOME={}\'; echo \'export PATH={}:$PATH\')"'.format(install_path, java_bin_path)
                print(f"  {colorize(cmd, Colors.MAGENTA)}")
                
                # Показываем команду для проверки
                print()
                print(f"{colorize('🔍 Проверьте установку:', Colors.BOLD)}")
                print(f"  {colorize('java --version', Colors.CYAN)}")
                print(f"  {colorize('javac --version', Colors.CYAN)}")
                print(f"  {colorize('echo $JAVA_HOME', Colors.CYAN)}")
                print_separator()

                # Предлагаем автоматическую настройку
                print()
                choice = input(f"{colorize('Добавить Java в конфигурацию shell автоматически? [y/N]: ', Colors.BOLD)}").lower()
                if choice == 'y':
                    latest_link_exists = os.path.exists(latest_link) if 'latest_link' in locals() else False
                    self.add_to_shell_config(
                        install_path, 
                        latest_link if latest_link_exists else None
                    )

                return True
                
            elif package_type == 'zip':
                # Распаковка zip
                print_info(f"Распаковываю {filename}...")
                
                install_dir = self.settings.get('install_dir')
                # Убеждаемся, что директория установки существует
                os.makedirs(install_dir, exist_ok=True)
                
                # Определяем корневую папку из архива
                with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                    # Получаем первую папку в архиве
                    first_member = zip_ref.namelist()[0] if zip_ref.namelist() else ''
                    if '/' in first_member:
                        archive_root_dir = first_member.split('/')[0]
                    else:
                        archive_root_dir = os.path.splitext(filename)[0]
                    
                    install_path = os.path.join(install_dir, archive_root_dir)
                
                # Если папка уже существует, удаляем её рекурсивно
                if os.path.exists(install_path):
                    print_warning(f"Папка {os.path.basename(install_path)} уже существует. Удаляю...")
                    try:
                        shutil.rmtree(install_path)
                        print_success(f"Папка удалена: {install_path}")
                    except PermissionError as e:
                        print_error(f"Не удалось удалить папку: {e}")
                        print_info("Попробуйте удалить её вручную:")
                        print_info(f"  rm -rf {install_path}")
                        return False
                    except Exception as e:
                        print_error(f"Ошибка при удалении папки: {e}")
                        return False
                
                # Распаковываем архив
                with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                    # Создаём все директории перед извлечением
                    for member in zip_ref.namelist():
                        member_path = os.path.join(install_dir, member)
                        if member.endswith('/'):  # Это директория
                            os.makedirs(member_path, exist_ok=True)
                    
                    # Извлекаем файлы
                    zip_ref.extractall(install_dir)
                
                print_success(f"Java распакована в: {colorize(install_path, Colors.GREEN)}")
                
                # Проверяем, что извлечение прошло успешно
                if os.path.exists(install_path):
                    # Считаем количество файлов
                    file_count = 0
                    for root, dirs, files in os.walk(install_path):
                        file_count += len(files)
                    
                    print_info(f"Установлено файлов: {colorize(str(file_count), Colors.CYAN)}")
                else:
                    print_error(f"Папка не найдена после распаковки: {install_path}")
                    # Ищем вновь созданные папки
                    print_info("Ищу вновь созданные папки...")
                    new_dirs = []
                    for item in os.listdir(install_dir):
                        item_path = os.path.join(install_dir, item)
                        if os.path.isdir(item_path):
                            dir_mtime = os.path.getmtime(item_path)
                            if time.time() - dir_mtime < 10:  # Папка создана менее 10 секунд назад
                                new_dirs.append((item_path, dir_mtime))
                    
                    if new_dirs:
                        # Берём самую свежую папку
                        new_dirs.sort(key=lambda x: x[1], reverse=True)
                        install_path = new_dirs[0][0]
                        print_success(f"Java распакована в: {colorize(install_path, Colors.GREEN)}")
                    else:
                        print_error("Не удалось найти распакованные файлы")
                        return False
                
                # Создаём символическую ссылку на последнюю версию
                latest_link = os.path.join(install_dir, "latest")
                if os.path.exists(latest_link):
                    try:
                        if os.path.islink(latest_link):
                            os.unlink(latest_link)
                        else:
                            shutil.rmtree(latest_link)
                        print_info(f"Удалена старая ссылка: {latest_link}")
                    except Exception as e:
                        print_warning(f"Не удалось удалить старую ссылку: {e}")
                
                try:
                    # Создаём относительную ссылку
                    rel_path = os.path.relpath(install_path, install_dir)
                    os.symlink(rel_path, latest_link)
                    print_info(f"Создана ссылка: {colorize('latest', Colors.BLUE)} → {colorize(rel_path, Colors.CYAN)}")
                except Exception as e:
                    print_warning(f"Не удалось создать символическую ссылку: {e}")
                
                # Добавляем команду для PATH
                print()
                print_separator()
                print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Для использования Java добавьте в PATH:', Colors.BOLD)}")
                java_bin_path = os.path.join(install_path, 'bin')
                print(f"  {format_path_cmd(java_bin_path, Colors.GREEN)}")
                
                if os.path.exists(latest_link):
                    latest_bin_path = os.path.join(latest_link, 'bin')
                    print(f"  {colorize('или используйте символическую ссылку:', Colors.DIM)}")
                    print(f"  {format_path_cmd(latest_bin_path, Colors.GREEN)}")
                
                # Показываем команду для текущей сессии
                print()
                print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Для использования в текущей сессии:', Colors.BOLD)}")
                cmd = f'source <(echo "export PATH={java_bin_path}:$PATH")'
                print(f"  {colorize(cmd, Colors.YELLOW)}")
                print_separator()

                # Предлагаем автоматическую настройку
                print()
                choice = input(f"{colorize('Добавить Java в конфигурацию shell автоматически? [y/N]: ', Colors.BOLD)}").lower()
                if choice == 'y':
                    latest_link_exists = os.path.exists(latest_link) if 'latest_link' in locals() else False
                    self.add_to_shell_config(
                        install_path, 
                        latest_link if latest_link_exists else None
                    )

                return True
                
            elif package_type == 'deb' and os_type == 'linux':
                # Установка DEB пакета
                print_info(f"Устанавливаю DEB пакет...")
                
                # Создаём временную директорию для извлечения deb
                temp_dir = tempfile.mkdtemp()
                try:
                    # Извлекаем deb пакет для просмотра содержимого
                    subprocess.run(['dpkg', '-x', downloaded_file, temp_dir], 
                                 capture_output=True, text=True, check=True)
                    
                    # Ищем путь к Java
                    java_paths = []
                    for root, dirs, files in os.walk(temp_dir):
                        if 'bin' in dirs and 'java' in os.listdir(os.path.join(root, 'bin')):
                            java_paths.append(root)
                    
                    if java_paths:
                        install_path = java_paths[0]
                        print_info(f"Java будет установлена в системные директории")
                        print_info(f"Основная папка: {install_path}")
                    
                except Exception as e:
                    print_warning(f"Не удалось проанализировать DEB пакет: {e}")
                    install_path = "/usr/lib/jvm"
                
                # Устанавливаем пакет
                result = subprocess.run(['sudo', 'dpkg', '-i', downloaded_file],
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print_success("DEB пакет успешно установлен")
                    
                    # Показываем информацию о PATH
                    print()
                    print_separator()
                    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Java установлена в системные директории', Colors.BOLD)}")
                    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Обычно она уже добавлена в PATH автоматически', Colors.BOLD)}")
                    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Проверьте версию:', Colors.BOLD)}")
                    print(f"  {colorize('java --version', Colors.GREEN)}")
                    print_separator()
                    
                    return True
                else:
                    print_error(f"Ошибка установки DEB пакета: {result.stderr}")
                    
                    # Если ошибка из-за зависимостей, предлагаем исправить
                    if "dependency" in result.stderr.lower():
                        print_info("Попробуйте установить зависимости:")
                        print(f"  {colorize('sudo apt --fix-broken install', Colors.YELLOW)}")
                    
                    return False
                    
            elif package_type == 'rpm' and os_type == 'linux':
                # Установка RPM пакета
                print_info(f"Устанавливаю RPM пакет...")
                
                # Создаём временную директорию для извлечения rpm
                temp_dir = tempfile.mkdtemp()
                try:
                    # Извлекаем rpm пакет для просмотра содержимого
                    subprocess.run(['rpm2cpio', downloaded_file], 
                                 stdout=subprocess.PIPE).stdout
                    
                    print_info(f"Java будет установлена в системные директории")
                    
                except Exception as e:
                    print_warning(f"Не удалось проанализировать RPM пакет: {e}")
                
                # Устанавливаем пакет
                result = subprocess.run(['sudo', 'rpm', '-i', '--nodeps', downloaded_file],
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print_success("RPM пакет успешно установлен")
                    
                    # Показываем информацию о PATH
                    print()
                    print_separator()
                    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Java установлена в системные директории', Colors.BOLD)}")
                    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Обычно она уже добавлена в PATH автоматически', Colors.BOLD)}")
                    print(f"{colorize(EMOJI['info'], Colors.CYAN)} {colorize('Проверьте версию:', Colors.BOLD)}")
                    print(f"  {colorize('java --version', Colors.GREEN)}")
                    print_separator()
                    
                    return True
                else:
                    print_error(f"Ошибка установки RPM пакета: {result.stderr}")
                    return False
                    
            elif package_type == 'msi' and os_type == 'windows':
                # Установка MSI пакета (требует Windows)
                print_info(f"Запускаю установщик MSI...")
                result = subprocess.run(['msiexec', '/i', downloaded_file, '/quiet'],
                                      capture_output=True, text=True)
                
                if result.returncode == 0:
                    print_success("MSI пакет успешно установлен")
                    return True
                else:
                    print_error(f"Ошибка установки MSI пакета: {result.stderr}")
                    return False
            
            else:
                print_warning(f"Тип пакета {package_type} требует ручной установки")
                print_info(f"Файл скачан: {downloaded_file}")
                install_dir = self.settings.get('install_dir')
                print_info(f"Установите его вручную в: {install_dir}")

                return True
                
        except Exception as e:
            print_error(f"Ошибка установки: {e}")
            return False
    
    def cleanup_old_files(self):
        """Очищает старые файлы"""
        cleanup_days = self.settings.get('cleanup_days', 7)
        cache_dir = self.settings.get('cache_dir')
        
        print_info(f"Очищаю старые файлы (старше {cleanup_days} дней)...")
        
        try:
            cutoff_time = time.time() - (cleanup_days * 24 * 3600)
            deleted_count = 0
            kept_count = 0
            
            # Очищаем загрузки
            downloads_dir = os.path.join(cache_dir, "downloads")
            if os.path.exists(downloads_dir):
                for f in os.listdir(downloads_dir):
                    file_path = os.path.join(downloads_dir, f)
                    if os.path.isfile(file_path):
                        if os.path.getmtime(file_path) < cutoff_time:
                            try:
                                os.remove(file_path)
                                deleted_count += 1
                                self.log(f"Удалён старый файл загрузки: {f}")
                            except Exception as e:
                                print_warning(f"Не удалось удалить {file_path}: {e}")
                        else:
                            kept_count += 1
            
            # Очищаем старые логи, если они слишком большие
            log_file = os.path.join(cache_dir, "installer.log")
            if os.path.exists(log_file):
                log_size = os.path.getsize(log_file)
                log_mtime = os.path.getmtime(log_file)
                
                # Очищаем если лог старше установленного времени ИЛИ если он слишком большой (>10MB)
                if log_mtime < cutoff_time or log_size > 10 * 1024 * 1024:
                    try:
                        # Вместо полной очистки, сохраняем только последние 1000 строк
                        with open(log_file, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        
                        if len(lines) > 1000:
                            # Сохраняем только последние 1000 строк
                            with open(log_file, 'w', encoding='utf-8') as f:
                                f.writelines(lines[-1000:])
                            print_info(f"Лог сокращён с {len(lines)} до 1000 строк")
                            self.log("Лог был сокращён в процессе очистки")
                    except Exception as e:
                        print_warning(f"Не удалось обработать лог: {e}")
            
            # Очищаем старые кэши API
            cache_files = []
            for f in os.listdir(cache_dir):
                if f.startswith(CACHE_FILE_PREFIX) and f.endswith('.json'):
                    try:
                        file_path = os.path.join(cache_dir, f)
                        file_mtime = os.path.getmtime(file_path)
                        cache_files.append((f, file_mtime))
                    except Exception as e:
                        print_warning(f"Не удалось обработать файл кэша {f}: {e}")
            
            if cache_files:
                # Сортируем по дате (новые сначала)
                cache_files.sort(key=lambda x: x[1], reverse=True)
                
                keep_old = self.settings.get('keep_old_cache', 3)
                print_info(f"Храню {keep_old} последних кэшей...")
                
                for i, (filename, file_mtime) in enumerate(cache_files):
                    file_path = os.path.join(cache_dir, filename)
                    
                    if i < keep_old:
                        # Оставляем первые N файлов
                        kept_count += 1
                    elif file_mtime < cutoff_time:
                        # Удаляем если старый
                        try:
                            os.remove(file_path)
                            deleted_count += 1
                            self.log(f"Удалён старый кэш: {filename}")
                        except Exception as e:
                            print_warning(f"Не удалось удалить кэш {filename}: {e}")
                    else:
                        # Не удаляем, если файл не слишком старый
                        kept_count += 1
            
            # Очищаем старые настройки бэкапы, если они есть
            settings_backup_pattern = "settings-backup-*.json"
            for backup_file in glob.glob(os.path.join(cache_dir, settings_backup_pattern)):
                try:
                    if os.path.getmtime(backup_file) < cutoff_time:
                        os.remove(backup_file)
                        deleted_count += 1
                except Exception:
                    pass
            
            # Показываем результат
            print_separator()
            print_success(f"Очистка завершена!")
            print_info(f"Удалено файлов: {colorize(str(deleted_count), Colors.RED if deleted_count > 0 else Colors.GREEN)}")
            print_info(f"Оставлено файлов: {colorize(str(kept_count), Colors.GREEN)}")
            
            # Если было удалено много файлов, показываем подсказку
            if deleted_count > 0:
                current_cache_size = 0
                try:
                    for root, dirs, files in os.walk(cache_dir):
                        for f in files:
                            fp = os.path.join(root, f)
                            current_cache_size += os.path.getsize(fp)
                    
                    print_info(f"Текущий размер кэша: {colorize(human_size(current_cache_size), Colors.CYAN)}")
                except Exception:
                    pass
                
            print_separator()
            
        except Exception as e:
            print_error(f"Ошибка очистки: {e}")
            import traceback
            self.log(f"Ошибка в cleanup_old_files: {e}\n{traceback.format_exc()}")
    
    def show_settings_menu(self):
        """Меню настроек"""
        while True:
            clear_screen()
            print()
            print_separator()
            print(f"{colorize(EMOJI['gear'], Colors.MAGENTA)} {colorize('Настройки', Colors.BOLD + Colors.CYAN)}")
            print_separator()
            
            # Получаем все настройки
            all_settings = self.settings.get_all()
            setting_keys = list(all_settings.keys())
            
            # Отображаем настройки
            for i, key in enumerate(setting_keys, 1):
                display_name = self.settings.get_display_name(key)
                value = self.settings.format_value(key, all_settings[key])
                print(f"{colorize(str(i), Colors.YELLOW)}. {colorize(display_name, Colors.GREEN)}: {value}")
            
            print()
            print(f"{colorize('R', Colors.YELLOW)}. {colorize(EMOJI['reset'], Colors.MAGENTA)} {colorize('Сбросить к настройкам по умолчанию', Colors.BOLD)}")
            print(f"{colorize('S', Colors.YELLOW)}. {colorize(EMOJI['save'], Colors.BLUE)} {colorize('Сохранить и выйти', Colors.BOLD)}")
            print(f"{colorize('0', Colors.YELLOW)}. {colorize('Назад', Colors.BOLD)}")
            print_separator()
            
            try:
                choice = input(colorize("Выберите действие [1-" + str(len(setting_keys)) + ", R, S, 0]: ", Colors.BOLD)).lower()
                
                if choice == '0':
                    return True
                elif choice == 'r':
                    print()
                    confirm = input(colorize("Сбросить все настройки к значениям по умолчанию? [y/N]: ", Colors.BOLD)).lower()
                    if confirm == 'y':
                        if self.settings.reset_to_defaults():
                            print_success("Настройки сброшены к значениям по умолчанию")
                            # Обновляем глобальные переменные
                            # Вместо global объявления просто обновляем через globals()
                            globals()['HAS_COLOR'] = self.settings.get('show_colors') and sys.stdout.isatty()
                            time.sleep(1)
                    continue
                elif choice == 's':
                    if self.settings.save_settings():
                        print_success("Настройки сохранены")
                        time.sleep(1)
                    return True
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(setting_keys):
                        key = setting_keys[idx]
                        current_value = all_settings[key]
                        display_name = self.settings.get_display_name(key)
                        
                        print()
                        print_separator()
                        print(f"{colorize(EMOJI['gear'], Colors.MAGENTA)} {colorize('Изменение настройки:', Colors.BOLD + Colors.CYAN)}")
                        print_separator()
                        print(f"{colorize('Название:', Colors.BOLD)} {colorize(display_name, Colors.GREEN)}")
                        print(f"{colorize('Текущее значение:', Colors.BOLD)} {self.settings.format_value(key, current_value)}")
                        print_separator()
                        
                        # В зависимости от типа значения предлагаем разный ввод
                        if isinstance(current_value, bool):
                            new_value_str = input(f"{colorize('Новое значение [y/n]: ', Colors.BOLD)}").lower()
                            new_value = new_value_str == 'y'
                        elif isinstance(current_value, int):
                            try:
                                new_value_str = input(f"{colorize('Новое значение (число): ', Colors.BOLD)}")
                                new_value = int(new_value_str)
                            except ValueError:
                                print_error("Некорректное число")
                                input("Нажмите Enter для продолжения...")
                                continue
                        else:
                            new_value_str = input(f"{colorize('Новое значение: ', Colors.BOLD)}").strip()
                            new_value = new_value_str if new_value_str else current_value
                        
                        # Валидация для определенных настроек
                        if key == 'cleanup_days' and new_value < 0:
                            print_error("Количество дней не может быть отрицательным")
                            input("Нажмите Enter для продолжения...")
                            continue
                        elif key == 'timeout' and new_value < 1:
                            print_error("Таймаут должен быть не менее 1 секунды")
                            input("Нажмите Enter для продолжения...")
                            continue
                        elif key == 'keep_old_cache' and new_value < 1:
                            print_error("Должен храниться хотя бы 1 кэш")
                            input("Нажмите Enter для продолжения...")
                            continue
                        
                        # Применяем изменения
                        if self.settings.set(key, new_value):
                            print_success(f"Настройка изменена: {display_name}")
                            
                            # Особые обработки для некоторых настроек
                            if key == 'show_colors':
                                # Обновляем глобальную переменную
                                globals()['HAS_COLOR'] = new_value and sys.stdout.isatty()
                                print_info("Изменения цвета вступят в силу после перезапуска меню")
                            
                            time.sleep(1)
                        else:
                            print_error("Не удалось изменить настройку")
                            time.sleep(1)
                    
                else:
                    print_error("Неверный выбор")
                    time.sleep(1)
            
            except KeyboardInterrupt:
                return False
            except Exception as e:
                print_error(f"Ошибка: {e}")
                time.sleep(2)

    def show_log_menu(self):
        """Меню просмотра лога"""
        log_file = os.path.join(self.settings.get('cache_dir'), "installer.log")
        
        while True:
            clear_screen()
            print()
            print_separator()
            print(f"{colorize(EMOJI['info'], Colors.MAGENTA)} {colorize('Просмотр лога', Colors.BOLD + Colors.CYAN)}")
            print_separator()
            
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    # Показываем последние 30 строк
                    start_idx = max(0, len(lines) - 30)
                    for i in range(start_idx, len(lines)):
                        print(lines[i].rstrip())
                    
                    print_separator()
                    print(f"{colorize('Всего строк:', Colors.BOLD)} {colorize(str(len(lines)), Colors.GREEN)}")
                    print(f"{colorize('Показано:', Colors.BOLD)} {colorize(str(len(lines) - start_idx), Colors.CYAN)}")
                    
                except Exception as e:
                    print_error(f"Ошибка чтения лога: {e}")
            else:
                print_error("Лог-файл не найден")
            
            print_separator()
            print(f"{colorize('1', Colors.YELLOW)}. {colorize('Очистить лог', Colors.BOLD)}")
            print(f"{colorize('0', Colors.YELLOW)}. {colorize('Назад', Colors.BOLD)}")
            print_separator()
            
            try:
                choice = input(colorize("Выберите действие [1, 0]: ", Colors.BOLD))
                
                if choice == '0':
                    return
                elif choice == '1':
                    confirm = input(colorize("Очистить весь лог? [y/N]: ", Colors.BOLD)).lower()
                    if confirm == 'y':
                        try:
                            with open(log_file, 'w') as f:
                                f.write('')
                            print_success("Лог очищен")
                        except Exception as e:
                            print_error(f"Не удалось очистить лог: {e}")
                        time.sleep(1)
                else:
                    print_error("Неверный выбор")
                    time.sleep(1)
            
            except KeyboardInterrupt:
                return
            except Exception as e:
                print_error(f"Ошибка: {e}")
                time.sleep(2)
    
    def main_menu(self):
        """Главное меню"""
        while True:
            clear_screen()
            print()
            print_separator()
            print(f"{colorize('🚀 BellSoft Java Universal Installer', Colors.BOLD + Colors.CYAN)}")
            print_separator()
            print(f"1. {colorize(EMOJI['rocket'], Colors.GREEN)} {colorize('Установить Java (интерактивный выбор)', Colors.BOLD)}")
            print(f"2. {colorize(EMOJI['download'], Colors.BLUE)} {colorize('Обновить кэш данных', Colors.BOLD)}")
            print(f"3. {colorize(EMOJI['chart'], Colors.MAGENTA)} {colorize('Показать информацию о кэше', Colors.BOLD)}")
            print(f"4. {colorize(EMOJI['trash'], Colors.YELLOW)} {colorize('Очистить старые файлы', Colors.BOLD)}")
            print(f"5. {colorize(EMOJI['info'], Colors.CYAN)} {colorize('Показать лог операций', Colors.BOLD)}")
            print(f"6. {colorize(EMOJI['gear'], Colors.MAGENTA)} {colorize('Настройки', Colors.BOLD)}")
            print(f"0. {colorize(EMOJI['check'], Colors.GREEN)} {colorize('Выход', Colors.BOLD)}")
            print_separator()
            
            try:
                choice = input(colorize("Выберите действие [0-6]: ", Colors.BOLD))
                
                if choice == "1":
                    # Интерактивная установка
                    if not self.load_cached_data():
                        if not self.fetch_api_data():
                            input("Нажмите Enter для продолжения...")
                            continue
                    
                    selection = self.interactive_setup()
                    if selection:
                        print()
                        confirm = input("Начать установку? [y/N]: ").lower()
                        if confirm == 'y':
                            if self.install_package(selection):
                                print_success("Установка завершена успешно!")
                            else:
                                print_error("Установка не удалась")
                        
                        input("Нажмите Enter для продолжения...")
                
                elif choice == "2":
                    # Обновление кэша
                    if self.fetch_api_data(force=True):
                        print_success("Кэш успешно обновлён")
                    else:
                        print_error("Не удалось обновить кэш")
                    input("Нажмите Enter для продолжения...")
                
                elif choice == "3":
                    # Информация о кэше
                    self.show_cache_info()
                    input("Нажмите Enter для продолжения...")
                
                elif choice == "4":
                    # Очистка
                    self.cleanup_old_files()
                    input("Нажмите Enter для продолжения...")
                
                elif choice == "5":
                    # Показать лог
                    self.show_log_menu()
                
                elif choice == "6":
                    # Настройки
                    self.show_settings_menu()
                
                elif choice == "0":
                    # Выход
                    print()
                    print_success("Работа завершена!")
                    break
                
                else:
                    print_error("Неверный выбор")
                    time.sleep(1)
            
            except KeyboardInterrupt:
                print()
                print_info("Прервано пользователем")
                break
            except Exception as e:
                print_error(f"Ошибка: {e}")
                time.sleep(2)

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    parser = argparse.ArgumentParser(
        description="BellSoft Java Universal Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  %(prog)s                    # Запустить интерактивный режим
  %(prog)s --work-dir /tmp/my-cache
  %(prog)s --install-dir /opt/java
  %(prog)s --offline          # Только офлайн режим
  %(prog)s --no-color         # Отключить цвета в выводе
  %(prog)s --cleanup          # Очистить старые файлы
  %(prog)s --show-log         # Показать лог
  %(prog)s --cache-info       # Показать информацию о кэше
        """
    )

    parser.add_argument('--work-dir',
                       default=DEFAULT_CACHE_DIR,
                       help=f"Рабочая директория (по умолчанию: {DEFAULT_CACHE_DIR})")
    
    parser.add_argument('--install-dir',
                       default=DEFAULT_INSTALL_DIR,
                       help=f"Директория для установки Java (по умолчанию: {DEFAULT_INSTALL_DIR})")
    
    parser.add_argument('--timeout',
                       type=int,
                       default=REQUEST_TIMEOUT,
                       help=f"Таймаут запросов в секундах (по умолчанию: {REQUEST_TIMEOUT})")
    
    parser.add_argument('--offline',
                       action='store_true',
                       help="Работа в офлайн-режиме (только с кэшем)")
    
    parser.add_argument('--cleanup',
                       action='store_true',
                       help="Очистить старые файлы и выйти")
    
    parser.add_argument('--show-log',
                       action='store_true',
                       help="Показать лог операций")
    
    parser.add_argument('--cache-info',
                       action='store_true',
                       help="Показать информацию о кэше")
    
    parser.add_argument('--no-color',
                       action='store_true',
                       help="Отключить цвета в выводе")
    
    args = parser.parse_args()
    
    # Отключаем цвета если нужно
    # Используем globals() для доступа к глобальной переменной
    globals()['HAS_COLOR'] = not args.no_color and sys.stdout.isatty()
    
    # Создаём экземпляр установщика
    installer = JavaInstaller(args)
    
    # Обрабатываем специальные флаги
    if args.cleanup:
        installer.cleanup_old_files()
        return
    
    if args.show_log:
        log_file = os.path.join(installer.settings.get('cache_dir'), "installer.log")
        if os.path.exists(log_file):
            with open(log_file, 'r', encoding='utf-8') as f:
                print(f.read())
        else:
            print_error(f"Лог-файл не найден: {log_file}")
        return
    
    if args.cache_info:
        if installer.fetch_api_data():
            installer.show_cache_info()
        return
    
    # Запускаем главное меню
    try:
        installer.main_menu()
    except KeyboardInterrupt:
        print()
        print_info("Прервано пользователем")
    except Exception as e:
        print_error(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()


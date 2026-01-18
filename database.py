import sqlite3
import os
from datetime import datetime, timedelta
from functools import lru_cache
import threading

DB_PATH = 'vodka_meter.db'

# Потокобезопасность и кэширование
_db_lock = threading.Lock()
_user_cache = {}
_group_cache = {}

def init_db():
    """Инициализация базы данных с оптимизацией"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Оптимизация для больших объемов данных
    cursor.execute('PRAGMA journal_mode = WAL')  # Write-Ahead Logging
    cursor.execute('PRAGMA synchronous = NORMAL')  # Быстрее, но безопасно
    cursor.execute('PRAGMA cache_size = -64000')  # 64MB кэша
    cursor.execute('PRAGMA temp_store = MEMORY')  # Временные данные в памяти
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            total_drinks INTEGER DEFAULT 0,
            today_drinks INTEGER DEFAULT 0,
            last_drink_date TEXT,
            join_date TEXT,
            level INTEGER DEFAULT 1,
            achievements TEXT DEFAULT '',
            vodka_liters REAL DEFAULT 0,
            last_drink_time TEXT DEFAULT NULL
        )
    ''')
    
    # Индексы для быстрого поиска
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_level ON users(level)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_total_drinks ON users(total_drinks DESC)')
    
    # Таблица рекордов
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS records (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            drink_count INTEGER,
            record_type TEXT,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_records_user_id ON records(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_records_date ON records(date)')
    
    # Таблица групп
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY,
            group_name TEXT,
            total_drinks INTEGER DEFAULT 0,
            join_date TEXT
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_groups_total ON groups(total_drinks DESC)')
    
    # Таблица группо́вых статистик
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS group_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER,
            user_id INTEGER,
            drinks_in_group INTEGER DEFAULT 0,
            FOREIGN KEY (group_id) REFERENCES groups(group_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            UNIQUE(group_id, user_id)
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_group_members_drinks ON group_members(group_id, drinks_in_group DESC)')
    
    conn.commit()
    conn.close()

def get_or_create_user(user_id, username):
    """Получить или создать пользователя с кэшированием"""
    with _db_lock:
        # Проверить кэш
        if user_id in _user_cache:
            return _user_cache[user_id]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            cursor.execute('''
                INSERT INTO users (user_id, username, join_date)
                VALUES (?, ?, ?)
            ''', (user_id, username, datetime.now().isoformat()))
            conn.commit()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        # Кэшировать
        _user_cache[user_id] = user
        
        conn.close()
        return user

def get_user_data(user_id):
    """Получить данные пользователя с кэшированием"""
    with _db_lock:
        # Проверить кэш
        if user_id in _user_cache:
            return _user_cache[user_id]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if user:
            _user_cache[user_id] = user
        
        conn.close()
        return user

def _invalidate_user_cache(user_id):
    """Инвалидировать кэш пользователя"""
    if user_id in _user_cache:
        del _user_cache[user_id]

def can_drink(user_id):
    """Проверить может ли пользователь пить (прошло 5 часов)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT last_drink_time FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result or result[0] is None:
        return True, 0
    
    last_time = datetime.fromisoformat(result[0])
    now = datetime.now()
    diff = now - last_time
    
    if diff.total_seconds() >= 5 * 3600:  # 5 часов
        return True, 0
    else:
        minutes_left = int((5 * 3600 - diff.total_seconds()) / 60)
        return False, minutes_left

def add_drink(user_id):
    """Добавить рюмку с случайной водкой (0-10 литров)"""
    import random
    
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        now = datetime.now().isoformat()
        
        # Получить текущие данные
        cursor.execute('SELECT total_drinks, today_drinks, last_drink_date, vodka_liters FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            total, today_drinks, last_date, vodka = result
            
            # Сбросить счетчик если прошли сутки
            if last_date and last_date != today:
                today_drinks = 0
            
            # Случайная водка от 0 до 10 литров
            vodka_gain = random.randint(0, 10)
            
            cursor.execute('''
                UPDATE users 
                SET total_drinks = total_drinks + 1,
                    today_drinks = ?,
                    last_drink_date = ?,
                    vodka_liters = ?,
                    last_drink_time = ?
                WHERE user_id = ?
            ''', (today_drinks + 1, today, vodka + vodka_gain, now, user_id))
            
            conn.commit()
        
        conn.close()
        
        # Инвалидировать кэш
        _invalidate_user_cache(user_id)
        
        return vodka_gain if result else 0

def get_leaderboard(limit=10):
    """Получить топ пьяниц - оптимизировано"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, total_drinks, level 
            FROM users 
            ORDER BY total_drinks DESC 
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results

def get_today_leaderboard(limit=10):
    """Получить топ за сегодня - оптимизировано"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id, username, today_drinks 
            FROM users 
            ORDER BY today_drinks DESC 
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        return results

def calculate_level(total_drinks):
    """Вычислить уровень по количеству рюмок"""
    if total_drinks < 10:
        return 1
    elif total_drinks < 50:
        return 2
    elif total_drinks < 100:
        return 3
    elif total_drinks < 200:
        return 4
    elif total_drinks < 500:
        return 5
    else:
        return 6

def update_level(user_id):
    """Обновить уровень"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT total_drinks FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            level = calculate_level(result[0])
            cursor.execute('UPDATE users SET level = ? WHERE user_id = ?', (level, user_id))
            conn.commit()
        
        conn.close()
        _invalidate_user_cache(user_id)

# ===== АДМИН ФУНКЦИИ =====

def add_vodka(user_id, amount):
    """Админ команда: добавить водку"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET vodka_liters = vodka_liters + ? WHERE user_id = ?', (amount, user_id))
        conn.commit()
        conn.close()
        _invalidate_user_cache(user_id)

def remove_vodka(user_id, amount):
    """Админ команда: отнять водку (макс 10 литров)"""
    amount = min(amount, 10)  # Максимум 10 литров
    
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT vodka_liters FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if result:
            current = result[0]
            new_amount = max(0, current - amount)
            cursor.execute('UPDATE users SET vodka_liters = ? WHERE user_id = ?', (new_amount, user_id))
            conn.commit()
        
        conn.close()
        _invalidate_user_cache(user_id)

def add_levels(user_id, levels_count):
    """Админ команда: добавить уровни"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('UPDATE users SET level = level + ? WHERE user_id = ?', (levels_count, user_id))
        conn.commit()
        conn.close()
        _invalidate_user_cache(user_id)

def get_user_by_username(username):
    """Получить пользователя по username"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Без @ префикса
    clean_username = username.lstrip('@')
    
    cursor.execute('SELECT user_id FROM users WHERE username = ?', (clean_username,))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

# ===== ГРУППО́ВЫЕ ФУНКЦИИ =====

def add_group(group_id, group_name):
    """Добавить группу в БД"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT group_id FROM groups WHERE group_id = ?', (group_id,))
        if cursor.fetchone():
            conn.close()
            return False
        
        cursor.execute('''
            INSERT INTO groups (group_id, group_name, join_date)
            VALUES (?, ?, ?)
        ''', (group_id, group_name, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # Кэшировать группу
        _group_cache[group_id] = (group_name, 0)
        
        return True

def add_user_to_group(group_id, user_id):
    """Добавить пользователя в группу"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR IGNORE INTO group_members (group_id, user_id)
                VALUES (?, ?)
            ''', (group_id, user_id))
            conn.commit()
        except:
            pass
        
        conn.close()

def add_group_drink(group_id, user_id):
    """Добавить выпивку в группе"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Увеличить счетчик группы
        cursor.execute('''
            UPDATE groups 
            SET total_drinks = total_drinks + 1 
            WHERE group_id = ?
        ''', (group_id,))
        
        # Увеличить счетчик пользователя в группе
        cursor.execute('''
            UPDATE group_members 
            SET drinks_in_group = drinks_in_group + 1 
            WHERE group_id = ? AND user_id = ?
        ''', (group_id, user_id))
        
        conn.commit()
        conn.close()
        
        # Инвалидировать кэш группы
        if group_id in _group_cache:
            del _group_cache[group_id]

def get_group_top(group_id, limit=10):
    """Получить топ в группе - оптимизировано"""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.username, gm.drinks_in_group, u.level
            FROM group_members gm
            JOIN users u ON gm.user_id = u.user_id
            WHERE gm.group_id = ?
            ORDER BY gm.drinks_in_group DESC
            LIMIT ?
        ''', (group_id, limit))
        
        results = cursor.fetchall()
        conn.close()
        return results

def get_group_info(group_id):
    """Получить информацию о группе с кэшированием"""
    with _db_lock:
        # Проверить кэш
        if group_id in _group_cache:
            return _group_cache[group_id]
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT group_name, total_drinks FROM groups WHERE group_id = ?', (group_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            _group_cache[group_id] = result
        
        return result

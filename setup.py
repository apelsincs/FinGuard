#!/usr/bin/env python3
"""
Скрипт для быстрой настройки FinGuard
Устанавливает зависимости и создает необходимые файлы
"""

import os
import subprocess
import sys


def run_command(command, description):
    """Выполнить команду с выводом"""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} завершено успешно")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка при {description.lower()}: {e}")
        print(f"Вывод: {e.stderr}")
        return False


def create_env_file():
    """Создать файл .env из примера"""
    if not os.path.exists('.env'):
        print("📝 Создание файла .env...")
        try:
            with open('env.example', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Заменяем placeholder на реальные значения для демо
            content = content.replace('your_telegram_bot_token_here', 'DEMO_TOKEN_PLACEHOLDER')
            content = content.replace('your_secret_key_here_make_it_long_and_random', 'demo_secret_key_for_development_only_change_in_production')
            content = content.replace('your_encryption_key_here_32_bytes', 'demo_encryption_key_32_bytes_long')
            
            with open('.env', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ Файл .env создан")
            print("⚠️  Не забудьте заменить DEMO_TOKEN_PLACEHOLDER на реальный токен бота!")
            return True
        except Exception as e:
            print(f"❌ Ошибка при создании .env: {e}")
            return False
    else:
        print("✅ Файл .env уже существует")
        return True


def main():
    """Главная функция настройки"""
    print("🚀 Настройка FinGuard Telegram Bot")
    print("=" * 50)
    
    # Проверяем Python
    if sys.version_info < (3, 8):
        print("❌ Требуется Python 3.8 или выше")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} обнаружен")
    
    # Создаем виртуальное окружение если его нет
    if not os.path.exists('venv'):
        print("🐍 Создание виртуального окружения...")
        if not run_command('python3 -m venv venv', 'Создание виртуального окружения'):
            return False
    else:
        print("✅ Виртуальное окружение уже существует")
    
    # Активируем виртуальное окружение и устанавливаем зависимости
    if os.name == 'nt':  # Windows
        pip_cmd = 'venv\\Scripts\\pip'
        python_cmd = 'venv\\Scripts\\python'
    else:  # Unix/Linux/macOS
        pip_cmd = 'venv/bin/pip'
        python_cmd = 'venv/bin/python'
    
    # Обновляем pip
    if not run_command(f'{pip_cmd} install --upgrade pip', 'Обновление pip'):
        return False
    
    # Устанавливаем зависимости
    if not run_command(f'{pip_cmd} install -r requirements.txt', 'Установка зависимостей'):
        return False
    
    # Создаем .env файл
    if not create_env_file():
        return False
    
    # Создаем директории
    os.makedirs('logs', exist_ok=True)
    print("✅ Директории созданы")
    
    print("\n🎉 Настройка завершена!")
    print("\n📋 Следующие шаги:")
    print("1. Получите токен бота у @BotFather в Telegram")
    print("2. Замените DEMO_TOKEN_PLACEHOLDER в файле .env на ваш токен")
    print("3. Запустите бота командой: python app/main.py")
    print("\n💡 Для получения токена бота:")
    print("   - Напишите @BotFather в Telegram")
    print("   - Отправьте /newbot")
    print("   - Следуйте инструкциям")
    
    return True


if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)

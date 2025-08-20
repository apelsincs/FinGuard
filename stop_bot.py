#!/usr/bin/env python3
"""
Скрипт для остановки всех процессов FinGuard бота
"""

import os
import signal
import subprocess
import sys


def stop_bot():
    """Остановить все процессы бота"""
    print("🛑 Остановка FinGuard бота...")
    
    try:
        # Ищем процессы Python, которые запускают наш бот
        result = subprocess.run(
            ['ps', 'aux'], 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            bot_processes = []
            
            for line in lines:
                if 'python' in line and 'app/main.py' in line:
                    parts = line.split()
                    if len(parts) > 1:
                        pid = parts[1]
                        bot_processes.append(pid)
                        print(f"Найден процесс бота: PID {pid}")
            
            if bot_processes:
                for pid in bot_processes:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        print(f"✅ Процесс {pid} остановлен")
                    except ProcessLookupError:
                        print(f"⚠️ Процесс {pid} уже завершен")
                    except Exception as e:
                        print(f"❌ Ошибка при остановке процесса {pid}: {e}")
            else:
                print("ℹ️ Процессы бота не найдены")
        else:
            print("❌ Ошибка при поиске процессов")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    stop_bot()

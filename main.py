"""
Основной модуль - мониторит папку и сортирует письма
"""
import shutil
import time
from pathlib import Path
from email_reader import EmailReader
from classifier import EmailClassifier

# Папки
BASE_DIR = Path(__file__).parent
INBOX = BASE_DIR /"folders"/ "inbox"
SPAM = BASE_DIR /"folders"/ "spam"
CONTAINERS = BASE_DIR /"folders"/ "containers"
LOGISTICS = BASE_DIR /"folders"/ "logistics"
PERSONAL = BASE_DIR /"folders"/ "personal"
REVIEW = BASE_DIR /"folders"/ "review"

FOLDERS = {
    'spam': SPAM,
    'containers': CONTAINERS,
    'logistics': LOGISTICS,
    'personal': PERSONAL,
    'review': REVIEW
}

def setup():
    """Создает папки и тестовые письма"""
    for folder in [INBOX] + list(FOLDERS.values()):
        folder.mkdir(parents=True, exist_ok=True)
    
    # Создаем тестовые письма если папка пуста
    if not list(INBOX.glob("*")):
        print("Создание тестовых писем...\n")
        
        # EML с HTML и вложением
        eml_content = """From: client@company.com
Subject: Container Rental Request
MIME-Version: 1.0
Content-Type: multipart/mixed; boundary="boundary123"

--boundary123
Content-Type: text/html; charset=utf-8

<html>
<body>
<h2>Container Rental Inquiry</h2>
<p>We need <b>20 shipping containers</b> for our logistics project.</p>
<table border="1">
<tr><th>Type</th><th>Quantity</th></tr>
<tr><td>20ft Dry</td><td>10</td></tr>
<tr><td>40ft High Cube</td><td>10</td></tr>
</table>
<p>Please send your rates.</p>
</body>
</html>

--boundary123
Content-Type: text/plain; charset=utf-8
Content-Disposition: attachment; filename="details.txt"

Container specifications:
- 10x 20ft Dry Containers
- 10x 40ft High Cube Containers
- Delivery to Shanghai Port
- Long-term rental preferred

--boundary123--
"""
        with open(INBOX / "container_inquiry.eml", 'w', encoding='utf-8') as f:
            f.write(eml_content)
        
        # Простой текст
        with open(INBOX / "logistics_request.txt", 'w', encoding='utf-8') as f:
            f.write("Need multimodal transport from Moscow to Beijing. Cargo: electronics.")
        
        # Спам
        with open(INBOX / "spam_offer.txt", 'w', encoding='utf-8') as f:
            f.write("CONGRATULATIONS! You won $1,000,000! Click here to claim your prize now!")
        
        # Личное
        with open(INBOX / "personal_lunch.txt", 'w', encoding='utf-8') as f:
            f.write("Hi! Are you free for lunch this weekend? Let's meet at the restaurant.")
        
        print("✓ Создано 4 тестовых письма\n")

def process_emails(reader: EmailReader, classifier: EmailClassifier):
    """Обрабатывает все письма в inbox"""
    files = list(INBOX.glob("*"))
    
    if not files:
        return False
    
    print(f"\n{'='*50}")
    print(f"Найдено писем: {len(files)}")
    print(f"{'='*50}")
    
    stats = {}
    
    for filepath in files:
        if not filepath.is_file():
            continue
        
        try:
            # Читаем письмо
            text = reader.read_file(filepath)
            
            if not text.strip():
                print(f"  ⚠ Пустой файл: {filepath.name}")
                continue
            
            # Классифицируем
            category, confidence = classifier.classify(text)
            
            # Перемещаем
            target_dir = FOLDERS.get(category, REVIEW)
            target_path = target_dir / filepath.name
            
            # Если файл существует - добавляем номер
            counter = 1
            while target_path.exists():
                stem = filepath.stem
                target_path = target_dir / f"{stem}_{counter}{filepath.suffix}"
                counter += 1
            
            shutil.move(str(filepath), str(target_path))
            
            # Статистика
            stats[category] = stats.get(category, 0) + 1
            
            # Вывод с цветом (если поддерживается)
            emoji = {'spam': '🗑', 'containers': '📦', 'logistics': '🚛', 
                     'personal': '👤', 'review': '❓'}.get(category, '📄')
            print(f"  {emoji} {filepath.name} → {category} ({confidence:.2f})")
            
        except Exception as e:
            print(f"  ✗ Ошибка: {filepath.name} - {e}")
    
    # Итоги
    print(f"\n{'─'*50}")
    print(f"Результаты обработки:")
    for cat, count in stats.items():
        print(f"  {cat}: {count}")
    print(f"{'─'*50}\n")
    
    return True

def main():
    print("="*50)
    print("  EMAIL CLASSIFIER v2.0")
    print("  Поддержка: EML, HTML, вложения, OCR")
    print("="*50)
    print(f"  Inbox: {INBOX}")
    print(f"{'='*50}\n")
    
    # Инициализация
    reader = EmailReader()
    classifier = EmailClassifier()
    
    # Настройка
    setup()
    
    print("Мониторинг папки inbox...")
    print("Для выхода нажмите Ctrl+C\n")
    
    try:
        while True:
            has_files = process_emails(reader, classifier)
            if not has_files:
                print(f"\r[{time.strftime('%H:%M:%S')}] Ожидание новых писем...", end='')
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n\nРабота завершена.")

if __name__ == "__main__":
    main()
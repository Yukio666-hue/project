"""
Классификатор писем - объединяет правила и нейросеть
"""
import re
import torch
import numpy as np
from transformers import AutoTokenizer, AutoModel
from langdetect import detect

class EmailClassifier:
    def __init__(self, model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        """
        Инициализация классификатора
        
        Модель скачивается один раз и сохраняется в кеш Hugging Face
        """
        print(f"Загрузка модели {model_name}...")
        print("(при первом запуске скачивается примерно 470 MB)")
        
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        
        print("Модель загружена!")
        print()
        
        # Ключевые слова для быстрой классификации
        self._init_keywords()
    
    def _init_keywords(self):
        """Инициализация ключевых слов и паттернов"""
        
        # Паттерны спама (регулярные выражения)
        self.spam_patterns = [
            r'congratulations.*(?:won|winner|prize)',
            r'urgent.*(?:money|transfer|payment)',
            r'click here|act now|limited time|exclusive offer',
            r'\b(?:viagra|casino|lottery|jackpot|bitcoin)\b',
            r'free.*(?:trial|offer|sample|access)',
            r'\d{1,3}%\s*(?:off|discount)',
            r'unsubscribe|opt.out',
        ]
        
        # Ключевые слова для контейнеров
        self.container_keywords = [
            'container', 'reefer', 'tank container', 'flat rack',
            'container rental', 'container lease', 'container sale',
            'shipping container', 'storage container',
            'dry container', 'open top container',
        ]
        
        # Ключевые слова для логистики
        self.logistics_keywords = [
            'shipping', 'transport', 'logistics', 'freight',
            'delivery', 'cargo', 'shipment', 'forwarding',
            'multimodal', 'intermodal', 'railway',
            'customs', 'bill of lading',
            'tracking',
        ]
        
        # Ключевые слова для личной переписки
        self.personal_keywords = [
            'lunch', 'dinner', 'coffee', 'weekend',
            'birthday', 'congratulations on',
            'how are you', 'nice to meet',
            'family', 'vacation', 'holiday',
        ]
    
    def get_embedding(self, text: str):
        """
        Преобразует текст в вектор (эмбеддинг)
        
        Как это работает:
        1. Текст разбивается на токены (слова/части слов)
        2. Каждый токен получает числовой ID
        3. Модель преобразует последовательность ID в вектор из 384 чисел
        4. Этот вектор отражает СМЫСЛ текста
        """
        # Берем первые 256 токенов для скорости
        encoded = self.tokenizer(
            text[:1000],
            padding=True,
            truncation=True,
            max_length=256,
            return_tensors='pt'
        )
        
        # Отключаем вычисление градиентов (ускоряет работу)
        with torch.no_grad():
            output = self.model(**encoded)
        
        # Усредняем векторы всех токенов (mean pooling)
        attention_mask = encoded['attention_mask']
        token_embeddings = output[0]
        
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
        sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
        
        embedding = (sum_embeddings / sum_mask).numpy()
        return embedding[0]
    
    def cosine_similarity(self, a, b):
        """Косинусное сходство между двумя векторами"""
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    
    def classify(self, text: str):
        """
        Классифицирует письмо
        
        Возвращает: (категория, уверенность)
        """
        if not text or len(text.strip()) < 10:
            return 'review', 0.0
        
        text_lower = text.lower()
        
        # ========== ЭТАП 1: Быстрые правила ==========
        
        # Проверка спама
        spam_score = 0
        for pattern in self.spam_patterns:
            if re.search(pattern, text_lower):
                spam_score += 0.25
        
        if spam_score >= 0.75:
            return 'spam', min(0.95, spam_score)
        
        # Подсчет ключевых слов
        container_score = sum(1 for kw in self.container_keywords if kw in text_lower)
        logistics_score = sum(1 for kw in self.logistics_keywords if kw in text_lower)
        personal_score = sum(1 for kw in self.personal_keywords if kw in text_lower)
        
        # Если явное преобладание одной категории
        if container_score >= 3 and container_score > logistics_score + 1:
            return 'containers', 0.85
        elif logistics_score >= 3 and logistics_score > container_score + 1:
            return 'logistics', 0.85
        elif personal_score >= 3 and personal_score > max(container_score, logistics_score) + 1:
            return 'personal', 0.80
        
        # ========== ЭТАП 2: Нейросеть для сложных случаев ==========
        
        # Получаем вектор текста
        text_embedding = self.get_embedding(text[:1000])
        
        # Эталонные описания категорий
        references = {
            'containers': [
                "container rental lease purchase sale shipping storage equipment",
                "shipping containers for rent or sale logistics equipment"
            ],
            'logistics': [
                "transportation shipping logistics delivery freight cargo supply chain",
                "multimodal transport delivery service freight forwarding"
            ],
            'personal': [
                "personal meeting greetings lunch dinner family weekend",
                "how are you nice to meet you personal conversation"
            ],
            'spam': [
                "advertisement promotion offer discount buy now limited time",
                "urgent money transfer prize winner congratulations"
            ]
        }
        
        # Сравниваем с каждой категорией
        best_category = 'review'
        best_score = 0.0
        
        for category, ref_texts in references.items():
            # Усредняем сходство с несколькими эталонами
            scores = []
            for ref_text in ref_texts:
                ref_embedding = self.get_embedding(ref_text)
                score = self.cosine_similarity(text_embedding, ref_embedding)
                scores.append(score)
            
            avg_score = sum(scores) / len(scores)
            
            if avg_score > best_score:
                best_score = avg_score
                best_category = category
        
        # Корректируем с учетом ключевых слов
        if container_score >= 2 and best_category != 'containers':
            best_score += 0.1
        if logistics_score >= 2 and best_category != 'logistics':
            best_score += 0.1
        
        # Порог уверенности
        if best_score < 0.35:
            return 'review', best_score
        
        return best_category, min(0.95, best_score)


if __name__ == "__main__":
    # Тестирование классификатора
    classifier = EmailClassifier()
    
    tests = [
        "We need to rent 20 shipping containers for export to Europe",
        "Multimodal transport required from Shanghai to Moscow",
        "URGENT! You won $1,000,000! Click here to claim!",
        "Hi John, let's meet for lunch this weekend",
    ]
    
    for text in tests:
        category, confidence = classifier.classify(text)
        print(f"[{category}] (conf: {confidence:.2f}) - {text[:70]}...")
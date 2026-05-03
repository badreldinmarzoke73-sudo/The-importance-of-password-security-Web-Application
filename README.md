# 🚀 خطوات تشغيل المشروع

## 1. تثبيت المكتبات
افتح CMD أو Terminal جوه فولدر المشروع واكتب:
```
pip install -r requirements.txt
```

## 2. إنشاء قاعدة البيانات (XAMPP)
- افتح XAMPP وشغّل Apache + MySQL
- افتح http://localhost/phpmyadmin
- اضغط "New" وأنشئ Database اسمها:  flask_app
- خلاص! التطبيق هيعمل الجدول تلقائياً لما يشتغل

## 3. الحصول على Anthropic API Key
1. روح على: https://console.anthropic.com
2. اعمل Account لو مش عندك
3. اضغط "Get API Keys" ثم "Create Key"
4. انسخ الـ Key

## 4. إضافة الـ API Key للمشروع

### Windows:
```
set ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxx
```

### Mac / Linux:
```
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxx
```

أو ضيف السطر ده جوه app.py فوق مباشرةً (للتطوير المحلي فقط):
```python
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-xxxxxxxxxxxxxx"
```

## 5. تشغيل التطبيق
```
python app.py
```

ثم افتح المتصفح على: http://localhost:5000

## هيكل الملفات
```
project/
├── app.py
├── requirements.txt
├── README.md
├── templates/
│   ├── register.html
│   ├── login.html
│   └── chatbot.html
└── static/
    └── style.css
```

## ملاحظات
- بيانات تسجيل الدخول في MySQL بـ default: user=root, password=""
- لو الباسورد مختلف عدّله في دالة get_db() جوه app.py

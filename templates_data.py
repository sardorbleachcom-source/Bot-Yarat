# -*- coding: utf-8 -*-
"""Tayyor shablonlar (bazaga birinchi ishga tushishda yoziladi). Yangilarini admin paneldan qo'shish mumkin."""

GROUPS = ["media", "business", "channel", "community", "tools", "fun", "universal"]

# key, guruh, (uz, ru, en, ar), premium
TEMPLATES = [
    ("movie", "media", ("🎬 Kino bot", "🎬 Кино-бот", "🎬 Movie bot", "🎬 بوت الأفلام"), 0),
    ("series", "media", ("📺 Serial bot", "📺 Бот сериалов", "📺 Series bot", "📺 بوت المسلسلات"), 0),
    ("music", "media", ("🎵 Musiqa bot", "🎵 Музыкальный бот", "🎵 Music bot", "🎵 بوت الموسيقى"), 0),
    ("photo", "media", ("📸 Rasm bot", "📸 Фото-бот", "📸 Photo bot", "📸 بوت الصور"), 0),
    ("video", "media", ("🎞 Video bot", "🎞 Видео-бот", "🎞 Video bot", "🎞 بوت الفيديو"), 0),
    ("book", "media", ("📚 Kitob bot", "📚 Книжный бот", "📚 Book bot", "📚 بوت الكتب"), 0),
    ("shop", "business", ("🛍 Do‘kon bot", "🛍 Бот-магазин", "🛍 Shop bot", "🛍 بوت المتجر"), 0),
    ("orders", "business", ("📦 Buyurtma bot", "📦 Бот заказов", "📦 Orders bot", "📦 بوت الطلبات"), 0),
    ("payment", "business", ("💳 To‘lov bot", "💳 Платёжный бот", "💳 Payment bot", "💳 بوت الدفع"), 0),
    ("contact", "business", ("📞 Mijozlar bilan aloqa", "📞 Связь с клиентами", "📞 Customer contact", "📞 التواصل مع العملاء"), 0),
    ("crm", "business", ("📊 CRM bot", "📊 CRM-бот", "📊 CRM bot", "📊 بوت CRM"), 1),
    ("news", "channel", ("📰 Yangiliklar bot", "📰 Новостной бот", "📰 News bot", "📰 بوت الأخبار"), 0),
    ("chanhelper", "channel", ("📢 Kanal yordamchisi", "📢 Помощник канала", "📢 Channel helper", "📢 مساعد القناة"), 0),
    ("scheduler", "channel", ("📅 Post rejalashtiruvchi", "📅 Планировщик постов", "📅 Post scheduler", "📅 جدولة المنشورات"), 1),
    ("notify", "channel", ("🔔 Xabarnoma bot", "🔔 Бот уведомлений", "🔔 Notification bot", "🔔 بوت الإشعارات"), 0),
    ("chanstats", "channel", ("📊 Kanal statistika bot", "📊 Статистика канала", "📊 Channel stats bot", "📊 إحصائيات القناة"), 1),
    ("chathelper", "community", ("💬 Chat yordamchi", "💬 Помощник чата", "💬 Chat helper", "💬 مساعد الدردشة"), 0),
    ("voting", "community", ("🗳 Ovoz berish bot", "🗳 Бот голосования", "🗳 Voting bot", "🗳 بوت التصويت"), 0),
    ("qa", "community", ("❓ Savol-javob bot", "❓ Вопрос-ответ", "❓ Q&A bot", "❓ بوت الأسئلة والأجوبة"), 0),
    ("contest", "community", ("🎁 Tanlov bot", "🎁 Бот конкурсов", "🎁 Contest bot", "🎁 بوت المسابقات"), 0),
    ("register", "community", ("📝 Ro‘yxatdan o‘tish bot", "📝 Бот регистрации", "📝 Registration bot", "📝 بوت التسجيل"), 0),
    ("ai", "tools", ("🤖 AI bot", "🤖 AI-бот", "🤖 AI bot", "🤖 بوت الذكاء الاصطناعي"), 1),
    ("translator", "tools", ("🌐 Tarjimon bot", "🌐 Бот-переводчик", "🌐 Translator bot", "🌐 بوت الترجمة"), 0),
    ("search", "tools", ("🔎 Qidiruv bot", "🔎 Поисковый бот", "🔎 Search bot", "🔎 بوت البحث"), 0),
    ("links", "tools", ("🔗 Havola bot", "🔗 Бот ссылок", "🔗 Links bot", "🔗 بوت الروابط"), 0),
    ("files", "tools", ("📁 Fayl bot", "📁 Файловый бот", "📁 File bot", "📁 بوت الملفات"), 0),
    ("calc", "tools", ("🧮 Kalkulyator bot", "🧮 Калькулятор", "🧮 Calculator bot", "🧮 بوت الحاسبة"), 0),
    ("game", "fun", ("🎮 O‘yin bot", "🎮 Игровой бот", "🎮 Game bot", "🎮 بوت الألعاب"), 0),
    ("quiz", "fun", ("🧠 Viktorina bot", "🧠 Бот-викторина", "🧠 Quiz bot", "🧠 بوت المسابقات الثقافية"), 0),
    ("random", "fun", ("🎲 Tasodifiy tanlov", "🎲 Случайный выбор", "🎲 Random picker", "🎲 اختيار عشوائي"), 0),
    ("rating", "fun", ("🏆 Reyting bot", "🏆 Бот рейтинга", "🏆 Rating bot", "🏆 بوت التصنيف"), 1),
    ("prize", "fun", ("🎁 Sovrin bot", "🎁 Бот призов", "🎁 Prize bot", "🎁 بوت الجوائز"), 0),
    ("empty", "universal", ("➕ Bo‘sh bot", "➕ Пустой бот", "➕ Empty bot", "➕ بوت فارغ"), 0),
    ("custom", "universal", ("⚙️ O‘zingiz sozlash", "⚙️ Настроить самому", "⚙️ Customize yourself", "⚙️ خصّصه بنفسك"), 0),
]

# Shablon asosiy tugmasi tashqari qo'shiladigan tayyor buyruq-tugmalar
EXTRA_CMDS = {
    "calc": ["calc"], "random": ["random", "coin"], "prize": ["random"], "game": ["coin", "random"],
    "contact": ["contact"], "qa": ["contact"], "chathelper": ["contact"], "register": ["contact"],
    "ai": ["contact"], "contest": ["contact", "random"], "voting": ["contact"],
}
COMMANDS = ["contact", "calc", "random", "coin", "id"]

require('dotenv').config();

const express = require('express');
const path = require('path');
const cors = require('cors');
const { startBot } = require('./bot');
const apiRoutes = require('./routes/api');

const app = express();
const PORT = process.env.PORT || 3000;

// Проверяем обязательные настройки
const requiredEnv = ['BOT_TOKEN', 'ADMIN_TELEGRAM_ID'];
const missing = requiredEnv.filter((key) => !process.env[key]);
if (missing.length > 0) {
  console.error('❌ Заполни файл .env! Не хватает:', missing.join(', '));
  console.error('   Скопируй .env.example → .env и вставь свои значения.');
  process.exit(1);
}

// URL Mini App: локально, на Render или из .env
const miniAppUrl =
  process.env.MINI_APP_URL ||
  process.env.RENDER_EXTERNAL_URL ||
  `http://localhost:${PORT}`;

app.use(cors());
app.use(express.json());

// API-маршруты (всё, что делает Mini App на сервере)
app.use('/api', apiRoutes);

// Раздаём файлы Mini App как обычный сайт
app.use(express.static(path.join(__dirname, '..', 'miniapp')));

// Любой неизвестный путь → главная страница Mini App
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'miniapp', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`🌐 Сервер запущен: http://localhost:${PORT}`);
  console.log(`📱 Mini App URL: ${miniAppUrl}`);
  console.log('');
  console.log('Следующий шаг: открой бота в Telegram и нажми /start');
});

// Запускаем Telegram-бота
startBot({
  token: process.env.BOT_TOKEN,
  adminTelegramId: process.env.ADMIN_TELEGRAM_ID,
  miniAppUrl,
});

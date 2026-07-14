require('dotenv').config();

const express = require('express');
const path = require('path');
const cors = require('cors');
const { startBot } = require('./bot');
const apiRoutes = require('./routes/api');
const { initDb, usePostgres } = require('./db');

const app = express();
const PORT = process.env.PORT || 3000;

const requiredEnv = ['BOT_TOKEN', 'ADMIN_TELEGRAM_ID'];
const missing = requiredEnv.filter((key) => !process.env[key]);
if (missing.length > 0) {
  console.error('❌ Заполни файл .env! Не хватает:', missing.join(', '));
  console.error('   Скопируй .env.example → .env и вставь свои значения.');
  process.exit(1);
}

const miniAppUrl =
  process.env.MINI_APP_URL ||
  process.env.RENDER_EXTERNAL_URL ||
  `http://localhost:${PORT}`;

app.use(cors());
app.use(express.json());
app.use('/api', apiRoutes);
app.use(express.static(path.join(__dirname, '..', 'miniapp')));

app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, '..', 'miniapp', 'index.html'));
});

async function start() {
  try {
    await initDb();
    console.log(usePostgres ? '🐘 База: PostgreSQL' : '📁 База: SQLite (локально)');

    app.listen(PORT, () => {
      console.log(`🌐 Сервер запущен: http://localhost:${PORT}`);
      console.log(`📱 Mini App URL: ${miniAppUrl}`);
      console.log('');
      console.log('Следующий шаг: открой бота в Telegram и нажми /start');
    });

    startBot({
      token: process.env.BOT_TOKEN,
      adminTelegramId: process.env.ADMIN_TELEGRAM_ID,
      miniAppUrl,
    });
  } catch (error) {
    console.error('❌ Не удалось запустить базу данных:', error.message);
    process.exit(1);
  }
}

start();

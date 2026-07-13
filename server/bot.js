const TelegramBot = require('node-telegram-bot-api');
const {
  findOrCreateUser,
  logActivity,
  getUserByTelegramId,
  createDepositRequest,
  approveDepositRequest,
  rejectDepositRequest,
  getPendingDepositRequests,
  createWithdrawalRequest,
  approveWithdrawalRequest,
  rejectWithdrawalRequest,
  getPendingWithdrawalRequests,
  getAllUsers,
  setWithdrawalEnabled,
  getUserNfts,
} = require('./db');
const withdrawConfig = require('./withdraw-config');
const nftCatalog = require('./nft-catalog');

let bot = null;

function formatUserName(user) {
  if (user.username) return `@${user.username}`;
  return [user.first_name, user.last_name].filter(Boolean).join(' ') || `ID ${user.telegram_id}`;
}

function isHttpsUrl(url) {
  return typeof url === 'string' && url.startsWith('https://');
}

function startBot({ token, adminTelegramId, miniAppUrl }) {
  bot = new TelegramBot(token, { polling: true });

  console.log('🤖 Telegram-бот запущен');
  if (!isHttpsUrl(miniAppUrl)) {
    console.log('⚠️  MINI_APP_URL без HTTPS — кнопка Mini App пока недоступна');
    console.log('   Запусти ngrok http 3000 и обнови MINI_APP_URL в .env');
  }

  // Команда /start — первое, что видит пользователь
  bot.onText(/\/start/, async (msg) => {
    const chatId = msg.chat.id;
    const telegramUser = msg.from;

    const { user, isNew } = findOrCreateUser(telegramUser);
    logActivity(user.id, isNew ? 'registered' : 'opened_bot', isNew ? 'Новый пользователь' : 'Вернулся в бота');

    const welcomeText = isNew
      ? `👋 Привет, ${telegramUser.first_name || 'друг'}!\n\nДобро пожаловать в Zeritime NFT.`
      : `С возвращением, ${telegramUser.first_name || 'друг'}! 👋`;

    try {
      if (isHttpsUrl(miniAppUrl)) {
        await bot.sendMessage(chatId, `${welcomeText}\n\nНажми кнопку ниже, чтобы открыть приложение.`, {
          reply_markup: {
            inline_keyboard: [
              [{ text: '🚀 Открыть Zeritime NFT', web_app: { url: miniAppUrl } }],
            ],
          },
        });
      } else {
        await bot.sendMessage(
          chatId,
          `${welcomeText}\n\n✅ Бот работает!\n\nКнопка Mini App появится после настройки HTTPS (ngrok). Пока можешь проверить уведомления админу.`
        );
      }
    } catch (error) {
      console.error('Ошибка ответа на /start:', error.message);
      await bot.sendMessage(chatId, `${welcomeText}\n\n✅ Ты зарегистрирован. Mini App подключим на следующем шаге.`);
    }

    // Уведомляем админа о каждом заходе
    if (adminTelegramId) {
      const adminMessage = isNew
        ? `🆕 Новый пользователь!\n\n👤 ${formatUserName(user)}\n🆔 ${user.telegram_id}\n💰 Баланс: 0`
        : `👀 Пользователь зашёл\n\n👤 ${formatUserName(user)}\n🆔 ${user.telegram_id}`;

      try {
        await bot.sendMessage(adminTelegramId, adminMessage);
      } catch (error) {
        console.error('Не удалось отправить уведомление админу:', error.message);
      }
    }
  });

  // Команда /deposit 1000 — запрос пополнения прямо в боте
  bot.onText(/\/deposit(?:\s+(\d+))?/, async (msg, match) => {
    const chatId = msg.chat.id;
    const amount = Number(match[1]);

    if (!amount || amount <= 0) {
      await bot.sendMessage(chatId, '💳 Напиши сумму так:\n/deposit 1000');
      return;
    }

    const { user } = findOrCreateUser(msg.from);
    const request = createDepositRequest(user.id, amount);
    logActivity(user.id, 'deposit_request', `Запрос ${amount} ₽`);

    await bot.sendMessage(
      chatId,
      `✅ Запрос на пополнение ${amount} ₽ отправлен.\n\nЖди подтверждения админа.`
    );

    await sendDepositRequestToAdmin(adminTelegramId, request, user);
  });

  // Команда /withdraw 500 — запрос вывода
  bot.onText(/\/withdraw(?:\s+(\d+))?/, async (msg, match) => {
    const chatId = msg.chat.id;
    const amount = Number(match[1]);

    if (!amount || amount <= 0) {
      await bot.sendMessage(chatId, '💸 Напиши сумму так:\n/withdraw 500');
      return;
    }

    const { user } = findOrCreateUser(msg.from);
    const error = validateWithdrawal(user, amount);

    if (error) {
      await bot.sendMessage(chatId, error);
      return;
    }

    const request = createWithdrawalRequest(user.id, amount);
    logActivity(user.id, 'withdrawal_request', `Запрос ${amount} ₽`);

    await bot.sendMessage(
      chatId,
      `✅ Запрос на вывод ${amount} ₽ отправлен.\n\nЖди подтверждения админа.`
    );

    await sendWithdrawalRequestToAdmin(adminTelegramId, request, user);
  });

  // ═══ УРОК 6: /balance — персонализируй строку replyText ниже ═══
  bot.onText(/\/balance/, async (msg) => {
    const chatId = msg.chat.id;
    const user = getUserByTelegramId(String(msg.from.id));

    if (!user) {
      await bot.sendMessage(chatId, 'Сначала нажми /start');
      return;
    }

    const replyText = `💰 Ваш баланс: ${user.balance} ₽`; // ← ТВОЯ ЗАДАЧА: поменяй текст

    await bot.sendMessage(chatId, replyText);
  });

  bot.onText(/\/me/, async (msg) => {
    const chatId = msg.chat.id;
    const user = getUserByTelegramId(String(msg.from.id));

    if (!user) {
      await bot.sendMessage(chatId, 'Сначала нажми /start');
      return;
    }

    const replyText = `👤 ${user.first_name}\n💰 Баланс: ${user.balance} ₽`;

    await bot.sendMessage(chatId, replyText);
  });

  bot.onText(/\/price(?:\s+(\w+))?/, async (msg, match) => {
    const chatId = msg.chat.id;
    const nftId = match[1];

    if (!nftId) {
      await bot.sendMessage(chatId, 'Напиши так:\n/price owl');
      return;
    }

    const nft = nftCatalog.find((item) => item.id === nftId);

    if (!nft) {
      await bot.sendMessage(chatId, 'Такого NFT нет в каталоге');
      return;
    }

    const replyText = `🖼️ ${nft.name}\n💰 Цена: ${nft.price} ₽`;

    await bot.sendMessage(chatId, replyText);
  });

  // ═══ УРОК 7: /help — перечисли команды в replyText ниже ═══
  bot.onText(/\/help/, async (msg) => {
    const chatId = msg.chat.id;

    const replyText = `📖 Команды:\n/start — начать\n/balance — баланс\n/deposit - пополнение\n/withdraw - вывод\n/mynft - мои NFT\n/help - справка\n/about - о проекте\n/ping - проверка работы бота\n/id - id твой Telegram ID\n/me - информация о пользователе`; // ← ТВОЯ ЗАДАЧА: допиши остальные

    await bot.sendMessage(chatId, replyText);
  });

  bot.onText(/\/ping/, async (msg) => {
    const chatId = msg.chat.id;

    const replyText = `👞 Бот работает`; // ← ТВОЯ ЗАДАЧА: допиши остальные

    await bot.sendMessage(chatId, replyText);
  });

  bot.onText(/\/about/, async (msg) => {
    const chatId = msg.chat.id;

    const replyText = 'Zeritime NFT - это платформа для покупки и продажи NFT. Здесь ты можешь купить и продать NFT, а также посмотреть свои NFT.';

    await bot.sendMessage(chatId, replyText);
  });

  bot.onText(/\/id/, async (msg) => {
    const chatId = msg.chat.id;

    const replyText = `🆔 Твой Telegram ID: ${msg.from.id}`;

    await bot.sendMessage(chatId, replyText);
  });
  
  // Список купленных NFT в боте
  bot.onText(/\/mynft/, async (msg) => {
    const chatId = msg.chat.id;
    const user = getUserByTelegramId(String(msg.from.id));

    if (!user) {
      await bot.sendMessage(chatId, 'Сначала нажми /start');
      return;
    }

    const nfts = getUserNfts(user.id);
    if (nfts.length === 0) {
      await bot.sendMessage(chatId, '🖼 У тебя пока нет NFT.\n\nОткрой Mini App → Смотреть NFT');
      return;
    }

    const lines = nfts.map((nft) => `• ${nft.nft_name} — ${nft.price_paid} ₽`).join('\n');
    await bot.sendMessage(chatId, `🖼 Твои NFT:\n\n${lines}`);
  });

  // Команда /admin — только для тебя
  bot.onText(/\/admin/, async (msg) => {
    const chatId = msg.chat.id;

    if (String(chatId) !== String(adminTelegramId)) {
      await bot.sendMessage(chatId, '⛔ Эта команда только для администратора.');
      return;
    }

    const pendingDeposits = getPendingDepositRequests();
    const pendingWithdrawals = getPendingWithdrawalRequests();
    const total = pendingDeposits.length + pendingWithdrawals.length;

    const text = total === 0
      ? '🔐 Админ-панель\n\nНет ожидающих запросов.'
      : `🔐 Админ-панель\n\n⏳ Пополнения: ${pendingDeposits.length}\n⏳ Выводы: ${pendingWithdrawals.length}\n\nПодтверждай кнопками в уведомлениях 👇`;

    await bot.sendMessage(chatId, text);
  });

  // Список пользователей — только админ
  bot.onText(/\/users/, async (msg) => {
    const chatId = msg.chat.id;

    if (String(chatId) !== String(adminTelegramId)) {
      await bot.sendMessage(chatId, '⛔ Эта команда только для администратора.');
      return;
    }

    const users = getAllUsers();
    if (users.length === 0) {
      await bot.sendMessage(chatId, '👥 Пользователей пока нет.');
      return;
    }

    const lines = users.map((user) => {
      const withdrawStatus = user.withdrawal_enabled ? '✅ вывод' : '🔒 вывод';
      return `👤 ${formatUserName(user)}\n🆔 ${user.telegram_id}\n💰 ${user.balance} ₽ · ${withdrawStatus}`;
    });

    await bot.sendMessage(chatId, `👥 Пользователи (${users.length}):\n\n${lines.join('\n\n')}`);
  });

  // Заблокировать вывод пользователю
  bot.onText(/\/blockwithdraw(?:\s+(\d+))?/, async (msg, match) => {
    const chatId = msg.chat.id;

    if (String(chatId) !== String(adminTelegramId)) {
      await bot.sendMessage(chatId, '⛔ Эта команда только для администратора.');
      return;
    }

    const targetId = match[1];
    if (!targetId) {
      await bot.sendMessage(chatId, '🔒 Напиши так:\n/blockwithdraw 8779645850');
      return;
    }

    const user = setWithdrawalEnabled(targetId, false);
    if (!user) {
      await bot.sendMessage(chatId, '❌ Пользователь не найден.');
      return;
    }

    await bot.sendMessage(
      chatId,
      `🔒 Вывод заблокирован для ${formatUserName(user)}`
    );
    await notifyUser(targetId, '⛔ Вывод средств для тебя временно отключён админом.');
  });

  // Разрешить вывод снова
  bot.onText(/\/allowwithdraw(?:\s+(\d+))?/, async (msg, match) => {
    const chatId = msg.chat.id;

    if (String(chatId) !== String(adminTelegramId)) {
      await bot.sendMessage(chatId, '⛔ Эта команда только для администратора.');
      return;
    }

    const targetId = match[1];
    if (!targetId) {
      await bot.sendMessage(chatId, '✅ Напиши так:\n/allowwithdraw 8779645850');
      return;
    }

    const user = setWithdrawalEnabled(targetId, true);
    if (!user) {
      await bot.sendMessage(chatId, '❌ Пользователь не найден.');
      return;
    }

    await bot.sendMessage(
      chatId,
      `✅ Вывод снова разрешён для ${formatUserName(user)}`
    );
    await notifyUser(targetId, '✅ Вывод средств снова доступен.');
  });

  // Кнопки «Подтвердить» / «Отклонить» у админа
  bot.on('callback_query', async (query) => {
    const data = query.data || '';

    const isDeposit = data.startsWith('dep_ok:') || data.startsWith('dep_no:');
    const isWithdrawal = data.startsWith('wdr_ok:') || data.startsWith('wdr_no:');

    if (!isDeposit && !isWithdrawal) return;

    if (String(query.from.id) !== String(adminTelegramId)) {
      await bot.answerCallbackQuery(query.id, { text: '⛔ Только для админа' });
      return;
    }

    const requestId = Number(data.split(':')[1]);
    const isApprove = data.startsWith('dep_ok:') || data.startsWith('wdr_ok:');

    let result;
    let amount;
    let successText;
    let userMessage;
    let adminMessage;

    if (isDeposit) {
      result = isApprove
        ? approveDepositRequest(requestId)
        : rejectDepositRequest(requestId);

      if (!result) {
        await bot.answerCallbackQuery(query.id, { text: 'Запрос уже обработан' });
        return;
      }

      amount = result.request.amount;
      successText = isApprove ? `✅ Начислено ${amount} ₽` : '❌ Отклонено';
      userMessage = isApprove
        ? `✅ Пополнение подтверждено!\n\n+${amount} ₽\n💰 Баланс: ${result.user.balance} ₽`
        : `❌ Запрос на пополнение ${amount} ₽ отклонён.`;
      adminMessage = isApprove
        ? `✅ Ты подтвердил пополнение ${amount} ₽ для ${formatUserName(result.user)}`
        : `❌ Ты отклонил пополнение ${amount} ₽ для ${formatUserName(result.user)}`;
    } else {
      result = isApprove
        ? approveWithdrawalRequest(requestId)
        : rejectWithdrawalRequest(requestId);

      if (!result) {
        await bot.answerCallbackQuery(query.id, {
          text: isApprove ? 'Недостаточно средств или запрос обработан' : 'Запрос уже обработан',
        });
        return;
      }

      amount = result.request.amount;
      successText = isApprove ? `✅ Выведено ${amount} ₽` : '❌ Отклонено';
      userMessage = isApprove
        ? `✅ Вывод подтверждён!\n\n−${amount} ₽\n💰 Баланс: ${result.user.balance} ₽`
        : `❌ Запрос на вывод ${amount} ₽ отклонён.`;
      adminMessage = isApprove
        ? `✅ Ты подтвердил вывод ${amount} ₽ для ${formatUserName(result.user)}`
        : `❌ Ты отклонил вывод ${amount} ₽ для ${formatUserName(result.user)}`;
    }

    await bot.answerCallbackQuery(query.id, { text: successText });

    try {
      await bot.editMessageReplyMarkup(
        { inline_keyboard: [] },
        { chat_id: query.message.chat.id, message_id: query.message.message_id }
      );
    } catch (_) {}

    await notifyUser(result.user.telegram_id, userMessage);
    await bot.sendMessage(adminTelegramId, adminMessage);
  });

  bot.on('polling_error', (error) => {
    console.error('Ошибка polling:', error.message);
  });

  return bot;
}

function getBot() {
  return bot;
}

/** Отправить уведомление админу из любого места сервера */
async function notifyAdmin(adminTelegramId, text) {
  if (!bot || !adminTelegramId) return;
  try {
    await bot.sendMessage(adminTelegramId, text);
  } catch (error) {
    console.error('Ошибка уведомления админу:', error.message);
  }
}

async function notifyUser(telegramId, text) {
  if (!bot || !telegramId) return;
  try {
    await bot.sendMessage(telegramId, text);
  } catch (error) {
    console.error('Ошибка уведомления пользователю:', error.message);
  }
}

async function sendDepositRequestToAdmin(adminTelegramId, request, user) {
  if (!bot || !adminTelegramId) return;

  const text =
    `💳 Запрос на пополнение!\n\n` +
    `👤 ${formatUserName(user)}\n` +
    `🆔 ${user.telegram_id}\n` +
    `💰 Сумма: ${request.amount} ₽\n` +
    `📊 Баланс сейчас: ${user.balance} ₽`;

  try {
    await bot.sendMessage(adminTelegramId, text, {
      reply_markup: {
        inline_keyboard: [
          [
            { text: '✅ Подтвердить', callback_data: `dep_ok:${request.id}` },
            { text: '❌ Отклонить', callback_data: `dep_no:${request.id}` },
          ],
        ],
      },
    });
  } catch (error) {
    console.error('Ошибка уведомления о пополнении:', error.message);
  }
}

function validateWithdrawal(user, amount) {
  if (!user.withdrawal_enabled) {
    return '⛔ Вывод для тебя временно отключён.';
  }
  if (amount < withdrawConfig.minAmount) {
    return `⛔ Минимальная сумма вывода: ${withdrawConfig.minAmount} ₽`;
  }
  if (user.balance < amount) {
    return `⛔ Недостаточно средств. Баланс: ${user.balance} ₽`;
  }
  return null;
}

async function sendWithdrawalRequestToAdmin(adminTelegramId, request, user) {
  if (!bot || !adminTelegramId) return;

  const text =
    `💸 Запрос на вывод!\n\n` +
    `👤 ${formatUserName(user)}\n` +
    `🆔 ${user.telegram_id}\n` +
    `💰 Сумма: ${request.amount} ₽\n` +
    `📊 Баланс сейчас: ${user.balance} ₽`;

  try {
    await bot.sendMessage(adminTelegramId, text, {
      reply_markup: {
        inline_keyboard: [
          [
            { text: '✅ Подтвердить', callback_data: `wdr_ok:${request.id}` },
            { text: '❌ Отклонить', callback_data: `wdr_no:${request.id}` },
          ],
        ],
      },
    });
  } catch (error) {
    console.error('Ошибка уведомления о выводе:', error.message);
  }
}

module.exports = {
  startBot,
  getBot,
  notifyAdmin,
  notifyUser,
  sendDepositRequestToAdmin,
  sendWithdrawalRequestToAdmin,
  validateWithdrawal,
  formatUserName,
};

const express = require('express');
const path = require('path');
const cors = require('cors');
const crypto = require('crypto');
const {
  findOrCreateUser,
  logActivity,
  getUserByTelegramId,
  getAllUsers,
  createDepositRequest,
  getUserNftIds,
  getUserNfts,
  buyNft,
  createWithdrawalRequest,
} = require('../db');
const nftCatalog = require('../nft-catalog');
const withdrawConfig = require('../withdraw-config');
const depositConfig = require('../deposit-config');
const {
  notifyAdmin,
  formatUserName,
  sendDepositRequestToAdmin,
  sendWithdrawalRequestToAdmin,
  validateWithdrawal,
} = require('../bot');

const router = express.Router();

function validateTelegramInitData(initData, botToken) {
  if (!initData || !botToken) return null;

  const params = new URLSearchParams(initData);
  const hash = params.get('hash');
  if (!hash) return null;

  params.delete('hash');

  const dataCheckString = [...params.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([key, value]) => `${key}=${value}`)
    .join('\n');

  const secretKey = crypto
    .createHmac('sha256', 'WebAppData')
    .update(botToken)
    .digest();

  const calculatedHash = crypto
    .createHmac('sha256', secretKey)
    .update(dataCheckString)
    .digest('hex');

  if (calculatedHash !== hash) return null;

  const userRaw = params.get('user');
  if (!userRaw) return null;

  try {
    return JSON.parse(userRaw);
  } catch {
    return null;
  }
}

router.post('/auth', async (req, res) => {
  const { initData } = req.body;
  const botToken = process.env.BOT_TOKEN;

  const telegramUser = validateTelegramInitData(initData, botToken);

  const isDev = process.env.NODE_ENV !== 'production';
  let userToRegister = telegramUser;

  if (!userToRegister && isDev && req.body.devUser) {
    userToRegister = req.body.devUser;
  }

  if (!userToRegister) {
    return res.status(401).json({ error: 'Неверные данные Telegram' });
  }

  const { user, isNew } = await findOrCreateUser(userToRegister);
  await logActivity(user.id, isNew ? 'registered' : 'opened_miniapp');

  const adminId = process.env.ADMIN_TELEGRAM_ID;
  if (isNew && adminId) {
    notifyAdmin(
      adminId,
      `🆕 Новый пользователь (через Mini App)!\n\n👤 ${formatUserName(user)}\n🆔 ${user.telegram_id}`
    );
  } else if (adminId) {
    notifyAdmin(
      adminId,
      `📱 Открыл Mini App\n\n👤 ${formatUserName(user)}\n🆔 ${user.telegram_id}`
    );
  }

  res.json({
    user: {
      id: user.id,
      telegram_id: user.telegram_id,
      username: user.username,
      first_name: user.first_name,
      balance: user.balance,
      withdrawal_enabled: Boolean(user.withdrawal_enabled),
    },
    isNew,
  });
});

router.get('/me', async (req, res) => {
  const telegramId = req.headers['x-telegram-id'];
  if (!telegramId) {
    return res.status(400).json({ error: 'Нужен заголовок x-telegram-id' });
  }

  const user = await getUserByTelegramId(telegramId);
  if (!user) {
    return res.status(404).json({ error: 'Пользователь не найден' });
  }

  res.json({
    id: user.id,
    telegram_id: user.telegram_id,
    username: user.username,
    first_name: user.first_name,
    balance: user.balance,
    withdrawal_enabled: Boolean(user.withdrawal_enabled),
  });
});

router.post('/deposit-request', async (req, res) => {
  const { telegramId, amount } = req.body;

  if (!telegramId || !amount || amount <= 0) {
    return res.status(400).json({ error: 'Нужны telegramId и amount' });
  }

  const user = await getUserByTelegramId(telegramId);
  if (!user) {
    return res.status(404).json({ error: 'Пользователь не найден' });
  }

  const request = await createDepositRequest(user.id, Number(amount));
  await logActivity(user.id, 'deposit_request', `Запрос ${amount} ₽`);

  const adminId = process.env.ADMIN_TELEGRAM_ID;
  if (adminId) {
    sendDepositRequestToAdmin(adminId, request, user);
  }

  res.json({ ok: true, requestId: request.id });
});

router.get('/deposit-info', (req, res) => {
  res.json({
    amounts: depositConfig.amounts,
  });
});

router.get('/withdraw-info', (req, res) => {
  res.json({
    minAmount: withdrawConfig.minAmount,
    amounts: withdrawConfig.amounts,
  });
});

router.post('/withdraw-request', async (req, res) => {
  const { telegramId, amount } = req.body;

  if (!telegramId || !amount || amount <= 0) {
    return res.status(400).json({ error: 'Нужны telegramId и amount' });
  }

  const user = await getUserByTelegramId(telegramId);
  if (!user) {
    return res.status(404).json({ error: 'Пользователь не найден' });
  }

  const validationError = validateWithdrawal(user, Number(amount));
  if (validationError) {
    return res.status(400).json({ error: validationError });
  }

  const request = await createWithdrawalRequest(user.id, Number(amount));
  await logActivity(user.id, 'withdrawal_request', `Запрос ${amount} ₽`);

  const adminId = process.env.ADMIN_TELEGRAM_ID;
  if (adminId) {
    sendWithdrawalRequestToAdmin(adminId, request, user);
  }

  res.json({ ok: true, requestId: request.id });
});

router.post('/action', async (req, res) => {
  const { telegramId, action, details } = req.body;

  if (!telegramId || !action) {
    return res.status(400).json({ error: 'Нужны telegramId и action' });
  }

  const user = await getUserByTelegramId(telegramId);
  if (!user) {
    return res.status(404).json({ error: 'Пользователь не найден' });
  }

  await logActivity(user.id, action, details || null);

  const adminId = process.env.ADMIN_TELEGRAM_ID;
  if (adminId) {
    notifyAdmin(
      adminId,
      `⚡ Действие: ${action}\n\n👤 ${formatUserName(user)}\n📝 ${details || '—'}`
    );
  }

  res.json({ ok: true });
});

router.get('/nfts', async (req, res) => {
  const telegramId = req.query.telegramId;
  if (!telegramId) {
    return res.status(400).json({ error: 'Нужен telegramId' });
  }

  const user = await getUserByTelegramId(telegramId);
  if (!user) {
    return res.status(404).json({ error: 'Пользователь не найден' });
  }

  res.json({
    catalog: nftCatalog,
    ownedIds: await getUserNftIds(user.id),
    owned: await getUserNfts(user.id),
    balance: user.balance,
  });
});

router.post('/nfts/buy', async (req, res) => {
  const { telegramId, nftId } = req.body;

  if (!telegramId || !nftId) {
    return res.status(400).json({ error: 'Нужны telegramId и nftId' });
  }

  const user = await getUserByTelegramId(telegramId);
  if (!user) {
    return res.status(404).json({ error: 'Пользователь не найден' });
  }

  const catalogItem = nftCatalog.find((item) => item.id === nftId);
  if (!catalogItem) {
    return res.status(404).json({ error: 'NFT не найден в каталоге' });
  }

  const result = await buyNft(user.id, nftId, catalogItem);

  if (result.error === 'already_owned') {
    return res.status(400).json({ error: 'Ты уже владеешь этим NFT' });
  }
  if (result.error === 'insufficient_balance') {
    return res.status(400).json({ error: 'Недостаточно средств на балансе' });
  }
  if (result.error) {
    return res.status(400).json({ error: 'Не удалось купить NFT' });
  }

  const adminId = process.env.ADMIN_TELEGRAM_ID;
  if (adminId) {
    notifyAdmin(
      adminId,
      `🖼 Покупка NFT!\n\n👤 ${formatUserName(result.user)}\n🎨 ${result.nft.name}\n💰 −${result.nft.price} ₽\n📊 Баланс: ${result.user.balance} ₽`
    );
  }

  res.json({
    ok: true,
    balance: result.user.balance,
    nft: result.nft,
  });
});

router.get('/admin/users', async (req, res) => {
  const adminId = req.headers['x-admin-telegram-id'];

  if (String(adminId) !== String(process.env.ADMIN_TELEGRAM_ID)) {
    return res.status(403).json({ error: 'Доступ запрещён' });
  }

  res.json({ users: await getAllUsers() });
});

module.exports = router;

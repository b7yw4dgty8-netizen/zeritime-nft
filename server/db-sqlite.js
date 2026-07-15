const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const dataDir = path.join(__dirname, '..', 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, 'app.db');
const db = new Database(dbPath);

db.pragma('journal_mode = WAL');

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    balance REAL DEFAULT 0,
    withdrawal_enabled INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now')),
    last_seen_at TEXT DEFAULT (datetime('now'))
  );

  CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT NOT NULL,
    details TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS deposit_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );

  CREATE TABLE IF NOT EXISTS user_nfts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    nft_id TEXT NOT NULL,
    nft_name TEXT NOT NULL,
    price_paid REAL NOT NULL,
    purchased_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, nft_id)
  );

  CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount REAL NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`;

db.exec(SCHEMA);

async function initDb() {
  // Таблицы SQLite создаются при загрузке модуля.
}

function findOrCreateUser(telegramUser) {
  const existing = db
    .prepare('SELECT * FROM users WHERE telegram_id = ?')
    .get(String(telegramUser.id));

  if (existing) {
    db.prepare(`
      UPDATE users
      SET username = ?, first_name = ?, last_name = ?, last_seen_at = datetime('now')
      WHERE telegram_id = ?
    `).run(
      telegramUser.username || null,
      telegramUser.first_name || null,
      telegramUser.last_name || null,
      String(telegramUser.id)
    );

    return {
      user: db.prepare('SELECT * FROM users WHERE telegram_id = ?').get(String(telegramUser.id)),
      isNew: false,
    };
  }

  const result = db.prepare(`
    INSERT INTO users (telegram_id, username, first_name, last_name)
    VALUES (?, ?, ?, ?)
  `).run(
    String(telegramUser.id),
    telegramUser.username || null,
    telegramUser.first_name || null,
    telegramUser.last_name || null
  );

  const user = db.prepare('SELECT * FROM users WHERE id = ?').get(result.lastInsertRowid);
  return { user, isNew: true };
}

function logActivity(userId, action, details = null) {
  db.prepare(`
    INSERT INTO activity_log (user_id, action, details)
    VALUES (?, ?, ?)
  `).run(userId, action, details);
}

function getUserByTelegramId(telegramId) {
  return db.prepare('SELECT * FROM users WHERE telegram_id = ?').get(String(telegramId));
}

function getAllUsers() {
  return db.prepare('SELECT * FROM users ORDER BY created_at DESC').all();
}

function getUserById(userId) {
  return db.prepare('SELECT * FROM users WHERE id = ?').get(userId);
}

function setWithdrawalEnabled(telegramId, enabled) {
  const user = getUserByTelegramId(telegramId);
  if (!user) return null;

  db.prepare(`
    UPDATE users SET withdrawal_enabled = ? WHERE telegram_id = ?
  `).run(enabled ? 1 : 0, String(telegramId));

  return getUserByTelegramId(telegramId);
}

function createDepositRequest(userId, amount) {
  const result = db.prepare(`
    INSERT INTO deposit_requests (user_id, amount, status)
    VALUES (?, ?, 'pending')
  `).run(userId, amount);

  return getDepositRequestById(result.lastInsertRowid);
}

function getDepositRequestById(requestId) {
  return db.prepare(`
    SELECT dr.*, u.telegram_id, u.username, u.first_name, u.last_name, u.balance
    FROM deposit_requests dr
    JOIN users u ON u.id = dr.user_id
    WHERE dr.id = ?
  `).get(requestId);
}

function getPendingDepositRequests() {
  return db.prepare(`
    SELECT dr.*, u.telegram_id, u.username, u.first_name
    FROM deposit_requests dr
    JOIN users u ON u.id = dr.user_id
    WHERE dr.status = 'pending'
    ORDER BY dr.created_at DESC
  `).all();
}

function approveDepositRequest(requestId) {
  const request = getDepositRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  db.prepare(`
    UPDATE deposit_requests
    SET status = 'approved', resolved_at = datetime('now')
    WHERE id = ?
  `).run(requestId);

  db.prepare(`
    UPDATE users SET balance = balance + ? WHERE id = ?
  `).run(request.amount, request.user_id);

  logActivity(request.user_id, 'deposit_approved', `+${request.amount} ₽`);

  return {
    request: getDepositRequestById(requestId),
    user: getUserById(request.user_id),
  };
}

function getUserNftIds(userId) {
  return db
    .prepare('SELECT nft_id FROM user_nfts WHERE user_id = ?')
    .all(userId)
    .map((row) => row.nft_id);
}

function getUserNfts(userId) {
  return db
    .prepare('SELECT * FROM user_nfts WHERE user_id = ? ORDER BY purchased_at DESC')
    .all(userId);
}

function buyNft(userId, nftId, catalogItem) {
  const user = getUserById(userId);
  if (!user) return { error: 'user_not_found' };

  const alreadyOwned = db
    .prepare('SELECT id FROM user_nfts WHERE user_id = ? AND nft_id = ?')
    .get(userId, nftId);
  if (alreadyOwned) return { error: 'already_owned' };

  if (user.balance < catalogItem.price) return { error: 'insufficient_balance' };

  const purchase = db.transaction(() => {
    db.prepare('UPDATE users SET balance = balance - ? WHERE id = ?').run(
      catalogItem.price,
      userId
    );
    db.prepare(`
      INSERT INTO user_nfts (user_id, nft_id, nft_name, price_paid)
      VALUES (?, ?, ?, ?)
    `).run(userId, nftId, catalogItem.name, catalogItem.price);
    logActivity(userId, 'nft_purchase', `${catalogItem.name} за ${catalogItem.price} ₽`);
  });

  purchase();

  return {
    user: getUserById(userId),
    nft: catalogItem,
  };
}

function giftNft(userId, nftId, catalogItem) {
  const user = getUserById(userId);
  if (!user) return { error: 'user_not_found' };

  const alreadyOwned = db
    .prepare('SELECT id FROM user_nfts WHERE user_id = ? AND nft_id = ?')
    .get(userId, nftId);
  if (alreadyOwned) return { error: 'already_owned' };

  db.prepare(`
    INSERT INTO user_nfts (user_id, nft_id, nft_name, price_paid)
    VALUES (?, ?, ?, ?)
  `).run(userId, nftId, catalogItem.name, 0);
  logActivity(userId, 'nft_gift', `Подарок: ${catalogItem.name}`);

  return {
    user: getUserById(userId),
    nft: catalogItem,
  };
}

function rejectDepositRequest(requestId) {
  const request = getDepositRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  db.prepare(`
    UPDATE deposit_requests
    SET status = 'rejected', resolved_at = datetime('now')
    WHERE id = ?
  `).run(requestId);

  logActivity(request.user_id, 'deposit_rejected', `${request.amount} ₽`);

  return {
    request: getDepositRequestById(requestId),
    user: getUserById(request.user_id),
  };
}

function createWithdrawalRequest(userId, amount) {
  const result = db.prepare(`
    INSERT INTO withdrawal_requests (user_id, amount, status)
    VALUES (?, ?, 'pending')
  `).run(userId, amount);

  return getWithdrawalRequestById(result.lastInsertRowid);
}

function getWithdrawalRequestById(requestId) {
  return db.prepare(`
    SELECT wr.*, u.telegram_id, u.username, u.first_name, u.last_name, u.balance
    FROM withdrawal_requests wr
    JOIN users u ON u.id = wr.user_id
    WHERE wr.id = ?
  `).get(requestId);
}

function getPendingWithdrawalRequests() {
  return db.prepare(`
    SELECT wr.*, u.telegram_id, u.username, u.first_name
    FROM withdrawal_requests wr
    JOIN users u ON u.id = wr.user_id
    WHERE wr.status = 'pending'
    ORDER BY wr.created_at DESC
  `).all();
}

function approveWithdrawalRequest(requestId) {
  const request = getWithdrawalRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  const user = getUserById(request.user_id);
  if (!user || user.balance < request.amount) return null;

  const approve = db.transaction(() => {
    db.prepare(`
      UPDATE withdrawal_requests
      SET status = 'approved', resolved_at = datetime('now')
      WHERE id = ?
    `).run(requestId);

    db.prepare(`
      UPDATE users SET balance = balance - ? WHERE id = ?
    `).run(request.amount, request.user_id);

    logActivity(request.user_id, 'withdrawal_approved', `−${request.amount} ₽`);
  });

  approve();

  return {
    request: getWithdrawalRequestById(requestId),
    user: getUserById(request.user_id),
  };
}

function rejectWithdrawalRequest(requestId) {
  const request = getWithdrawalRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  db.prepare(`
    UPDATE withdrawal_requests
    SET status = 'rejected', resolved_at = datetime('now')
    WHERE id = ?
  `).run(requestId);

  logActivity(request.user_id, 'withdrawal_rejected', `${request.amount} ₽`);

  return {
    request: getWithdrawalRequestById(requestId),
    user: getUserById(request.user_id),
  };
}

module.exports = {
  initDb,
  findOrCreateUser,
  logActivity,
  getUserByTelegramId,
  getUserById,
  getAllUsers,
  setWithdrawalEnabled,
  createDepositRequest,
  getDepositRequestById,
  getPendingDepositRequests,
  approveDepositRequest,
  rejectDepositRequest,
  getUserNftIds,
  getUserNfts,
  buyNft,
  giftNft,
  createWithdrawalRequest,
  getWithdrawalRequestById,
  getPendingWithdrawalRequests,
  approveWithdrawalRequest,
  rejectWithdrawalRequest,
};

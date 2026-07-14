const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
});

const SCHEMA = `
  CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    telegram_id TEXT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    balance DOUBLE PRECISION DEFAULT 0,
    withdrawal_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE TABLE IF NOT EXISTS activity_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
  );

  CREATE TABLE IF NOT EXISTS deposit_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
  );

  CREATE TABLE IF NOT EXISTS user_nfts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    nft_id TEXT NOT NULL,
    nft_name TEXT NOT NULL,
    price_paid DOUBLE PRECISION NOT NULL,
    purchased_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, nft_id)
  );

  CREATE TABLE IF NOT EXISTS withdrawal_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    amount DOUBLE PRECISION NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
  );
`;

async function initDb() {
  await pool.query(SCHEMA);
}

async function findOrCreateUser(telegramUser) {
  const telegramId = String(telegramUser.id);
  const existing = await pool.query('SELECT * FROM users WHERE telegram_id = $1', [telegramId]);

  if (existing.rows.length > 0) {
    await pool.query(
      `UPDATE users
       SET username = $1, first_name = $2, last_name = $3, last_seen_at = NOW()
       WHERE telegram_id = $4`,
      [
        telegramUser.username || null,
        telegramUser.first_name || null,
        telegramUser.last_name || null,
        telegramId,
      ]
    );

    const updated = await pool.query('SELECT * FROM users WHERE telegram_id = $1', [telegramId]);
    return { user: updated.rows[0], isNew: false };
  }

  const created = await pool.query(
    `INSERT INTO users (telegram_id, username, first_name, last_name)
     VALUES ($1, $2, $3, $4)
     RETURNING *`,
    [
      telegramId,
      telegramUser.username || null,
      telegramUser.first_name || null,
      telegramUser.last_name || null,
    ]
  );

  return { user: created.rows[0], isNew: true };
}

async function logActivity(userId, action, details = null) {
  await pool.query(
    'INSERT INTO activity_log (user_id, action, details) VALUES ($1, $2, $3)',
    [userId, action, details]
  );
}

async function getUserByTelegramId(telegramId) {
  const result = await pool.query('SELECT * FROM users WHERE telegram_id = $1', [String(telegramId)]);
  return result.rows[0] || null;
}

async function getAllUsers() {
  const result = await pool.query('SELECT * FROM users ORDER BY created_at DESC');
  return result.rows;
}

async function getUserById(userId) {
  const result = await pool.query('SELECT * FROM users WHERE id = $1', [userId]);
  return result.rows[0] || null;
}

async function setWithdrawalEnabled(telegramId, enabled) {
  const user = await getUserByTelegramId(telegramId);
  if (!user) return null;

  await pool.query('UPDATE users SET withdrawal_enabled = $1 WHERE telegram_id = $2', [
    enabled,
    String(telegramId),
  ]);

  return getUserByTelegramId(telegramId);
}

async function createDepositRequest(userId, amount) {
  const result = await pool.query(
    `INSERT INTO deposit_requests (user_id, amount, status)
     VALUES ($1, $2, 'pending')
     RETURNING id`,
    [userId, amount]
  );

  return getDepositRequestById(result.rows[0].id);
}

async function getDepositRequestById(requestId) {
  const result = await pool.query(
    `SELECT dr.*, u.telegram_id, u.username, u.first_name, u.last_name, u.balance
     FROM deposit_requests dr
     JOIN users u ON u.id = dr.user_id
     WHERE dr.id = $1`,
    [requestId]
  );
  return result.rows[0] || null;
}

async function getPendingDepositRequests() {
  const result = await pool.query(
    `SELECT dr.*, u.telegram_id, u.username, u.first_name
     FROM deposit_requests dr
     JOIN users u ON u.id = dr.user_id
     WHERE dr.status = 'pending'
     ORDER BY dr.created_at DESC`
  );
  return result.rows;
}

async function approveDepositRequest(requestId) {
  const request = await getDepositRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  await pool.query(
    `UPDATE deposit_requests
     SET status = 'approved', resolved_at = NOW()
     WHERE id = $1`,
    [requestId]
  );

  await pool.query('UPDATE users SET balance = balance + $1 WHERE id = $2', [
    request.amount,
    request.user_id,
  ]);

  await logActivity(request.user_id, 'deposit_approved', `+${request.amount} ₽`);

  return {
    request: await getDepositRequestById(requestId),
    user: await getUserById(request.user_id),
  };
}

async function getUserNftIds(userId) {
  const result = await pool.query('SELECT nft_id FROM user_nfts WHERE user_id = $1', [userId]);
  return result.rows.map((row) => row.nft_id);
}

async function getUserNfts(userId) {
  const result = await pool.query(
    'SELECT * FROM user_nfts WHERE user_id = $1 ORDER BY purchased_at DESC',
    [userId]
  );
  return result.rows;
}

async function buyNft(userId, nftId, catalogItem) {
  const user = await getUserById(userId);
  if (!user) return { error: 'user_not_found' };

  const owned = await pool.query(
    'SELECT id FROM user_nfts WHERE user_id = $1 AND nft_id = $2',
    [userId, nftId]
  );
  if (owned.rows.length > 0) return { error: 'already_owned' };

  if (user.balance < catalogItem.price) return { error: 'insufficient_balance' };

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query('UPDATE users SET balance = balance - $1 WHERE id = $2', [
      catalogItem.price,
      userId,
    ]);
    await client.query(
      `INSERT INTO user_nfts (user_id, nft_id, nft_name, price_paid)
       VALUES ($1, $2, $3, $4)`,
      [userId, nftId, catalogItem.name, catalogItem.price]
    );
    await client.query('INSERT INTO activity_log (user_id, action, details) VALUES ($1, $2, $3)', [
      userId,
      'nft_purchase',
      `${catalogItem.name} за ${catalogItem.price} ₽`,
    ]);
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }

  return {
    user: await getUserById(userId),
    nft: catalogItem,
  };
}

async function rejectDepositRequest(requestId) {
  const request = await getDepositRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  await pool.query(
    `UPDATE deposit_requests
     SET status = 'rejected', resolved_at = NOW()
     WHERE id = $1`,
    [requestId]
  );

  await logActivity(request.user_id, 'deposit_rejected', `${request.amount} ₽`);

  return {
    request: await getDepositRequestById(requestId),
    user: await getUserById(request.user_id),
  };
}

async function createWithdrawalRequest(userId, amount) {
  const result = await pool.query(
    `INSERT INTO withdrawal_requests (user_id, amount, status)
     VALUES ($1, $2, 'pending')
     RETURNING id`,
    [userId, amount]
  );

  return getWithdrawalRequestById(result.rows[0].id);
}

async function getWithdrawalRequestById(requestId) {
  const result = await pool.query(
    `SELECT wr.*, u.telegram_id, u.username, u.first_name, u.last_name, u.balance
     FROM withdrawal_requests wr
     JOIN users u ON u.id = wr.user_id
     WHERE wr.id = $1`,
    [requestId]
  );
  return result.rows[0] || null;
}

async function getPendingWithdrawalRequests() {
  const result = await pool.query(
    `SELECT wr.*, u.telegram_id, u.username, u.first_name
     FROM withdrawal_requests wr
     JOIN users u ON u.id = wr.user_id
     WHERE wr.status = 'pending'
     ORDER BY wr.created_at DESC`
  );
  return result.rows;
}

async function approveWithdrawalRequest(requestId) {
  const request = await getWithdrawalRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  const user = await getUserById(request.user_id);
  if (!user || user.balance < request.amount) return null;

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    await client.query(
      `UPDATE withdrawal_requests
       SET status = 'approved', resolved_at = NOW()
       WHERE id = $1`,
      [requestId]
    );
    await client.query('UPDATE users SET balance = balance - $1 WHERE id = $2', [
      request.amount,
      request.user_id,
    ]);
    await client.query('INSERT INTO activity_log (user_id, action, details) VALUES ($1, $2, $3)', [
      request.user_id,
      'withdrawal_approved',
      `−${request.amount} ₽`,
    ]);
    await client.query('COMMIT');
  } catch (error) {
    await client.query('ROLLBACK');
    throw error;
  } finally {
    client.release();
  }

  return {
    request: await getWithdrawalRequestById(requestId),
    user: await getUserById(request.user_id),
  };
}

async function rejectWithdrawalRequest(requestId) {
  const request = await getWithdrawalRequestById(requestId);
  if (!request || request.status !== 'pending') return null;

  await pool.query(
    `UPDATE withdrawal_requests
     SET status = 'rejected', resolved_at = NOW()
     WHERE id = $1`,
    [requestId]
  );

  await logActivity(request.user_id, 'withdrawal_rejected', `${request.amount} ₽`);

  return {
    request: await getWithdrawalRequestById(requestId),
    user: await getUserById(request.user_id),
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
  createWithdrawalRequest,
  getWithdrawalRequestById,
  getPendingWithdrawalRequests,
  approveWithdrawalRequest,
  rejectWithdrawalRequest,
};

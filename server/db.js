const usePostgres = Boolean(process.env.DATABASE_URL);
const driver = usePostgres ? require('./db-postgres') : require('./db-sqlite');

const METHODS = [
  'findOrCreateUser',
  'logActivity',
  'getUserByTelegramId',
  'getUserById',
  'getAllUsers',
  'setWithdrawalEnabled',
  'createDepositRequest',
  'getDepositRequestById',
  'getPendingDepositRequests',
  'approveDepositRequest',
  'rejectDepositRequest',
  'getUserNftIds',
  'getUserNfts',
  'buyNft',
  'giftNft',
  'createWithdrawalRequest',
  'getWithdrawalRequestById',
  'getPendingWithdrawalRequests',
  'approveWithdrawalRequest',
  'rejectWithdrawalRequest',
];

async function initDb() {
  await driver.initDb();
}

const dbApi = { initDb, usePostgres };

for (const method of METHODS) {
  dbApi[method] = async (...args) => {
    const result = driver[method](...args);
    return result instanceof Promise ? result : result;
  };
}

module.exports = dbApi;

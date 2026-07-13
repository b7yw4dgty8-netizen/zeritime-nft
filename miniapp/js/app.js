const tg = window.Telegram?.WebApp;

let currentUser = null;

const welcomeEl = document.getElementById('welcome');
const actionsEl = document.getElementById('actions');
const withdrawSectionEl = document.getElementById('withdraw-section');
const withdrawAmountsEl = document.getElementById('withdraw-amounts');
const withdrawHintEl = document.getElementById('withdraw-hint');
const nftSectionEl = document.getElementById('nft-section');
const nftListEl = document.getElementById('nft-list');
const myNftsEl = document.getElementById('my-nfts');
const statusEl = document.getElementById('status');
const balanceEl = document.getElementById('balance');

function showStatus(text, isSuccess = false) {
  statusEl.textContent = text;
  statusEl.classList.remove('hidden');
  statusEl.classList.toggle('success', isSuccess);
}

function updateBalance(balance) {
  balanceEl.textContent = `${balance} ₽`;
  if (currentUser) currentUser.balance = balance;
}

async function requestDeposit(amount) {
  const response = await fetch('/api/deposit-request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      telegramId: currentUser.telegram_id,
      amount,
    }),
  });

  if (!response.ok) {
    showStatus('Не удалось отправить запрос. Попробуй ещё раз.');
    return;
  }

  showStatus(`Запрос на ${amount} ₽ отправлен. Жди подтверждения админа.`, true);
}

async function requestWithdraw(amount) {
  const response = await fetch('/api/withdraw-request', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      telegramId: currentUser.telegram_id,
      amount,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    showStatus(data.error || 'Не удалось отправить запрос на вывод.');
    return;
  }

  showStatus(`Запрос на вывод ${amount} ₽ отправлен. Жди подтверждения админа.`, true);
}

async function loadWithdrawSection() {
  const response = await fetch('/api/withdraw-info');
  if (!response.ok) {
    showStatus('Не удалось загрузить настройки вывода.');
    return;
  }

  const data = await response.json();
  withdrawHintEl.textContent = `Минимум ${data.minAmount} ₽. Выбери сумму:`;

  const validAmounts = data.amounts.filter((amount) => amount >= data.minAmount);

  withdrawAmountsEl.innerHTML = validAmounts
    .map(
      (amount) => `
        <button class="btn btn-amount btn-withdraw-amount" data-amount="${amount}">
          ${amount} ₽
        </button>
      `
    )
    .join('');

  if (validAmounts.length === 0) {
    withdrawAmountsEl.innerHTML = '<p class="empty-hint">Нет готовых кнопок — введи сумму ниже</p>';
  }

  withdrawAmountsEl.querySelectorAll('.btn-withdraw-amount').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await requestWithdraw(Number(btn.dataset.amount));
    });
  });
}

function renderMyNfts(owned) {
  if (!owned.length) {
    myNftsEl.innerHTML = '<p class="empty-hint">Пока пусто — купи что-нибудь из каталога</p>';
    return;
  }

  myNftsEl.innerHTML = owned
    .map(
      (item) => `
        <div class="my-nft-item">
          <span>✅</span>
          <span>${item.nft_name} · ${item.price_paid} ₽</span>
        </div>
      `
    )
    .join('');
}

function renderNftCatalog(catalog, ownedIds, balance) {
  nftListEl.innerHTML = catalog
    .map((nft) => {
      const owned = ownedIds.includes(nft.id);
      const canAfford = balance >= nft.price;
      const disabled = owned || !canAfford;
      let buttonText = 'Купить';

      if (owned) buttonText = 'Твой';
      else if (!canAfford) buttonText = 'Мало ₽';

      const preview = nft.imageUrl
        ? `<img class="nft-image" src="${nft.imageUrl}" alt="${nft.name}">`
        : `<div class="nft-emoji">${nft.emoji}</div>`;

      return `
        <div class="nft-card">
          ${preview}
          <div class="nft-info">
            <div class="nft-name">${nft.name}</div>
            <div class="nft-desc">${nft.description}</div>
            <div class="nft-price">${nft.price} ₽</div>
          </div>
          <button
            class="btn btn-buy"
            data-nft-id="${nft.id}"
            ${disabled ? 'disabled' : ''}
          >${buttonText}</button>
        </div>
      `;
    })
    .join('');

  nftListEl.querySelectorAll('.btn-buy:not([disabled])').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await buyNft(btn.dataset.nftId);
    });
  });
}

async function loadNftCatalog() {
  const response = await fetch(`/api/nfts?telegramId=${currentUser.telegram_id}`);
  if (!response.ok) {
    showStatus('Не удалось загрузить каталог NFT.');
    return;
  }

  const data = await response.json();
  updateBalance(data.balance);
  renderNftCatalog(data.catalog, data.ownedIds, data.balance);
  renderMyNfts(data.owned);
}

async function buyNft(nftId) {
  const response = await fetch('/api/nfts/buy', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      telegramId: currentUser.telegram_id,
      nftId,
    }),
  });

  const data = await response.json();

  if (!response.ok) {
    showStatus(data.error || 'Не удалось купить NFT.');
    return;
  }

  updateBalance(data.balance);
  showStatus(`Куплено: ${data.nft.name}! Баланс: ${data.balance} ₽`, true);
  await loadNftCatalog();
}

async function logAction(action, details) {
  if (!currentUser) return;

  await fetch('/api/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      telegramId: currentUser.telegram_id,
      action,
      details,
    }),
  });
}

async function login() {
  const isTelegram = Boolean(tg?.initData);
  let body = {};

  if (isTelegram) {
    tg.ready();
    tg.expand();
    body = { initData: tg.initData };
  } else {
    body = {
      devUser: {
        id: 999999001,
        first_name: 'Тестовый',
        username: 'test_user',
      },
    };
    showStatus('Режим разработки: тестовый пользователь.');
  }

  const response = await fetch('/api/auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    welcomeEl.querySelector('h1').textContent = 'Ошибка входа';
    welcomeEl.querySelector('p').textContent = 'Проверь сервер и .env';
    return;
  }

  const data = await response.json();
  currentUser = data.user;

  const name = currentUser.first_name || currentUser.username || 'друг';
  welcomeEl.querySelector('h1').textContent = `Привет, ${name}! 👋`;
  welcomeEl.querySelector('p').textContent = 'Выбери сумму пополнения или другую кнопку.';

  updateBalance(currentUser.balance);
  actionsEl.classList.remove('hidden');
}

document.querySelectorAll('.btn-amount').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const amount = Number(btn.dataset.amount);
    await requestDeposit(amount);
  });
});

document.getElementById('btn-withdraw').addEventListener('click', async () => {
  welcomeEl.classList.add('hidden');
  actionsEl.classList.add('hidden');
  withdrawSectionEl.classList.remove('hidden');
  await loadWithdrawSection();
});

document.getElementById('btn-back-withdraw').addEventListener('click', () => {
  withdrawSectionEl.classList.add('hidden');
  welcomeEl.classList.remove('hidden');
  actionsEl.classList.remove('hidden');
});

document.getElementById('btn-withdraw-custom').addEventListener('click', async () => {
  const input = document.getElementById('withdraw-custom');
  const amount = Number(input.value);

  if (!amount || amount <= 0) {
    showStatus('Введи сумму больше нуля.');
    return;
  }

  await requestWithdraw(amount);
  input.value = '';
});

document.getElementById('btn-nft').addEventListener('click', async () => {
  welcomeEl.classList.add('hidden');
  actionsEl.classList.add('hidden');
  nftSectionEl.classList.remove('hidden');
  await loadNftCatalog();
});

document.getElementById('btn-back').addEventListener('click', () => {
  nftSectionEl.classList.add('hidden');
  welcomeEl.classList.remove('hidden');
  actionsEl.classList.remove('hidden');
});

login().catch((error) => {
  welcomeEl.querySelector('h1').textContent = 'Ошибка';
  welcomeEl.querySelector('p').textContent = error.message;
});

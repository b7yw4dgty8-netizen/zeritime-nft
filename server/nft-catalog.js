/**
 * ═══════════════════════════════════════════════════════════
 *  КАТАЛОГ NFT — ЭТО ТВОЙ ФАЙЛ. Правь его сам.
 * ═══════════════════════════════════════════════════════════
 *
 *  id          — уникальный ключ (латиница, без пробелов)
 *  name        — название, видит пользователь
 *  price       — цена в рублях (списывается с баланса)
 *  emoji       — иконка, если нет картинки
 *  imageUrl    — ссылка на картинку (необязательно)
 *  description — короткое описание
 *
 *  Чтобы добавить второй NFT — скопируй блок { ... } и вставь запятую после предыдущего.
 */

module.exports = [
  {
    id: 'starter',
    name: 'Brains Together',  // ← ТВОЯ ЗАДАЧА: поменяй название
    price: 300,              // ← ТВОЯ ЗАДАЧА: поменяй цену
    emoji: '🎨',
    imageUrl: 'https://i.ibb.co/v6VHrcsp/images.jpg',
    description: 'Твой первый NFT в коллекции',
  },
  {
    id: 'owl',
    name: 'My Owl',
    price: 650,
    emoji: '🦉',
    imageUrl: 'https://i.ibb.co/qMbgmBng/146121854812165290.png',
    description: 'I drawed it for memory about my old owl pet',
  },
  {
    id: 'blue-cube',
    name: 'Blue Cube',
    price: '5000',
    emoji: '🧊',
    imageUrl : 'https://i.ibb.co/q3fMnM1h/3d-rendering-geometric-cube-23-2150979614-jpg.avif',
    descriptiom: 'Blue Cube is a cube that is blue',
  },
];
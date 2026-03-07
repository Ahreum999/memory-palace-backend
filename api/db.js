const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://postgres:YqPFZxFQtNzOMREvzqLuNInEHSjhORbY@maglev.proxy.rlwy.net:44365/railway',
  ssl: { rejectUnauthorized: false }
});

async function initDB() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS sentences (
      id SERIAL PRIMARY KEY,
      text TEXT NOT NULL UNIQUE,
      source VARCHAR(50),
      extra TEXT,
      image TEXT,
      added DATE DEFAULT CURRENT_DATE
    )
  `);
  console.log('Database ready');
}

async function saveSentences(sentences) {
  let added = 0;
  for (const s of sentences) {
    try {
      await pool.query(
        `INSERT INTO sentences (text, source, extra, image, added)
         VALUES ($1, $2, $3, $4, $5)
         ON CONFLICT (text) DO NOTHING`,
        [s.text, s.source, s.extra || '', s.image || null, s.added || new Date().toISOString().split('T')[0]]
      );
      added++;
    } catch (err) {
      // skip duplicates
    }
  }
  return added;
}

async function getSentences(limit = 500) {
  const result = await pool.query(
    `SELECT text, source, extra, image FROM sentences 
     ORDER BY RANDOM() LIMIT $1`,
    [limit]
  );
  return result.rows;
}

async function getStats() {
  const result = await pool.query(
    `SELECT source, COUNT(*) as count 
     FROM sentences 
     GROUP BY source`
  );
  const stats = {};
  let total = 0;
  for (const row of result.rows) {
    stats[row.source] = parseInt(row.count);
    total += parseInt(row.count);
  }
  return { stats, total };
}

module.exports = { initDB, saveSentences, getSentences, getStats };
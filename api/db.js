const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// How many to keep in live DB after archiving
const KEEP_COUNT = 5000;
// Trigger archiving when total exceeds this
const ARCHIVE_THRESHOLD = 10000;

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
  const count = await pool.query('SELECT COUNT(*) FROM sentences');
  console.log(`Database ready — ${count.rows[0].count} sentences`);
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

// Feed: newest sentences first
async function getSentences(limit = 500) {
  const result = await pool.query(
    `SELECT text, source, extra, image, added FROM sentences
     ORDER BY id DESC
     LIMIT $1`,
    [limit]
  );
  return result.rows;
}

async function getStats() {
  const result = await pool.query(
    `SELECT source, COUNT(*)::int as count
     FROM sentences
     GROUP BY source`
  );
  const stats = {};
  let total = 0;
  for (const row of result.rows) {
    stats[row.source] = row.count;
    total += row.count;
  }
  stats.total = total;
  return stats;
}

// Get total sentence count
async function getTotal() {
  const result = await pool.query('SELECT COUNT(*)::int as count FROM sentences');
  return result.rows[0].count;
}

// Get the oldest sentences (the ones to archive)
async function getOldestSentences(count) {
  const result = await pool.query(
    `SELECT id, text, source, extra, image, added FROM sentences
     ORDER BY id ASC
     LIMIT $1`,
    [count]
  );
  return result.rows;
}

// Delete sentences by their IDs
async function deleteSentencesById(ids) {
  if (ids.length === 0) return 0;
  const result = await pool.query(
    `DELETE FROM sentences WHERE id = ANY($1)`,
    [ids]
  );
  return result.rowCount;
}

// Full export (for manual /archive/export endpoint)
async function getAllSentences() {
  const result = await pool.query(
    `SELECT id, text, source, extra, image, added
     FROM sentences
     ORDER BY id DESC`
  );
  return result.rows;
}

module.exports = {
  initDB, saveSentences, getSentences, getStats,
  getAllSentences, getTotal, getOldestSentences, deleteSentencesById,
  KEEP_COUNT, ARCHIVE_THRESHOLD
};

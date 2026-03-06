const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(cors());

const DATA_FILE = path.join(__dirname, '../data/sentences.json');

// GET /feed — returns N random sentences
app.get('/feed', (req, res) => {
  try {
    const raw = fs.readFileSync(DATA_FILE, 'utf-8');
    const all = JSON.parse(raw);

    // Shuffle and return 50 lines
    const shuffled = all.sort(() => Math.random() - 0.5);
    const lines = shuffled.slice(0, 50);

    res.json({ lines });
  } catch (err) {
    res.status(500).json({ error: 'Could not load sentences', lines: [] });
  }
});

// GET /health — just to check if server is alive
app.get('/health', (req, res) => res.json({ status: 'ok' }));

const PORT = process.env.PORT || 3001;
app.listen(PORT, () => console.log(`API running on port ${PORT}`));

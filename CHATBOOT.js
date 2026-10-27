import express from 'express';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';
import cors from 'cors';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { DatabaseSync } from 'node:sqlite';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load environment variables from .env or process.env
if (fs.existsSync(path.join(__dirname, '.env'))) {
    dotenv.config({ path: path.join(__dirname, '.env') });
} else if (fs.existsSync(path.join(__dirname, 'process.env'))) {
    dotenv.config({ path: path.join(__dirname, 'process.env') });
} else {
    dotenv.config();
}

const app = express();

app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '1mb' }));
app.use(express.urlencoded({ extended: true }));
// Serve all project static files (HTML, CSS, images, etc.)
app.use(express.static(__dirname));

// Initialize feedback SQLite database
const dbPath = path.join(__dirname, 'feedback.db');
const db = new DatabaseSync(dbPath);

db.exec(`
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        feedback TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
`);

if (!process.env.GEMINI_API_KEY) {
    console.error('ERROR: GEMINI_API_KEY is missing from .env or process.env');
    process.exit(1);
}

const ai = new GoogleGenAI({
    apiKey: process.env.GEMINI_API_KEY
});

const MODEL_NAME = process.env.GEMINI_MODEL || 'gemini-3.6-flash';

const SYSTEM_INSTRUCTION = `
You are "Dripora Bot", an artisan AI barista for Dripora Coffee Shop.

Your goals:
1. Greet customers warmly and answer questions about Dripora's menu,
   coffee origin, and dietary options.
2. Help customers build their order.
3. Recommend coffee based on their preferences.
4. Keep answers concise, friendly, and modern.
5. Do not invent products or prices that are not listed below.

MENU:

Single Origin Espresso:
$3.50

Signature Dripora Latte:
Small: $5.00
Medium: $5.80
Large: $6.40

Cold Brew Special:
Medium: $4.50
Large: $5.20

Artisan Pastries:
Butter Croissant: $3.50
Chocolate Croissant: $4.00
Vegan Cookie: $3.00

ADD-ONS:
Oat Milk: +$0.80
Almond Milk: +$0.80
Vanilla Syrup: +$0.50
Hazelnut Syrup: +$0.50

Keep responses aligned with Dripora's minimalist aesthetic.
`;

function normalizeHistory(history) {
    if (!Array.isArray(history)) return [];

    return history
        .filter(item =>
            item &&
            (item.role === 'user' || item.role === 'model') &&
            typeof item.content === 'string' &&
            item.content.trim() !== ''
        )
        .slice(-20)
        .map(item => ({
            role: item.role,
            parts: [{ text: item.content.trim() }]
        }));
}

// Default route opens chatboot.html
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'chatboot.html'));
});

// Health check endpoint
app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', model: MODEL_NAME, hasApiKey: Boolean(process.env.GEMINI_API_KEY) });
});

// Feedback submission endpoint (saves to feedback.db and links to home.html)
app.post('/submit-feedback', (req, res) => {
    try {
        const { name, email, feedback } = req.body || {};

        if (!name || !email || !feedback) {
            return res.status(400).send('Name, email, and feedback are required.');
        }

        const stmt = db.prepare('INSERT INTO feedback (name, email, feedback) VALUES (?, ?, ?)');
        stmt.run(name.trim(), email.trim(), feedback.trim());

        console.log(`[Feedback] Saved feedback from: ${name.trim()} <${email.trim()}>`);

        const isJson = req.xhr || req.headers.accept?.includes('application/json') || req.is('json');
        if (isJson) {
            return res.json({ success: true, redirect: 'home.html' });
        }

        return res.redirect('/home.html');
    } catch (error) {
        console.error('Error saving feedback:', error);
        return res.status(500).send('Error saving feedback to database.');
    }
});

// Alias routes for convenience
app.post('/feedback', (req, res, next) => {
    req.url = '/submit-feedback';
    app.handle(req, res, next);
});

app.post('/add-user', (req, res, next) => {
    req.url = '/submit-feedback';
    app.handle(req, res, next);
});

// View saved feedback entries (JSON API)
app.get('/api/feedback', (req, res) => {
    try {
        const stmt = db.prepare('SELECT * FROM feedback ORDER BY id DESC');
        res.json(stmt.all());
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.post('/api/chat', async (req, res) => {
    try {
        const { message, history } = req.body ?? {};

        if (typeof message !== 'string' || message.trim() === '') {
            return res.status(400).json({ error: 'Message is required.' });
        }

        const contents = normalizeHistory(history);
        contents.push({
            role: 'user',
            parts: [{ text: message.trim() }]
        });

        const response = await ai.models.generateContent({
            model: MODEL_NAME,
            contents: contents,
            config: {
                systemInstruction: SYSTEM_INSTRUCTION
            }
        });

        const reply = response?.text?.trim();

        if (!reply) {
            throw new Error('Gemini returned an empty response.');
        }

        res.json({ reply });
    } catch (error) {
        console.error('Gemini API Error:', error);
        res.status(500).json({
            error: error?.message || 'Failed to generate response. Please try again.'
        });
    }
});

const PORT = Number(process.env.PORT) || 3000;

app.listen(PORT, () => {
    console.log(`Dripora server running at http://localhost:${PORT}`);
    console.log(`Using model: ${MODEL_NAME}`);
});
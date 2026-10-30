from pathlib import Path
import re, shutil

base = Path("/mnt/data")
html_path = base / "chatboot.html"
css_path = base / "chatboot.css"
js_path = base / "CHATBOOT.js"
env_path = base / "process.env"

# Keep the user's original files intact; create fixed copies.
fixed_html = base / "chatboot_fixed.html"
fixed_css = base / "chatboot_fixed.css"
fixed_js = base / "CHATBOOT_fixed.js"
fixed_env = base / "process_env_fixed.env"

# Read source files.
html = html_path.read_text(encoding="utf-8")
css = css_path.read_text(encoding="utf-8")
js = js_path.read_text(encoding="utf-8")
env = env_path.read_text(encoding="utf-8")

# 1) Replace the client-side Gemini implementation with a safe API call.
# The original HTML exposes a Gemini API key placeholder/client-side setup.
script = r'''<script>
    let chatHistory = [];

    function updateAlgeriaClock() {
        const options = {
            timeZone: 'Africa/Algiers',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: true
        };
        const formatter = new Intl.DateTimeFormat('en-US', options);
        const clockEl = document.getElementById('algeria-clock');
        if (clockEl) clockEl.textContent = `ALG ${formatter.format(new Date())}`;
    }

    updateAlgeriaClock();
    setInterval(updateAlgeriaClock, 1000);

    async function sendMessage() {
        const input = document.getElementById('userInput');
        const text = input.value.trim();
        if (!text) return;

        appendMessage('user', text);
        input.value = '';

        const sendButton = document.querySelector('.input-box button');
        if (sendButton) sendButton.disabled = true;

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    history: chatHistory
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate response');
            }

            const replyText = data.reply || 'Sorry, I did not receive a response.';

            chatHistory.push({ role: 'user', content: text });
            chatHistory.push({ role: 'model', content: replyText });

            appendMessage('assistant', replyText);
        } catch (err) {
            console.error('Chat error:', err);
            appendMessage(
                'assistant',
                'Sorry, I am having trouble connecting right now. Please try again.'
            );
        } finally {
            if (sendButton) sendButton.disabled = false;
            input.focus();
        }
    }

    function appendMessage(role, text) {
        const container = document.getElementById('messages');
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${role}`;

        const content = document.createElement('div');
        content.className = 'message-content';

        // textContent prevents HTML/script injection from chatbot responses.
        content.textContent = text;

        msgDiv.appendChild(content);
        container.appendChild(msgDiv);
        container.scrollTop = container.scrollHeight;
    }

    function resetChat() {
        chatHistory = [];

        document.getElementById('messages').innerHTML = `
            <div class="message assistant">
                <div class="message-content">
                    👋 Welcome to <strong>Dripora</strong>! How can I help you today?
                </div>
            </div>`;
    }

    window.sendMessage = sendMessage;
    window.resetChat = resetChat;
</script>'''

# Replace the module script at the bottom of HTML.
html_fixed = re.sub(
    r'<script type="module">.*?</script>',
    script,
    html,
    flags=re.DOTALL
)

# 2) Add a few reliability/accessibility styles.
css_fixed = css.rstrip() + r'''

/* Chat reliability */
.input-box button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.message-content {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 768px) {
  .main-content {
    padding: 0 1rem;
  }

  #f1 {
    margin-top: 7rem;
  }

  .messages {
    padding: 16px;
  }

  .message-content {
    max-width: 90%;
  }

  .input-area {
    padding: 12px;
  }
}
'''

# 3) Replace server with a more robust version.
js_fixed = r'''import express from 'express';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';
import cors from 'cors';

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json({ limit: '1mb' }));
app.use(express.static('public'));

if (!process.env.GEMINI_API_KEY) {
  console.error('Missing GEMINI_API_KEY in environment.');
  process.exit(1);
}

const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const SYSTEM_INSTRUCTION = `
You are "Dripora Bot", an artisan AI barista for Dripora Coffee Shop.

Your goals:
1. Greet customers warmly and answer questions about Dripora's menu, coffee origin, and dietary options.
2. Guide customers to build their order (sizes, milk alternatives, flavor shots).
3. Provide coffee recommendations based on preference (espresso roast strength, sweet vs bitter balance).

MENU DETAILS:
- Single Origin Espresso: $3.50
- Signature Dripora Latte: $5.00 (S), $5.80 (M), $6.40 (L)
- Cold Brew Special: $4.50 (M), $5.20 (L)
- Artisan Pastries: Butter Croissant ($3.50), Chocolate Croissant ($4.00), Vegan Cookie ($3.00)
- Add-ons: Oat/Almond Milk (+$0.80), Vanilla/Hazelnut Syrup (+$0.50)

Keep responses concise, modern, friendly, and aligned with Dripora's minimalist visual aesthetic.
Do not invent menu items, prices, ingredients, opening hours, or policies that are not provided.
`;

function normalizeHistory(history) {
  if (!Array.isArray(history)) return [];

  return history
    .filter(
      (item) =>
        item &&
        (item.role === 'user' || item.role === 'model') &&
        typeof item.content === 'string' &&
        item.content.trim()
    )
    .slice(-20)
    .map((item) => ({
      role: item.role,
      parts: [{ text: item.content.trim() }]
    }));
}

app.post('/api/chat', async (req, res) => {
  try {
    const { history, message } = req.body ?? {};

    if (typeof message !== 'string' || !message.trim()) {
      return res.status(400).json({ error: 'Message is required.' });
    }

    const contents = normalizeHistory(history);
    contents.push({
      role: 'user',
      parts: [{ text: message.trim() }]
    });

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents,
      config: {
        systemInstruction: SYSTEM_INSTRUCTION
      }
    });

    const reply = response?.text?.trim();

    if (!reply) {
      throw new Error('Gemini returned an empty response.');
    }

    res.json({ reply });
  } catch (err) {
    console.error('Gemini API error:', err);
    res.status(500).json({
      error: 'Failed to generate response. Please try again.'
    });
  }
});

const PORT = Number(process.env.PORT) || 3000;

app.listen(PORT, () => {
  console.log(`Dripora server running on http://localhost:${PORT}`);
});
'''

# 4) Do not reproduce the exposed key. Make a safe env template.
env_fixed = "GEMINI_API_KEY=PUT_YOUR_NEW_GEMINI_API_KEY_HERE\nPORT=3000\n"

fixed_html.write_text(html_fixed, encoding="utf-8")
fixed_css.write_text(css_fixed, encoding="utf-8")
fixed_js.write_text(js_fixed, encoding="utf-8")
fixed_env.write_text(env_fixed, encoding="utf-8")

print("Created fixed files:")
for p in (fixed_html, fixed_css, fixed_js, fixed_env):
    print(p)

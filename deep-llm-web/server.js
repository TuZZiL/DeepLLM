const express = require('express');
const cors = require('cors');
const { OpenAI } = require('openai');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.static('public'));

const openai = new OpenAI({
  apiKey: process.env.NVAPI_KEY,
  baseURL: 'https://integrate.api.nvidia.com/v1'
});

app.get('/api/chat', async (req, res) => {
  try {
    const messages = JSON.parse(req.query.messages);
    
    const temperature = parseFloat(req.query.temperature);
    const top_p = parseFloat(req.query.top_p);
    const frequency_penalty = parseFloat(req.query.frequency_penalty);
    const presence_penalty = parseFloat(req.query.presence_penalty);
    const max_tokens = parseInt(req.query.max_tokens);

    const completion = await openai.chat.completions.create({
      model: "deepseek-ai/deepseek-r1",
      messages,
      temperature: isNaN(temperature) ? 0.6 : temperature,
      top_p: isNaN(top_p) ? 0.7 : top_p,
      frequency_penalty: isNaN(frequency_penalty) ? 0 : frequency_penalty,
      presence_penalty: isNaN(presence_penalty) ? 0 : presence_penalty,
      max_tokens: isNaN(max_tokens) ? 4096 : max_tokens,
      stream: true
    });

    res.setHeader('Content-Type', 'text/event-stream');
    
    for await (const chunk of completion) {
      const content = chunk.choices[0]?.delta?.content || '';
      const isThinking = content.includes('<think>');
      
      res.write(`data: ${JSON.stringify({
        type: isThinking ? 'thinking' : 'response',
        content: isThinking ? content.replace(/<think>/g, '') : content
      })}\n\n`);
    }
    
    res.end();

  } catch (error) {
    console.error('API Error:', error);
    res.status(500).json({ 
      error: 'AI service error',
      details: error.message 
    });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});

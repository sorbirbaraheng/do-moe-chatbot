/**
 * Simple Pinecone Proxy Server
 * Run with: node server/pinecone-proxy.js
 */

import express from 'express';
import cors from 'cors';

const app = express();
const PORT = 3001;

// Enable CORS for all origins (dev only)
app.use(cors());
app.use(express.json());

// Proxy endpoint for Pinecone
app.post('/api/pinecone/:action', async (req, res) => {
    const { action } = req.params;
    const pineconeHost = req.headers['x-pinecone-host'];
    const apiKey = req.headers['api-key'];

    if (!pineconeHost || !apiKey) {
        return res.status(400).json({ error: 'Missing X-Pinecone-Host or Api-Key header' });
    }

    const targetUrl = `https://${pineconeHost.replace(/^https?:\/\//, '')}/${action}`;

    console.log(`[Proxy] ${action} -> ${targetUrl}`);

    try {
        const response = await fetch(targetUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Api-Key': apiKey
            },
            body: JSON.stringify(req.body)
        });

        const data = await response.json();

        if (!response.ok) {
            console.error(`[Proxy] Error ${response.status}:`, data);
            return res.status(response.status).json(data);
        }

        console.log(`[Proxy] Success! Matches: ${data.matches?.length || 'N/A'}`);
        res.json(data);
    } catch (error) {
        console.error('[Proxy] Request failed:', error);
        res.status(500).json({ error: 'Proxy request failed', details: error.message });
    }
});

app.listen(PORT, () => {
    console.log(`🚀 Pinecone Proxy Server running on http://localhost:${PORT}`);
    console.log(`   POST /api/pinecone/query - Query vectors`);
    console.log(`   POST /api/pinecone/describe_index_stats - Get index stats`);
});

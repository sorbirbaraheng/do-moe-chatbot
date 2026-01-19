/**
 * Native Pinecone Integration Service
 * Connects directly to Pinecone without requiring n8n or proxy
 */

import { AdminConfig } from '../contexts/AdminConfigContext';

interface PineconeMatch {
    id: string;
    score: number;
    metadata?: {
        text?: string;
        content?: string;
        title?: string;
        source?: string;
        [key: string]: any;
    };
}

interface PineconeQueryResponse {
    matches: PineconeMatch[];
    namespace: string;
}

/**
 * Generate embedding using Gemini's embedding model
 */
export async function generateEmbedding(
    text: string,
    apiKey: string
): Promise<number[] | null> {
    try {
        console.log('[Pinecone] Generating embedding for text:', text.substring(0, 50) + '...');
        const response = await fetch(
            `https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key=${apiKey}`,
            {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model: 'models/text-embedding-004',
                    content: { parts: [{ text }] },
                    taskType: 'RETRIEVAL_QUERY'
                })
            }
        );

        if (!response.ok) {
            console.error('[Pinecone] Embedding API error:', response.status, await response.text());
            return null;
        }

        const data = await response.json();
        const embedding = data.embedding?.values || null;

        if (embedding) {
            console.log('[Pinecone] Embedding generated successfully! Length:', embedding.length);
        } else {
            console.error('[Pinecone] Embedding result is empty/null');
        }

        return embedding;
    } catch (error) {
        console.error('[Pinecone] Embedding generation failed:', error);
        return null;
    }
}

/**
 * Query Pinecone directly using the generated embedding
 * Uses proxy server to bypass CORS restrictions
 */
export async function queryPinecone(
    embedding: number[],
    pineconeConfig: {
        apiKey: string;
        host: string;
        indexName: string;
        namespace?: string;
        topK?: number;
    }
): Promise<PineconeMatch[]> {
    try {
        const { apiKey, host, indexName, namespace = '', topK = 50 } = pineconeConfig;

        // Use proxy server to bypass CORS
        const proxyUrl = 'http://localhost:3001/api/pinecone/query';

        // Allow up to 20 results for better context coverage
        const effectiveTopK = Math.min(Math.max(topK || 20, 15), 30);

        console.log('[Pinecone] Querying via Proxy Server | Host:', host, '| Namespace:', namespace || '(default)', '| TopK:', effectiveTopK);

        const response = await fetch(proxyUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Api-Key': apiKey,
                'X-Pinecone-Host': host
            },
            body: JSON.stringify({
                vector: embedding,
                topK: effectiveTopK,
                includeMetadata: true,
                namespace
            })
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('[Pinecone] Query error:', response.status, errorText);
            return [];
        }

        const data: PineconeQueryResponse = await response.json();
        console.log('[Pinecone] Query success! Matches:', data.matches?.length || 0);
        return data.matches || [];
    } catch (error) {
        console.error('[Pinecone] Query failed:', error);
        return [];
    }
}

/**
 * High-level function: Get context from Pinecone for RAG
 * This is the main function called by geminiService
 */

// Thai synonym mapping for query expansion
const SYNONYM_MAP: Record<string, string[]> = {
    'จองรถ': ['ยานพาหนะ', 'รถราชการ', 'การจองยานพาหนะ', 'ขอใช้รถ'],
    'รถ': ['ยานพาหนะ', 'รถยนต์', 'รถราชการ'],
    'ประชุม': ['ห้องประชุม', 'การจองห้องประชุม', 'meeting room'],
    'จองห้อง': ['ห้องประชุม', 'การจองห้องประชุม', 'booking'],
    'แจ้งซ่อม': ['ซ่อมบำรุง', 'maintenance', 'แจ้งปัญหา'],
    'ซ่อม': ['ซ่อมบำรุง', 'แจ้งซ่อม', 'maintenance'],
    'สารบรรณ': ['เอกสาร', 'หนังสือราชการ', 'งานธุรการ'],
    'คู่มือ': ['manual', 'วิธีใช้งาน', 'ขั้นตอน'],
};

function expandQuery(query: string): string {
    let expandedQuery = query;
    for (const [keyword, synonyms] of Object.entries(SYNONYM_MAP)) {
        if (query.includes(keyword)) {
            expandedQuery += ' ' + synonyms.join(' ');
        }
    }
    return expandedQuery;
}

export async function getPineconeContext(
    query: string,
    categoryConfig: {
        pineconeApiKey: string;
        pineconeHost: string;
        pineconeIndex: string;
        pineconeNamespace?: string;
        ragTopK?: number;
    },
    geminiApiKey: string
): Promise<string> {
    // Expand query with synonyms for better matching
    const expandedQuery = expandQuery(query);
    console.log('[Pinecone] Starting RAG retrieval for query:', query.substring(0, 50) + '... (expanded:', expandedQuery.length, 'chars)');

    // Step 1: Generate embedding for the EXPANDED query
    const embedding = await generateEmbedding(expandedQuery, geminiApiKey);
    if (!embedding) {
        console.warn('[Pinecone] Failed to generate embedding, skipping RAG');
        return '';
    }

    // Step 2: Query Pinecone with the embedding
    const matches = await queryPinecone(embedding, {
        apiKey: categoryConfig.pineconeApiKey,
        host: categoryConfig.pineconeHost,
        indexName: categoryConfig.pineconeIndex,
        namespace: categoryConfig.pineconeNamespace,
        topK: categoryConfig.ragTopK || 20
    });

    if (matches.length === 0) {
        console.log('[Pinecone] No matches found');
        return '';
    }

    // Step 3: Filter by score - lowered threshold for better coverage
    const MIN_SCORE = 0.40; // Lowered from 0.70 to allow more matches
    const relevantMatches = matches.filter(m => m.score >= MIN_SCORE);

    console.log(`[Pinecone] Filtering: ${relevantMatches.length}/${matches.length} matches passed score threshold (${MIN_SCORE})`);

    // Log top 3 scores for debugging
    if (matches.length > 0) {
        const topScores = matches.slice(0, 3).map(m => (m.score * 100).toFixed(1) + '%').join(', ');
        console.log(`[Pinecone] Top 3 scores: ${topScores}`);
    }

    if (relevantMatches.length === 0) {
        return '';
    }

    const contextParts = relevantMatches
        .filter(m => m.metadata?.text || m.metadata?.content)
        .map((m, i) => {
            const text = m.metadata?.text || m.metadata?.content || '';
            const title = m.metadata?.title || m.metadata?.source || `Document ${i + 1}`;
            const score = (m.score * 100).toFixed(1);
            return `【${title}】(relevance: ${score}%)\n${text}`;
        });

    const context = contextParts.join('\n\n---\n\n');
    console.log(`[Pinecone] Context generated from ${relevantMatches.length} relevant matches, length: ${context.length}`);

    return context;
}

/**
 * Test Pinecone connection and fetch index info
 */
export async function testPineconeConnection(
    apiKey: string,
    host: string
): Promise<{
    success: boolean;
    message: string;
    indexName?: string;
    namespaces?: string[];
    vectorCount?: number;
}> {
    try {
        if (!apiKey || !host) {
            return { success: false, message: 'กรุณาระบุ API Key และ Host' };
        }

        // Use proxy server to bypass CORS
        const proxyUrl = 'http://localhost:3001/api/pinecone/describe_index_stats';

        // Extract index name from host (e.g., "n8n-chatbor-moe-0a3543c.svc.aped-4627-b74a.pinecone.io" -> "n8n-chatbor-moe")
        const hostWithoutProtocol = host.replace(/^https?:\/\//, '');
        const indexName = hostWithoutProtocol.split('.')[0].split('-').slice(0, -1).join('-') || hostWithoutProtocol.split('.')[0];

        console.log('[Pinecone Test] Using Proxy Server | Host:', host);

        // Try to describe the index (a simple health check)
        const response = await fetch(proxyUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Api-Key': apiKey,
                'X-Pinecone-Host': host
            },
            body: JSON.stringify({})
        });

        if (response.ok) {
            const data = await response.json();
            const vectorCount = data.totalVectorCount || 0;

            // Extract namespaces from the response
            const namespaceData = data.namespaces || {};
            const namespaces = Object.keys(namespaceData);

            console.log('[Pinecone Test] Success! Vectors:', vectorCount, 'Namespaces:', namespaces);

            return {
                success: true,
                message: `✅ เชื่อมต่อสำเร็จ! (${vectorCount.toLocaleString()} vectors, ${namespaces.length} namespaces)`,
                indexName: indexName,
                namespaces: namespaces.length > 0 ? namespaces : [''],
                vectorCount: vectorCount
            };
        } else if (response.status === 401 || response.status === 403) {
            return { success: false, message: '❌ API Key ไม่ถูกต้อง' };
        } else if (response.status === 404) {
            return { success: false, message: '❌ ไม่พบ Index (ตรวจสอบ Host URL)' };
        } else {
            return { success: false, message: `❌ Server Error (${response.status})` };
        }
    } catch (error: any) {
        console.error('[Pinecone Test] Error:', error);
        if (error.message?.includes('Failed to fetch') || error.name === 'TypeError') {
            return { success: false, message: '🌐 CORS Error: ต้องใช้ Backend Proxy หรือเปิด CORS' };
        }
        return { success: false, message: '🌐 Network Error' };
    }
}

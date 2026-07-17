// Vercel Edge Function — proxy para criptoya.com/api/dolar
export const config = { runtime: 'edge' };

export default async function handler(req) {
  try {
    const res = await fetch('https://criptoya.com/api/dolar', {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; seguimiento-fx/1.0)',
        'Accept': 'application/json'
      }
    });
    if (!res.ok) {
      return new Response(JSON.stringify({ error: `criptoya status ${res.status}` }), {
        status: 502,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
      });
    }
    const data = await res.json();
    return new Response(JSON.stringify(data), {
      status: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Cache-Control': 's-maxage=30, stale-while-revalidate=60'
      }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message, stack: e.stack }), {
      status: 500,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
    });
  }
}

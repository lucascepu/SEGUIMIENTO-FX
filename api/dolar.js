// Vercel Edge Function — proxy para criptoya.com/api/dolar
// Resuelve el problema de CORS: el browser llama a /api/dolar (mismo dominio)
// y esta función hace el fetch a criptoya en el servidor

export const config = { runtime: 'edge' };

export default async function handler(req) {
  try {
    const res = await fetch('https://criptoya.com/api/dolar', {
      headers: { 'User-Agent': 'seguimiento-fx/1.0' }
    });
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
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

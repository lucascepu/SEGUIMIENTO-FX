// Vercel Serverless Function — proxy para criptoya.com/api/dolar
export default async function handler(req, res) {
  try {
    const response = await fetch('https://criptoya.com/api/dolar', {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; seguimiento-fx/1.0)',
        'Accept': 'application/json'
      }
    });
    if (!response.ok) {
      res.status(502).json({ error: `criptoya status ${response.status}` });
      return;
    }
    const data = await response.json();
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json(data);
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}

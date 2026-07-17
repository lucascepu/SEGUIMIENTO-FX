// Vercel Serverless Function — proxy criptoya.com, devuelve solo mayorista
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
    // Devolver solo el campo mayorista
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json({ mayorista: data.mayorista });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
}

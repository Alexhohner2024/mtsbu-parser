import { parseMtsbuHtml } from "../lib/parseMtsbuHtml.js";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).json({ ok: false, error: "Method not allowed" });
    return;
  }

  try {
    const { url } = req.body || {};

    if (!url || typeof url !== "string") {
      res.status(400).json({ ok: false, error: "Field 'url' is required" });
      return;
    }

    if (!url.startsWith("https://policy.mtsbu.ua/")) {
      res.status(400).json({ ok: false, error: "Invalid MTSBU URL" });
      return;
    }

    const response = await fetch(url, {
      method: "GET",
      headers: {
        "User-Agent": process.env.USER_AGENT || "Mozilla/5.0"
      }
    });

    if (!response.ok) {
      res.status(502).json({
        ok: false,
        error: `Upstream MTSBU error: ${response.status} ${response.statusText}`
      });
      return;
    }

    const html = await response.text();
    const data = parseMtsbuHtml(html);

    if (!data || !data.policyNumber) {
      res.status(500).json({
        ok: false,
        error: "Failed to parse MTSBU page; structure may have changed"
      });
      return;
    }

    res.status(200).json({ ok: true, ...data });
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error(err);
    res.status(500).json({
      ok: false,
      error: err.message || "Unexpected error"
    });
  }
}

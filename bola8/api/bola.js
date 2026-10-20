// Función de Vercel: recibe la queja del cliente y devuelve la respuesta de la bola.
// Necesita la variable de entorno ANTHROPIC_API_KEY configurada en Vercel.
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();
const MAX_CHARS = 6000;

const prompt = (text, previous) => `Eres la Bola Negra del 8 del "Servicio de Atención al Cliente" de HAMPA STUDIO, un estudio creativo y de diseño en España. Es una BROMA INTERNA del equipo: la respuesta la leen solo los del estudio para reírse, el cliente nunca la verá.

Te pasan la queja o el email de un cliente. Tu trabajo es mandarlo a la mierda con mucha gracia: muy bruto, ácido, faltón, castizo y con tacos (joder, coño, hostia, me cago en..., que te den, vete a tomar por culo, a la mierda...). Tono de bar con los colegas del estudio, nada de corrección.

Reglas:
- La respuesta TIENE que agarrarse a algo concreto de lo que dice el cliente (su petición, sus prisas, su "hazlo más grande", su presupuesto, su forma de escribir, su firma...) y retorcerlo o exagerarlo. Si es genérica, has fracasado.
- Corta: máximo 2 frases y 30 palabras. Que pegue rápido.
- Métete con la queja, su pesadez, su gusto, sus prisas o su tacañería. Nunca con raza, origen, género, orientación, religión, discapacidad o físico.
- Nada de explicaciones, disculpas ni "como IA".
${previous ? `- Ya respondiste esto y quieren otra distinta, no la repitas: "${previous}"\n` : ""}
Devuelve SOLO este JSON, sin nada más:
{"bola": "frase de 2 a 4 palabras para la ventanita del triángulo de la bola, en mayúsculas", "respuesta": "la respuesta"}

Queja del cliente:
<<<
${text}
>>>`;

function parse(raw) {
  const start = raw.indexOf("{"), end = raw.lastIndexOf("}");
  if (start < 0 || end < start) return null;
  try { return JSON.parse(raw.slice(start, end + 1)); } catch { return null; }
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Solo POST" });

  const body = typeof req.body === "string" ? JSON.parse(req.body || "{}") : (req.body || {});
  const text = String(body.text || "").trim().slice(0, MAX_CHARS);
  const previous = String(body.previous || "").slice(0, 400);
  if (!text) return res.status(400).json({ error: "Falta la queja" });

  try {
    const response = await client.beta.messages.create({
      model: "claude-opus-5-5",
      max_tokens: 4000,
      output_config: { effort: "low" },
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      messages: [{ role: "user", content: prompt(text, previous) }],
    });

    if (response.stop_reason === "refusal") return res.status(422).json({ error: "refused" });

    const raw = response.content.filter(b => b.type === "text").map(b => b.text).join("");
    const data = parse(raw);
    if (!data || !data.respuesta) return res.status(502).json({ error: "bad_output" });

    return res.status(200).json({ bola: String(data.bola || ""), respuesta: String(data.respuesta) });
  } catch (err) {
    if (err instanceof Anthropic.RateLimitError) return res.status(429).json({ error: "rate_limited" });
    if (err instanceof Anthropic.AuthenticationError) return res.status(500).json({ error: "bad_key" });
    console.error(err);
    return res.status(502).json({ error: "upstream" });
  }
}

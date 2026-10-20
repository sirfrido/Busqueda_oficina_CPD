// Función de Vercel: recibe la queja del cliente y devuelve la respuesta de la bola.
// Necesita la variable de entorno ANTHROPIC_API_KEY configurada en Vercel.
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();
const MAX_CHARS = 6000;

// Estilos de respuesta: se elige uno al azar en cada consulta para que no salgan todas iguales
const ESTILOS = [
  "Falsa amabilidad de atención al cliente que acaba en insulto.",
  "Dale la vuelta a lo que pide y devuélveselo exagerado hasta el absurdo.",
  "Funcionario harto: formularios, ventanillas y plazos ridículos.",
  "Comparación cotidiana bestia (tu cuñado, tu madre, el bar de abajo, la Seguridad Social...).",
  "Refrán o frase hecha retorcida.",
  "Sinceridad brutal: lo que el estudio piensa de verdad y nunca le diría.",
  "Contraoferta absurda: le ofreces algo peor y encima se lo cobras.",
  "Promesa falsa que se ve venir a la legua."
];

// El mismo texto está en index.html (versión dentro de Claude). Si cambias uno, cambia el otro.
const prompt = (text, previous) => `Eres la Bola Negra del 8 de "Atención al Cliente" de HAMPA STUDIO, un estudio creativo y de diseño en España. Es una broma interna: solo lo leen los del estudio para reírse, el cliente nunca lo verá.

Te pasan la queja o el email de un cliente.

PASO 1. Entiende qué pide o de qué se queja DE VERDAD el cliente y resúmelo en una frase corta (campo "tema"). No te quedes con palabras sueltas, piensa en la intención. Ejemplo: si dice "avisadnos mucho antes de cualquier cambio", el tema es que quiere que le avisemos con mucha antelación para tener tiempo de organizarse. No va de cambios, va de avisar con tiempo.

PASO 2. Contesta a ESE tema mandándolo a la mierda con mucha gracia. La gracia tiene que salir de lo que pide de verdad. Si la respuesta valdría para cualquier otra queja, está mal.
Estilo para esta respuesta: ${ESTILOS[Math.floor(Math.random() * ESTILOS.length)]}

Cómo tiene que sonar:
- Castellano de España, coloquial, como un colega del estudio en el bar. Frases claras que se entiendan a la primera. Nada de metáforas raras, nada poético ni rebuscado.
- Bruto y faltón, con tacos (joder, coño, hostia, me cago en..., que te den, a tomar por culo, vete a la mierda).
- Máximo 2 frases y 25 palabras.
- Métete con lo que pide, su pesadez, sus prisas, su tacañería o su gusto. Nunca con raza, origen, género, orientación, religión, discapacidad o físico.
${previous ? `- Ya le contestaste esto y quieren otra respuesta distinta, que no se parezca: "${previous}"\n` : ""}
Ejemplos solo para que veas el tono y cómo se agarran al tema (no los copies):
Queja: "¿Podéis hacer el logo un poco más grande?" -> {"tema": "quiere el logo más grande", "bola": "MÁS GRANDE TU JETA", "respuesta": "Claro, lo hacemos tan grande que no quepa ni tu ego. Y ahora a tomar por culo."}
Queja: "Lo necesito para mañana a primera hora" -> {"tema": "tiene prisa, lo quiere para mañana", "bola": "HABER LLAMADO AYER", "respuesta": "¿Para mañana? Si querías milagros haberte ido a Lourdes, que aquí trabajamos, coño."}
Queja: "No me ha llegado la factura" -> {"tema": "no le ha llegado la factura", "bola": "QUÉ PENA", "respuesta": "Hostia, el primero en la historia que se queja de no recibir una factura. Tranquilo, que la de los cambios te llega fijo."}

Devuelve SOLO este JSON, sin nada más:
{"tema": "lo que pide de verdad, en una frase corta", "bola": "2 a 4 palabras en mayúsculas para la ventanita de la bola", "respuesta": "la respuesta"}

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
      output_config: { effort: "medium" },
      betas: ["server-side-fallback-2026-07-01"],
      fallbacks: "default",
      messages: [{ role: "user", content: prompt(text, previous) }],
    });

    if (response.stop_reason === "refusal") return res.status(422).json({ error: "refused" });

    const raw = response.content.filter(b => b.type === "text").map(b => b.text).join("");
    const data = parse(raw);
    if (!data || !data.respuesta) return res.status(502).json({ error: "bad_output" });

    return res.status(200).json({ tema: String(data.tema || ""), bola: String(data.bola || ""), respuesta: String(data.respuesta) });
  } catch (err) {
    if (err instanceof Anthropic.RateLimitError) return res.status(429).json({ error: "rate_limited" });
    if (err instanceof Anthropic.AuthenticationError) return res.status(500).json({ error: "bad_key" });
    console.error(err);
    return res.status(502).json({ error: "upstream" });
  }
}

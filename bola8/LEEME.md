# Bola 8 · Atención al cliente HAMPA STUDIO

Página de broma interna: pegas la queja o el email de un cliente y la bola le contesta (con IA) mandándolo a la mierda.

## Publicarla en internet (Vercel, gratis)

1. Consigue una clave de la API de Claude en https://console.anthropic.com (Settings → API Keys) y añade algo de saldo.
2. Entra en https://vercel.com con tu cuenta de GitHub → **Add New… → Project** → importa `busqueda_oficina_cpd`.
3. En la pantalla de configuración:
   - **Root Directory**: `bola8`
   - **Environment Variables**: nombre `ANTHROPIC_API_KEY`, valor = tu clave.
4. Pulsa **Deploy**.
5. En el proyecto: **Settings → Git → Production Branch** = `claude/kind-rubin-davtwx` y vuelve a desplegar (Deployments → ⋯ → Redeploy).

La dirección que te da Vercel (tipo `https://bola8-hampa.vercel.app`) se abre en cualquier navegador sin cuenta.

## Archivos

- `index.html` — la página.
- `api/bola.js` — la función del servidor que llama a Claude (la clave nunca llega al navegador).

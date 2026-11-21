// The desk's front end, bundled into ../plugin/web: index.html and
// popout.html (the page Dockview opens a popped-out group in), and one
// script and one stylesheet under assets/. No inline script, so the page's
// Content-Security-Policy needs none. bundled.json lists every file bundled.
import { build } from 'esbuild';
import fs from 'node:fs';
import path from 'node:path';

const here = path.dirname(new URL(import.meta.url).pathname);
const out = path.resolve(here, '../plugin/web');
fs.rmSync(out, { recursive: true, force: true });
fs.mkdirSync(path.join(out, 'assets'), { recursive: true });
const built = await build({
  entryPoints: { desk: path.join(here, 'src/main.tsx') },
  outdir: path.join(out, 'assets'),
  bundle: true,
  format: 'esm',
  minify: true,
  sourcemap: false,
  target: ['chrome120', 'firefox120', 'safari17'],
  jsx: 'automatic',
  define: { 'process.env.NODE_ENV': '"production"' },
  legalComments: 'none',
  logLevel: 'info',
  metafile: true,
});
// What went into the bundle, for the licence scan (ci/frontend.sh).
fs.writeFileSync(path.join(here, 'bundled.json'), JSON.stringify(Object.keys(built.metafile.inputs).sort(), null, 1));
for (const page of ['index.html', 'popout.html']) fs.copyFileSync(path.join(here, page), path.join(out, page));

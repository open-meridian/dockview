// The notices of every package the desk's build ships (web/package-lock.json's
// entries that are not dev-only), each with its licence and notice files; and
// the licence scan: a package under the AGPL, the GPL or the SSPL fails it, and
// so does `dockview-enterprise` (proprietary) under any licence, since only
// Dockview's MIT packages are used. Usage: node notices.mjs WEB_DIR OUT
import fs from 'node:fs';
import path from 'node:path';

const [web, out] = process.argv.slice(2);
const lock = JSON.parse(fs.readFileSync(path.join(web, 'package-lock.json'), 'utf8'));
const REFUSED = /(^|[^L])(A?GPL|SSPL)/i;
const parts = ['Notices of the packages the desk\'s front end ships', ''];
const refused = [];
let count = 0;
for (const [where, entry] of Object.entries(lock.packages ?? {})) {
  if (!where || entry.dev || entry.devOptional || entry.link) continue;
  const name = where.replace(/^.*node_modules\//, '');
  if (name === 'dockview-enterprise') refused.push(`${name}@${entry.version}: proprietary, never used`);
  const dir = path.join(web, where);
  if (!fs.existsSync(dir)) continue;
  const licence = String(entry.license ?? JSON.parse(fs.readFileSync(path.join(dir, 'package.json'), 'utf8')).license ?? 'UNKNOWN');
  const choices = licence.replace(/[()]/g, '').split(/\s+OR\s+/i);
  if (choices.every((each) => REFUSED.test(each))) refused.push(`${name}@${entry.version}: ${licence}`);
  const texts = fs.readdirSync(dir).filter((f) => /^(licen[cs]e|copying|notice)/i.test(f));
  if (!texts.length) refused.push(`${name}@${entry.version}: no licence file to ship`);
  parts.push(`== ${name}@${entry.version} (${licence}) ==`);
  for (const file of texts) parts.push(fs.readFileSync(path.join(dir, file), 'utf8'));
  count += 1;
}
if (refused.length) {
  console.error(`notices: the desk's build ships a package it cannot:\n${refused.join('\n')}`);
  process.exit(1);
}
fs.writeFileSync(out, parts.join('\n'));
console.log(`notices: ${count} packages, none under the AGPL, the GPL or the SSPL, and no dockview-enterprise`);

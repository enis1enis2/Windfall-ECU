#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if [ -f "node_modules/esbuild/bin/esbuild" ]; then
  ESBUILD="node_modules/esbuild/bin/esbuild"
elif command -v esbuild &>/dev/null; then
  ESBUILD="esbuild"
else
  echo "esbuild not found — skipping JS bundle"
  exit 0
fi

node -e "
const b=require('esbuild'),fs=require('fs');
const src=['app.js','terminal.js','filemanager.js','backups.js','import.js','download.js','plugins.js']
  .map(f=>fs.readFileSync('static/js/'+f,'utf8')).join('\n');
fs.writeFileSync('/tmp/_wf_bundle.js',src);
b.buildSync({entryPoints:['/tmp/_wf_bundle.js'],minify:true,keepNames:true,target:'es2022',outfile:'static/js/windfall.min.js',allowOverwrite:true});
fs.unlinkSync('/tmp/_wf_bundle.js');
"

node -e "const c=require('csso'),f=require('fs');f.writeFileSync('static/css/style.min.css',c.minify(f.readFileSync('static/css/style.css','utf8')).css);"

echo "Static build: done"

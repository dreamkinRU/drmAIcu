const ts = require('typescript');
let src = '';
process.stdin.on('data', (d) => { src += d; });
process.stdin.on('end', () => {
  const out = ts.transpileModule(src, {
    reportDiagnostics: true,
    fileName: process.argv[2] || 'file.tsx',
    compilerOptions: {
      jsx: ts.JsxEmit.ReactJSX,
      target: ts.ScriptTarget.ES2020,
      module: ts.ModuleKind.ESNext
    }
  });
  const errs = (out.diagnostics || []).filter((d) => d.category === ts.DiagnosticCategory.Error);
  if (errs.length === 0) { process.stdout.write('OK'); process.exit(0); }
  const d = errs[0];
  let msg = ts.flattenDiagnosticMessageText(d.messageText, ' ');
  if (d.file && d.start != null) {
    const p = d.file.getLineAndCharacterOfPosition(d.start);
    msg = 'line ' + (p.line + 1) + ': ' + msg;
  }
  process.stdout.write(msg);
  process.exit(1);
});

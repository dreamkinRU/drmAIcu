import assert from 'node:assert/strict';
import { cleanCommandOutput, updateStateLabel, hasNpmWarnings } from '../src/components/tabs/updatePresentation.ts';

assert.equal(cleanCommandOutput('\x1b[32mPASS\x1b[0m\r\nnext'), 'PASS\nnext');
assert.equal(cleanCommandOutput('\x1b]8;;https://example.com\x1b\\link\x1b]8;;\x1b\\'), 'link');
assert.equal(cleanCommandOutput('\x9b36mtext\x1b[39m'), 'text');
assert.equal(cleanCommandOutput('plain [32m text'), 'plain [32m text');
assert.equal(cleanCommandOutput(undefined), '');
assert.equal([ 'out', 'err' ].map(cleanCommandOutput).join('\n'), 'out\nerr');
assert.equal(updateStateLabel('COMPLETED'), 'Завершено');
assert.equal(updateStateLabel('RESTART_REQUIRED'), 'Требуется перезапуск');
assert.equal(updateStateLabel('FUTURE_STATE'), 'FUTURE_STATE');
assert.equal(updateStateLabel('toString'), 'toString');
assert.equal(hasNpmWarnings({step:'npm',ok:true,stderr:'\x1b[33mnpm warn deprecated recharts\x1b[0m'}), true);
assert.equal(hasNpmWarnings({step:'npm',ok:false,stderr:'npm warn deprecated'}), false);
assert.equal(hasNpmWarnings({step:'npm',ok:true,stderr:'npm error ERESOLVE'}), false);
assert.equal(hasNpmWarnings({step:'frontend_build',ok:true,stderr:'npm warn example'}), false);
console.log('14 presentation assertions passed');
